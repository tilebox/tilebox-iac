from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from pulumi import Alias, ComponentResource, Input, Output, ResourceOptions
from pulumi_gcp.compute import (
    Firewall,
    InstanceTemplate,
    InstanceTemplateNetworkInterfaceArgs,
    InstanceTemplateNetworkInterfaceArgsDict,
    RegionAutoscaler,
    RegionHealthCheck,
    RegionInstanceGroupManager,
)

from tilebox_iac.gcp.secrets import Secret
from tilebox_iac.gcp.service_account import ServiceAccount, ServiceAccountConfigDict
from tilebox_iac.release_runner import RUNNER_IMAGE, encode_environment_variables, validate_environment_variable_name

# This template renders cloud-init YAML rather than HTML.
env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=False)  # noqa: S701
template = env.get_template("cloud-init.yaml")


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the GCP VMs."""
    runner_image: str = kwargs["runner_image"]
    registry_hostname = runner_image.split("/", maxsplit=1)[0]
    is_gcp_registry = registry_hostname == "gcr.io" or registry_hostname.endswith((".gcr.io", ".pkg.dev"))
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]

    return template.render(
        CONTAINER_IMAGE=runner_image,
        GCP_REGISTRY_HOSTNAME=registry_hostname if is_gcp_registry else None,
        SECRETS=secrets,
        ENVIRONMENT_FILE=encode_environment_variables(environment_variables),
    )


def _get_health_check_network(network_interfaces: Any, health_check_network: str | None) -> str:
    if health_check_network:
        return health_check_network
    if not network_interfaces:
        return "default"

    first_interface = network_interfaces[0]
    network = (
        first_interface.get("network")
        if isinstance(first_interface, dict)
        else getattr(first_interface, "network", None)
    )
    if not network:
        raise ValueError("health_check_network is required when network_interfaces[0] does not specify its network")
    return str(network)


class AutoScalingCluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        gcp_project: str,
        gcp_region: str,
        machine_type: str,
        cpu_target: float,
        cluster_enabled: bool,
        min_replicas_config: int,
        max_replicas_config: int,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        roles: ServiceAccountConfigDict | None = None,
        network_interfaces: Input[
            Sequence[Input[InstanceTemplateNetworkInterfaceArgs | InstanceTemplateNetworkInterfaceArgsDict]]
        ]
        | None = None,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 40,
        opts: ResourceOptions | None = None,
        *,
        health_check_network: Input[str] | None = None,
        health_check_network_project: Input[str] | None = None,
        auto_healing_enabled: bool = False,
    ) -> None:
        """An auto-scaling cluster of Spot instances running a Docker container.

        Args:
            name: Name of the cluster.
            gcp_project: GCP project ID to deploy the cluster in.
            gcp_region: Region to deploy the cluster in.
            machine_type: Machine type to use for the VMs.
            cpu_target: CPU target for autoscaling.
            cluster_enabled: Whether the cluster is enabled.
            min_replicas_config: Minimum number of replicas.
            max_replicas_config: Maximum number of replicas.
            environment_variables: Environment variables to pass to the runner. TILEBOX_API_KEY is required;
                TILEBOX_CLUSTER is optional and defaults to the account's default cluster.
            roles: Roles to assign to the service account.
            network_interfaces: List of network interfaces to attach to the VMs.
            runner_image: Runner container image. Defaults to the official Tilebox runner. Private Artifact Registry
                images require reader permissions in roles.
            root_volume_size_gb: Root persistent disk size in GiB. Defaults to 40 GiB.
            health_check_network: VPC network for the runner health-check firewall. Defaults to the first network
                interface's network, or the default VPC when no interfaces are configured.
            health_check_network_project: Project that owns the health-check network. Defaults to gcp_project.
            auto_healing_enabled: Whether the MIG replaces instances that fail runner health checks. Enable only after
                every existing instance has rolled to a template containing the health endpoint.
            opts: Pulumi resource options.
        """
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:AutoScalingGCPCluster")]))
        super().__init__("tilebox:gcp:AutoScalingCluster", name, opts=opts)

        if environment_variables is None or "TILEBOX_API_KEY" not in environment_variables:
            raise ValueError("environment_variables must include TILEBOX_API_KEY")

        required_roles = {
            "roles/monitoring.metricWriter",
        }
        used_secrets: dict[str, Secret] = {}

        envs: dict[str, Input[str]] = {}
        if environment_variables is not None:
            for key in sorted(environment_variables):
                validate_environment_variable_name(key)
                value = environment_variables[key]
                if isinstance(value, Secret):
                    used_secrets[key] = value
                else:
                    envs[key] = value

        if roles is None:
            role_config: ServiceAccountConfigDict = {"roles": list(required_roles)}
        else:
            role_config = dict(roles)  # type: ignore[assignment]
            configured_roles = set(roles.get("roles", []))
            role_config["roles"] = list(required_roles | configured_roles)

        secret_roles = list(role_config.get("secret_roles", []))
        secret_roles.extend(
            [
                {
                    "secret_slug": secret.resource_name,
                    "secret": secret.secret,
                    "role": "roles/secretmanager.secretAccessor",
                }
                for secret in used_secrets.values()
            ]
        )
        role_config["secret_roles"] = secret_roles

        service_account = ServiceAccount.from_config(
            name, gcp_project, role_config, opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self)
        )

        health_check = RegionHealthCheck(
            f"{name}-health-check",
            name=f"{name}-health-check",
            project=gcp_project,
            region=gcp_region,
            check_interval_sec=30,
            timeout_sec=5,
            healthy_threshold=1,
            unhealthy_threshold=3,
            http_health_check={
                "port": 8080,
                "request_path": "/health",
            },
            opts=ResourceOptions(parent=self),
        )
        health_check_network_output = Output.all(
            network_interfaces=network_interfaces,
            health_check_network=health_check_network,
        ).apply(lambda values: _get_health_check_network(values["network_interfaces"], values["health_check_network"]))
        health_check_firewall = Firewall(
            f"{name}-health-check",
            name=f"{name}-health-check",
            project=health_check_network_project if health_check_network_project is not None else gcp_project,
            network=health_check_network_output,
            direction="INGRESS",
            # Google Cloud health-check probe ranges.
            source_ranges=["130.211.0.0/22", "35.191.0.0/16"],
            target_service_accounts=[service_account.email],
            allows=[{"protocol": "tcp", "ports": ["8080"]}],
            opts=ResourceOptions(depends_on=[service_account], parent=self),
        )

        secrets = {}
        for secret_env_var, secret in used_secrets.items():
            secrets[secret_env_var] = secret.secret.id

        cloud_init_config = Output.all(
            runner_image=runner_image,
            environment_variables=envs,
            secrets=secrets,
        ).apply(_get_cloud_init)

        instance_template = InstanceTemplate(
            f"{name}-template",
            project=gcp_project,
            machine_type=machine_type,
            metadata={
                "user-data": cloud_init_config,
                "google-monitoring-enabled": "true",
                "enable-oslogin": "TRUE",
            },
            disks=[
                {
                    "source_image": "cos-cloud/cos-stable",
                    "auto_delete": True,
                    "boot": True,
                    "disk_size_gb": root_volume_size_gb,
                },
            ],
            network_interfaces=network_interfaces,
            service_account={
                "email": service_account.email,
                "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
            },
            scheduling={
                "provisioning_model": "SPOT",
                "preemptible": True,
                "automatic_restart": False,
                "on_host_maintenance": "TERMINATE",
                "instance_termination_action": "STOP",
            },
            opts=ResourceOptions(depends_on=[service_account], parent=self),
        )

        mig = RegionInstanceGroupManager(
            f"{name}-mig",
            project=gcp_project,
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
                "max_surge_fixed": 10,
                "max_unavailable_fixed": 0,
            },
            auto_healing_policies=(
                {
                    "health_check": health_check.id,
                    "initial_delay_sec": 900,
                }
                if auto_healing_enabled
                else None
            ),
            opts=ResourceOptions(
                depends_on=[instance_template, health_check, health_check_firewall],
                parent=self,
            ),
        )

        if cluster_enabled:
            min_replicas = min_replicas_config
            max_replicas = max_replicas_config
        else:
            min_replicas = 0
            max_replicas = 0

        self.autoscaler = RegionAutoscaler(
            f"{name}-autoscaler",
            project=gcp_project,
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
