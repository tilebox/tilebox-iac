import base64
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure import authorization, compute, monitoring

from tilebox_iac.azure._naming import resource_name
from tilebox_iac.azure.secrets import Secret
from tilebox_iac.release_runner import RUNNER_IMAGE, encode_environment_variables, validate_environment_variable_name

template = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=False,  # noqa: S701 - cloud-init YAML, not HTML
    undefined=StrictUndefined,
).get_template("cloud-init.yaml")


class RoleAssignmentConfig(TypedDict):
    scope: Input[str]
    role_definition_name: str


def _validate_registry_id(value: str) -> str:
    if (
        re.fullmatch(
            r"/subscriptions/[0-9a-f-]{36}/resourceGroups/[^/\s]+/providers/Microsoft.ContainerRegistry/registries/[a-z0-9]{5,50}",
            value,
            flags=re.IGNORECASE,
        )
        is None
    ):
        raise ValueError("container_registry_id must be an Azure Container Registry resource ID")
    return value


def _get_cloud_init(values: dict[str, Any]) -> str:
    image = values["runner_image"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]*", image):
        raise ValueError("runner_image must be a container image reference without whitespace or shell characters")
    registry = values.get("container_registry_server")
    if registry is not None:
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.azurecr\.io", registry) is None:
            raise ValueError("container_registry_server must be an Azure public-cloud ACR login hostname")
        if not image.startswith(registry + "/") or not image.removeprefix(registry + "/"):
            raise ValueError("runner_image must belong to container_registry_server")
    rendered = template.render(
        CONTAINER_IMAGE=image,
        CONTAINER_REGISTRY=registry,
        ENVIRONMENT_FILE=encode_environment_variables(values["environment_variables"]),
        SECRET_CONFIG=base64.b64encode(
            json.dumps(
                {
                    "client_id": values["environment_variables"]["AZURE_CLIENT_ID"],
                    "secrets": values["secrets"],
                    **({"registry_server": registry} if registry is not None else {}),
                }
            ).encode()
        ).decode(),
    )
    if len(rendered.encode()) > 65535:
        raise ValueError("Azure custom data must be smaller than 64 KiB")
    return base64.b64encode(rendered.encode()).decode()


class AutoScalingCluster(ComponentResource):
    def __init__(  # noqa: C901, PLR0913
        self,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        subnet_id: Input[str],
        ssh_public_key: Input[str],
        instance_type: Input[str] = "Standard_D8s_v5",
        cpu_target: float = 0.6,
        cluster_enabled: bool = True,
        min_replicas_config: int = 1,
        max_replicas_config: int = 2,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 40,
        blob_container_ids: Mapping[str, Input[str]] | None = None,
        roles: Mapping[str, RoleAssignmentConfig] | None = None,
        spot: bool = False,
        opts: ResourceOptions | None = None,
        *,
        auto_healing_enabled: bool = True,
        container_registry_id: Input[str] | None = None,
        container_registry_server: Input[str] | None = None,
    ) -> None:
        """Run Ubuntu VMs with CPU autoscaling and a user-assigned managed identity."""
        if blob_container_ids is not None and not isinstance(blob_container_ids, Mapping):
            raise ValueError("blob_container_ids must map stable names to container IDs")
        if roles is not None and not isinstance(roles, Mapping):
            raise ValueError("roles must map stable names to role configurations")
        if (container_registry_id is None) != (container_registry_server is None):
            raise ValueError("Supply both container_registry_id and container_registry_server")
        if environment_variables is None or "TILEBOX_API_KEY" not in environment_variables:
            raise ValueError("environment_variables must include TILEBOX_API_KEY")
        for key in environment_variables:
            validate_environment_variable_name(key)
        if "AZURE_CLIENT_ID" in environment_variables:
            raise ValueError("AZURE_CLIENT_ID is set by the cluster's managed identity")
        if not 0 < cpu_target < 1:
            raise ValueError("cpu_target must be between 0 and 1 (exclusive)")
        if not 1 <= min_replicas_config <= max_replicas_config:
            raise ValueError("replicas must satisfy 1 <= min_replicas_config <= max_replicas_config")
        if root_volume_size_gb < 40:
            raise ValueError("root_volume_size_gb must be at least 40")
        super().__init__("tilebox:azure:AutoScalingCluster", name, opts=opts)
        child = ResourceOptions(parent=self)
        self.identity = authorization.UserAssignedIdentity(
            resource_name(name, 17), resource_group_name=resource_group_name, location=location, opts=child
        )
        secrets = {key: value for key, value in environment_variables.items() if isinstance(value, Secret)}
        plain = {key: value for key, value in environment_variables.items() if not isinstance(value, Secret)}
        grants = [
            authorization.Assignment(
                f"{name}-role-{key}",
                principal_id=self.identity.principal_id,
                principal_type="ServicePrincipal",
                scope=role["scope"],
                role_definition_name=role["role_definition_name"],
                opts=child,
            )
            for key, role in (roles or {}).items()
        ]
        grants.extend(
            authorization.Assignment(
                f"{name}-secret-{secret.resource_name}",
                principal_id=self.identity.principal_id,
                principal_type="ServicePrincipal",
                scope=secret.scope,
                role_definition_name="Key Vault Secrets User",
                opts=child,
            )
            for secret in dict.fromkeys(secrets.values())
        )
        grants.extend(
            authorization.Assignment(
                f"{name}-blob-{key}",
                principal_id=self.identity.principal_id,
                principal_type="ServicePrincipal",
                scope=scope,
                role_definition_name="Storage Blob Data Contributor",
                opts=child,
            )
            for key, scope in (blob_container_ids or {}).items()
        )
        if container_registry_id is not None:
            grants.append(
                authorization.Assignment(
                    f"{name}-registry-pull",
                    principal_id=self.identity.principal_id,
                    principal_type="ServicePrincipal",
                    scope=Output.apply(Output.from_input(container_registry_id), _validate_registry_id),
                    role_definition_name="AcrPull",
                    opts=child,
                )
            )
        self.scale_set: compute.LinuxVirtualMachineScaleSet | None = None
        self.autoscaler: monitoring.AutoscaleSetting | None = None
        if not cluster_enabled:
            self.register_outputs({"scale_set_id": None, "client_id": self.identity.client_id})
            return

        custom_data = Output.apply(
            Output.all(
                runner_image=runner_image,
                container_registry_server=container_registry_server,
                environment_variables={**plain, "AZURE_CLIENT_ID": self.identity.client_id},
                secrets={key: secret.url for key, secret in secrets.items()},
            ),
            _get_cloud_init,
        )
        self.scale_set = compute.LinuxVirtualMachineScaleSet(
            # The generated name also serves as the Linux host prefix, limited to 58 characters.
            resource_name(name, 50),
            resource_group_name=resource_group_name,
            location=location,
            sku=instance_type,
            instances=min_replicas_config,
            admin_username="tilebox",
            admin_ssh_keys=[{"username": "tilebox", "public_key": ssh_public_key}],
            disable_password_authentication=True,
            identity={"type": "UserAssigned", "identity_ids": [self.identity.id]},
            network_interfaces=[
                {
                    "name": "runner",
                    "primary": True,
                    "ip_configurations": [{"name": "runner", "primary": True, "subnet_id": subnet_id}],
                }
            ],
            source_image_reference={
                "publisher": "Canonical",
                "offer": "ubuntu-24_04-lts",
                "sku": "server",
                "version": "latest",
            },
            os_disk={
                "caching": "ReadWrite",
                "storage_account_type": "Premium_LRS",
                "disk_size_gb": root_volume_size_gb,
            },
            custom_data=cast(Output[str], Output.secret(custom_data)),
            priority="Spot" if spot else "Regular",
            eviction_policy="Delete" if spot else None,
            max_bid_price=-1 if spot else None,
            overprovision=False,
            # The Azure provider updates and reimages instances when custom data changes.
            upgrade_mode="Manual",
            extensions=[
                {
                    "name": "runner-health",
                    "publisher": "Microsoft.ManagedServices",
                    "type": "ApplicationHealthLinux",
                    "type_handler_version": "1.0",
                    "auto_upgrade_minor_version": True,
                    "settings": json.dumps(
                        {
                            "protocol": "http",
                            "port": 8080,
                            "requestPath": "/health",
                            "intervalInSeconds": 30,
                            "numberOfProbes": 3,
                        }
                    ),
                }
            ],
            automatic_instance_repair={
                "enabled": auto_healing_enabled,
                "action": "Replace",
                "grace_period": "PT30M",
            },
            opts=ResourceOptions(parent=self, depends_on=grants, ignore_changes=["instances"]),
        )
        self.autoscaler = monitoring.AutoscaleSetting(
            resource_name(name, 247),
            resource_group_name=resource_group_name,
            location=location,
            target_resource_id=self.scale_set.id,
            profiles=[
                {
                    "name": "cpu",
                    "capacity": {
                        "default": min_replicas_config,
                        "minimum": min_replicas_config,
                        "maximum": max_replicas_config,
                    },
                    "rules": [
                        {
                            "metric_trigger": {
                                "metric_name": "Percentage CPU",
                                "metric_resource_id": self.scale_set.id,
                                "time_grain": "PT1M",
                                "statistic": "Average",
                                "time_window": "PT5M",
                                "time_aggregation": "Average",
                                "operator": operator,
                                "threshold": threshold,
                            },
                            "scale_action": {
                                "direction": direction,
                                "type": "ChangeCount",
                                "value": 1,
                                "cooldown": "PT5M",
                            },
                        }
                        for operator, threshold, direction in [
                            ("GreaterThan", cpu_target * 100, "Increase"),
                            ("LessThan", cpu_target * 50, "Decrease"),
                        ]
                    ],
                }
            ],
            opts=child,
        )
        self.register_outputs({"scale_set_id": self.scale_set.id, "client_id": self.identity.client_id})
