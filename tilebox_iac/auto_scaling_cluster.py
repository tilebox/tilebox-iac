from pathlib import Path
from typing import Any, TypedDict

from jinja2 import Environment, FileSystemLoader
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_gcp.compute import (
    InstanceTemplate,
    Network,
    RegionAutoscaler,
    RegionInstanceGroupManager,
    Router,
    RouterNat,
    Subnetwork,
)
from pulumi_gcp.secretmanager import Secret as GCPSecret
from typing_extensions import NotRequired

from tilebox_iac.secrets import Secret
from tilebox_iac.service_account import ServiceAccount, ServiceAccountConfigDict

env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=True)
template = env.get_template("cloud-init.yaml")


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the VMs."""
    image: str = kwargs["image"]
    tag: str = kwargs["tag"]
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]

    return template.render(
        CONTAINER_IMAGE=f"{image}:{tag}",
        REGISTRY_HOSTNAME=image.split("/")[0],
        SECRETS=secrets,
        ENVIRONMENT_VARS=environment_variables,
    )


class ContainerConfig(TypedDict):
    image: Input[str]
    tag: NotRequired[Input[str]]


class AutoScalingGCPCluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        container: ContainerConfig,
        gcp_project: str,
        gcp_region: str,
        machine_type: str,
        cpu_target: float,
        cluster_enabled: bool,
        min_replicas_config: int,
        max_replicas_config: int,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        roles: ServiceAccountConfigDict | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """An auto-scaling cluster of Spot instances running a Docker container.

        Args:
            name: Name of the cluster.
            container: Container image to run.
            gcp_project: GCP project ID to deploy the cluster in.
            gcp_region: Region to deploy the cluster in.
            machine_type: Machine type to use for the VMs.
            cpu_target: CPU target for autoscaling.
            cluster_enabled : Whether the cluster is enabled.
            min_replicas_config: Minimum number of replicas.
            max_replicas_config: Maximum number of replicas.
            environment_variables: Environment variables to pass to the container.
            roles: Roles to assign to the service account.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:AutoScalingGCPCluster", name, opts=opts)

        if container.get("tag") == "":
            raise ValueError(
                "Container tag cannot be empty. Leave unset or manually set to `latest` to use the latest tag."
            )

        required_roles = {
            "roles/monitoring.metricWriter",  # write metrics to the monitoring console
        }
        used_secrets: dict[str, GCPSecret] = {}

        envs: dict[str, Input[str]] = {}
        if environment_variables is not None:
            for key in sorted(environment_variables):
                value = environment_variables[key]
                if isinstance(value, Secret):
                    used_secrets[value.resource_name] = value.secret
                else:
                    envs[key] = value

        if roles is None:
            roles = {"roles": list(required_roles)}
        else:
            configured_roles = set(roles.get("roles", []))
            roles["roles"] = list(required_roles | configured_roles)

        secret_roles = list(roles.get("secret_roles", []))
        for secret_name, secret in used_secrets.items():
            secret_roles.append(
                {"secret_slug": secret_name, "secret": secret, "role": "roles/secretmanager.secretAccessor"}
            )
        roles["secret_roles"] = secret_roles

        service_account = ServiceAccount.from_config(
            name, gcp_project, roles, opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self)
        )

        network = Network(
            f"{name}-network",
            name=f"{name}-network",
            auto_create_subnetworks=False,
            opts=ResourceOptions(parent=self),
        )
        pga_subnet = Subnetwork(
            f"{name}-pga-subnet",
            name=f"{name}-pga-subnet",
            ip_cidr_range="10.10.0.0/24",
            network=network.self_link,
            region=gcp_region,
            private_ip_google_access=True,  # Private Google Access (PGA) enabled
            opts=ResourceOptions(depends_on=[network], parent=self),
        )

        # Router and RouterNAT allow VMs to access the internet (outbound)
        router = Router(
            f"{name}-router",
            name=f"{name}-router",
            network=network.self_link,
            region=gcp_region,
            opts=ResourceOptions(depends_on=[network], parent=self),
        )
        self.router_nat = RouterNat(
            f"{name}-nat",
            name=f"{name}-nat",
            router=router.name,
            region=gcp_region,
            source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES",
            nat_ip_allocate_option="AUTO_ONLY",
            opts=ResourceOptions(depends_on=[router], parent=self),
        )

        secrets = {}
        for secret_name, secret in used_secrets.items():
            # convert secret_name from tilebox-api-key to TILEBOX_API_KEY
            secrets[secret_name.upper().replace("-", "_")] = secret.id

        cloud_init_config = Output.all(
            image=container["image"],
            tag=container.get("tag", "latest"),
            environment_variables=envs,
            secrets=secrets,
        ).apply(_get_cloud_init)

        # Define the Instance Template for the MIG
        instance_template = InstanceTemplate(
            f"{name}-template",
            machine_type=machine_type,
            metadata={
                "user-data": cloud_init_config,
                # Metadata key to enable the Ops Agent for monitoring (including memory) on Container-Optimized OS.
                # https://docs.cloud.google.com/container-optimized-os/docs/how-to/monitoring
                "google-monitoring-enabled": "true",
                # https://docs.cloud.google.com/compute/docs/oslogin
                "enable-oslogin": "TRUE",
            },
            disks=[
                {
                    "source_image": "cos-cloud/cos-stable",
                    "auto_delete": True,
                    "boot": True,
                    "disk_size_gb": 20,
                },
            ],
            network_interfaces=[{"subnetwork": pga_subnet.self_link}],
            service_account={
                "email": service_account.email,
                "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
            },
            # Use Spot VMs for cost savings. The API requires these specific scheduling options.
            scheduling={
                "provisioning_model": "SPOT",
                "preemptible": True,
                "automatic_restart": False,
                "on_host_maintenance": "TERMINATE",
                "instance_termination_action": "STOP",
            },
            opts=ResourceOptions(depends_on=[service_account, pga_subnet], parent=self),
        )

        # Define the Managed Instance Group
        mig = RegionInstanceGroupManager(
            f"{name}-mig",
            base_instance_name=name,
            region=gcp_region,
            versions=[
                {
                    "instance_template": instance_template.self_link,
                    "name": "primary",
                }
            ],
            update_policy={
                "type": "PROACTIVE",
                "minimal_action": "REPLACE",
                # Increase surge for faster rollouts
                "max_surge_fixed": 10,
                "max_unavailable_fixed": 0,
            },
            opts=ResourceOptions(depends_on=[instance_template], parent=self),
        )

        if cluster_enabled:
            # If the cluster is enabled, the autoscaler is ON and controls the size.
            # The MIG's target_size is not set, ceding control to the autoscaler,
            # which will scale up to min_replicas immediately.
            min_replicas = min_replicas_config
            max_replicas = max_replicas_config
        else:
            # If the cluster is disabled, the autoscaler is turned OFF.
            # The MIG's target_size is explicitly set to 0 to shut down all instances.
            min_replicas = 0
            max_replicas = 0

        # Define the Autoscaler for the MIG
        self.autoscaler = RegionAutoscaler(
            f"{name}-autoscaler",
            target=mig.self_link,
            region=gcp_region,
            autoscaling_policy={
                "max_replicas": max_replicas,
                "min_replicas": min_replicas,
                "cooldown_period": 60,
                "mode": "ON",
                "cpu_utilization": {
                    "target": cpu_target,
                },
            },
            opts=ResourceOptions(depends_on=[mig], parent=self),
        )

        self.register_outputs({})
