import base64
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

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
from pulumi_gcp.secretmanager import SecretIamMember
from typing_extensions import NotRequired

from tilebox_iac.gcp.secrets import Secret
from tilebox_iac.gcp.service_account import ServiceAccount, ServiceAccountConfigDict
from tilebox_iac.release_runner import (
    RUNNER_IMAGE,
    encode_environment_variables,
    validate_environment_variable_name,
    validate_runner_image,
)

# Render cloud-init YAML.
env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=False)  # noqa: S701
template = env.get_template("cloud-init.yaml")


class SecretReference(TypedDict):
    secret_id: Input[str]
    rollout_marker: NotRequired[Input[str]]


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the GCP VMs."""
    runner_image = validate_runner_image(kwargs["runner_image"])
    registry_hostname = runner_image.split("/", maxsplit=1)[0]
    is_gcp_registry = registry_hostname == "gcr.io" or registry_hostname.endswith((".gcr.io", ".pkg.dev"))
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]
    for secret in secrets.values():
        if re.fullmatch(r"projects/[A-Za-z0-9_-]+/secrets/[A-Za-z0-9_-]+", secret) is None:
            raise ValueError("secret_id must have the form projects/PROJECT/secrets/SECRET")

    return template.render(
        CONTAINER_IMAGE=runner_image,
        GCP_REGISTRY_HOSTNAME=registry_hostname if is_gcp_registry else None,
        SECRETS=secrets,
        SECRET_VERSIONS=base64.b64encode(
            json.dumps(kwargs.get("secret_versions", {}), sort_keys=True).encode()
        ).decode(),
        ENVIRONMENT_FILE=encode_environment_variables(environment_variables),
    )


def _get_health_check_network(network_interfaces: Any, health_check_network: str | None) -> str:
    """Resolve the VPC for the health-check firewall from an override or the first instance interface."""
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
    def __init__(  # noqa: C901, PLR0912, PLR0913, PLR0915
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
        root_volume_size_gb: int = 60,
        opts: ResourceOptions | None = None,
        *,
        health_check_network: Input[str] | None = None,
        health_check_network_project: Input[str] | None = None,
        auto_healing_enabled: bool = False,
        secret_environment_variables: dict[str, SecretReference] | None = None,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Run CPU-autoscaled GCP Spot workers with optional automatic healing."""
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:AutoScalingGCPCluster")]))
        super().__init__("tilebox:gcp:AutoScalingCluster", name, opts=opts)

        environment_variables = environment_variables or {}
        secret_environment_variables = secret_environment_variables or {}
        if environment_variables.keys() & secret_environment_variables.keys():
            raise ValueError("Environment and secret mappings must not overlap")
        if "TILEBOX_API_KEY" not in environment_variables and "TILEBOX_API_KEY" not in secret_environment_variables:
            raise ValueError("environment_variables must include TILEBOX_API_KEY")
        if not 0 < cpu_target <= 1 or not 0 <= min_replicas_config <= max_replicas_config:
            raise ValueError("Require 0 < cpu_target <= 1 and 0 <= min_replicas_config <= max_replicas_config")
        if cluster_enabled and min_replicas_config < 1:
            raise ValueError("Enabled clusters require at least one replica")
        if root_volume_size_gb < 1:
            raise ValueError("root_volume_size_gb must be positive")
        for key in secret_environment_variables:
            validate_environment_variable_name(key)

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
            role_config = roles.copy()
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
        self.service_account = service_account
        secret_grants = [
            SecretIamMember(
                f"{name}-secret-{key}",
                secret_id=ref["secret_id"],
                role="roles/secretmanager.secretAccessor",
                member=Output.concat("serviceAccount:", service_account.email),
                opts=ResourceOptions(parent=self),
            )
            for key, ref in secret_environment_variables.items()
        ]

        self.mig: RegionInstanceGroupManager | None = None
        self.autoscaler: RegionAutoscaler | None = None
        if not cluster_enabled:
            self.register_outputs({"instance_group": None, "service_account_email": service_account.email})
            return

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
        health_check_network_output = Output.apply(
            Output.all(
                network_interfaces=network_interfaces,
                health_check_network=health_check_network,
            ),
            lambda values: _get_health_check_network(values["network_interfaces"], values["health_check_network"]),
        )
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

        secrets: dict[str, Input[str]] = {key: ref["secret_id"] for key, ref in secret_environment_variables.items()}
        secret_versions: dict[str, Input[str]] = {
            key: ref.get("rollout_marker", "") for key, ref in secret_environment_variables.items()
        }
        for secret_env_var, secret in used_secrets.items():
            secrets[secret_env_var] = secret.secret.id
            secret_versions[secret_env_var] = secret.latest_version

        cloud_init_config = Output.apply(
            Output.all(
                runner_image=runner_image,
                environment_variables=envs,
                secrets=secrets,
                secret_versions=secret_versions,
            ),
            _get_cloud_init,
        )

        instance_template = InstanceTemplate(
            f"{name}-template",
            project=gcp_project,
            machine_type=machine_type,
            labels=labels,
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
            opts=ResourceOptions(depends_on=[service_account, *secret_grants], parent=self),
        )

        mig = RegionInstanceGroupManager(
            f"{name}-mig",
            project=gcp_project,
            base_instance_name=name,
            region=gcp_region,
            target_size=min_replicas_config,
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
                    "initial_delay_sec": 300,
                }
                if auto_healing_enabled
                else None
            ),
            opts=ResourceOptions(
                depends_on=[instance_template, health_check, health_check_firewall],
                parent=self,
                ignore_changes=["target_size"],
            ),
        )

        self.autoscaler = RegionAutoscaler(
            f"{name}-autoscaler",
            project=gcp_project,
            target=mig.self_link,
            region=gcp_region,
            autoscaling_policy={
                "max_replicas": max_replicas_config,
                "min_replicas": min_replicas_config,
                "cooldown_period": 60,
                "mode": "ON",
                "cpu_utilization": {
                    "target": cpu_target,
                },
            },
            opts=ResourceOptions(depends_on=[mig], parent=self),
        )

        self.mig = mig
        self.register_outputs({"instance_group": mig.instance_group, "service_account_email": service_account.email})
