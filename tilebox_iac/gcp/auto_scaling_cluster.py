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
from tilebox_iac.release_runner import RUNNER_IMAGE

env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=True)
template = env.get_template("cloud-init.yaml")


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the GCP VMs."""
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]

    return template.render(
        CONTAINER_IMAGE=RUNNER_IMAGE,
        SECRETS=secrets,
        ENVIRONMENT_VARS=environment_variables,
    )


def _get_health_check_network(network_interfaces: Any) -> str:
    if not network_interfaces:
        return "default"

    first_interface = network_interfaces[0]
    network = (
        first_interface.get("network")
        if isinstance(first_interface, dict)
        else getattr(first_interface, "network", None)
    )
    if not network:
        msg = "network_interfaces[0].network is required for GCP runner health checks"
        raise ValueError(msg)
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
        opts: ResourceOptions | None = None,
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
            environment_variables: Environment variables to pass to the container.
            roles: Roles to assign to the service account.
            network_interfaces: List of network interfaces to attach to the VMs. The first interface must include its
                network so the runner health-check firewall can target it.
            opts: Pulumi resource options.
        """
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:AutoScalingGCPCluster")]))
        super().__init__("tilebox:gcp:AutoScalingCluster", name, opts=opts)

        required_roles = {
            "roles/monitoring.metricWriter",
        }
        used_secrets: dict[str, Secret] = {}

        envs: dict[str, Input[str]] = {}
        if environment_variables is not None:
            for key in sorted(environment_variables):
                value = environment_variables[key]
                if isinstance(value, Secret):
                    used_secrets[key] = value
                else:
                    envs[key] = value

        if roles is None:
            roles = {"roles": list(required_roles)}
        else:
            configured_roles = set(roles.get("roles", []))
            roles["roles"] = list(required_roles | configured_roles)

        secret_roles = list(roles.get("secret_roles", []))
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
        roles["secret_roles"] = secret_roles

        service_account = ServiceAccount.from_config(
            name, gcp_project, roles, opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self)
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
        health_check_network = Output.from_input(network_interfaces).apply(_get_health_check_network)
        health_check_firewall = Firewall(
            f"{name}-health-check",
            name=f"{name}-health-check",
            project=gcp_project,
            network=health_check_network,
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
            environment_variables=envs,
            secrets=secrets,
        ).apply(_get_cloud_init)

        instance_template = InstanceTemplate(
            f"{name}-template",
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
                    "disk_size_gb": 20,
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
            auto_healing_policies={
                "health_check": health_check.id,
                "initial_delay_sec": 900,
            },
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
