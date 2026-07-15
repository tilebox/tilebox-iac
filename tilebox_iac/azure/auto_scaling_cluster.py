import base64
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import compute, monitor

from tilebox_iac.azure.identity import ManagedIdentity, ManagedIdentityConfigDict
from tilebox_iac.azure.secrets import Secret
from tilebox_iac.release_runner import RUNNER_IMAGE

env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=True)
template = env.get_template("cloud-init.yaml")


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]
    client_id: str = kwargs["client_id"]

    return template.render(
        CONTAINER_IMAGE=RUNNER_IMAGE,
        SECRETS=secrets,
        ENVIRONMENT_VARS=environment_variables,
        CLIENT_ID=client_id,
    )


class AutoScalingCluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        vm_size: str,
        cpu_target: float,
        cluster_enabled: bool,
        min_replicas_config: int,
        max_replicas_config: int,
        subnet_id: Input[str],
        admin_ssh_public_key: Input[str],
        admin_username: str = "cloudservice",
        use_spot: bool = True,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        identity_config: ManagedIdentityConfigDict | None = None,
        source_image_reference: compute.ImageReferenceArgs | None = None,
        os_disk_size_gb: int = 30,
        opts: ResourceOptions | None = None,
    ) -> None:
        """An auto-scaling cluster of Azure VMSS instances running a Docker container."""
        super().__init__("tilebox:azure:AutoScalingCluster", name, opts=opts)

        used_secrets: dict[str, Secret] = {}
        envs: dict[str, Input[str]] = {}
        if environment_variables is not None:
            for key in sorted(environment_variables):
                value = environment_variables[key]
                if isinstance(value, Secret):
                    used_secrets[key] = value
                else:
                    envs[key] = value

        managed_identity = ManagedIdentity.from_config(
            name,
            resource_group_name,
            location,
            identity_config,
            opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self),
        )

        secrets: dict[str, Input[str]] = {}
        for secret_env_var, secret in used_secrets.items():
            secrets[secret_env_var] = secret.secret_uri

        cloud_init_config = Output.all(
            environment_variables=envs,
            secrets=secrets,
            client_id=managed_identity.client_id,
        ).apply(_get_cloud_init)
        custom_data = cloud_init_config.apply(lambda c: base64.b64encode(c.encode()).decode())

        if source_image_reference is None:
            source_image_reference = compute.ImageReferenceArgs(
                publisher="Canonical",
                offer="0001-com-ubuntu-server-jammy",
                sku="22_04-lts-gen2",
                version="latest",
            )

        capacity = min_replicas_config if cluster_enabled else 0
        max_capacity = max_replicas_config if cluster_enabled else 0
        ignore_changes = ["sku.capacity"] if cluster_enabled else []

        self.vmss = compute.VirtualMachineScaleSet(
            f"{name}-vmss",
            resource_group_name=resource_group_name,
            vm_scale_set_name=f"{name}-vmss",
            location=location,
            sku={"name": vm_size, "tier": "Standard", "capacity": capacity},
            overprovision=False,
            upgrade_policy=compute.UpgradePolicyArgs(
                mode=compute.UpgradeMode.ROLLING,
                rolling_upgrade_policy=compute.RollingUpgradePolicyArgs(
                    # New VMs rerun cloud-init; quota fallback does not.
                    max_surge=True,
                ),
            ),
            identity=compute.VirtualMachineScaleSetIdentityArgs(
                type=compute.ResourceIdentityType.USER_ASSIGNED,
                user_assigned_identities=[managed_identity.id],
            ),
            virtual_machine_profile=compute.VirtualMachineScaleSetVMProfileArgs(
                priority="Spot" if use_spot else None,
                eviction_policy="Delete" if use_spot else None,
                billing_profile=compute.BillingProfileArgs(max_price=-1) if use_spot else None,
                extension_profile=compute.VirtualMachineScaleSetExtensionProfileArgs(
                    extensions=[
                        compute.VirtualMachineScaleSetExtensionArgs(
                            name="runner-health",
                            publisher="Microsoft.ManagedServices",
                            type="ApplicationHealthLinux",
                            type_handler_version="2.0",
                            auto_upgrade_minor_version=True,
                            settings={
                                "protocol": "http",
                                "port": 8080,
                                "requestPath": "/health",
                                "gracePeriod": 900,
                            },
                        )
                    ]
                ),
                storage_profile=compute.VirtualMachineScaleSetStorageProfileArgs(
                    image_reference=source_image_reference,
                    os_disk=compute.VirtualMachineScaleSetOSDiskArgs(
                        create_option="FromImage",
                        caching=compute.CachingTypes.READ_WRITE,
                        managed_disk=compute.VirtualMachineScaleSetManagedDiskParametersArgs(
                            storage_account_type="Standard_LRS"
                        ),
                        disk_size_gb=os_disk_size_gb,
                    ),
                ),
                os_profile=compute.VirtualMachineScaleSetOSProfileArgs(
                    computer_name_prefix=name[:9],
                    admin_username=admin_username,
                    custom_data=custom_data,
                    linux_configuration=compute.LinuxConfigurationArgs(
                        disable_password_authentication=True,
                        ssh=compute.SshConfigurationArgs(
                            public_keys=[
                                compute.SshPublicKeyArgs(
                                    path=f"/home/{admin_username}/.ssh/authorized_keys",
                                    key_data=admin_ssh_public_key,
                                )
                            ]
                        ),
                    ),
                ),
                network_profile=compute.VirtualMachineScaleSetNetworkProfileArgs(
                    network_interface_configurations=[
                        compute.VirtualMachineScaleSetNetworkConfigurationArgs(
                            name=f"{name}-nic",
                            primary=True,
                            ip_configurations=[
                                compute.VirtualMachineScaleSetIPConfigurationArgs(
                                    name=f"{name}-ipconfig",
                                    primary=True,
                                    subnet=compute.ApiEntityReferenceArgs(id=subnet_id),
                                )
                            ],
                        )
                    ]
                ),
            ),
            opts=ResourceOptions(depends_on=[managed_identity], parent=self, ignore_changes=ignore_changes),
        )

        if cluster_enabled:
            self.autoscale_setting = monitor.AutoscaleSetting(
                f"{name}-autoscale",
                resource_group_name=resource_group_name,
                autoscale_setting_name=f"{name}-autoscale",
                location=location,
                enabled=True,
                target_resource_uri=self.vmss.id,
                profiles=[
                    monitor.AutoscaleProfileArgs(
                        name="cpu-autoscale",
                        capacity=monitor.ScaleCapacityArgs(
                            minimum=str(min_replicas_config),
                            maximum=str(max_capacity),
                            default=str(capacity),
                        ),
                        rules=[
                            monitor.ScaleRuleArgs(
                                metric_trigger=monitor.MetricTriggerArgs(
                                    metric_name="Percentage CPU",
                                    metric_namespace="microsoft.compute/virtualmachinescalesets",
                                    metric_resource_uri=self.vmss.id,
                                    time_grain="PT1M",
                                    statistic=monitor.MetricStatisticType.AVERAGE,
                                    time_window="PT5M",
                                    time_aggregation=monitor.TimeAggregationType.AVERAGE,
                                    operator=monitor.ComparisonOperationType.GREATER_THAN,
                                    threshold=cpu_target * 100,
                                ),
                                scale_action=monitor.ScaleActionArgs(
                                    direction=monitor.ScaleDirection.INCREASE,
                                    type=monitor.ScaleType.CHANGE_COUNT,
                                    value="1",
                                    cooldown="PT1M",
                                ),
                            ),
                            monitor.ScaleRuleArgs(
                                metric_trigger=monitor.MetricTriggerArgs(
                                    metric_name="Percentage CPU",
                                    metric_namespace="microsoft.compute/virtualmachinescalesets",
                                    metric_resource_uri=self.vmss.id,
                                    time_grain="PT1M",
                                    statistic=monitor.MetricStatisticType.AVERAGE,
                                    time_window="PT5M",
                                    time_aggregation=monitor.TimeAggregationType.AVERAGE,
                                    operator=monitor.ComparisonOperationType.LESS_THAN,
                                    threshold=max(cpu_target * 50, 1),
                                ),
                                scale_action=monitor.ScaleActionArgs(
                                    direction=monitor.ScaleDirection.DECREASE,
                                    type=monitor.ScaleType.CHANGE_COUNT,
                                    value="1",
                                    cooldown="PT1M",
                                ),
                            ),
                        ],
                    )
                ],
                opts=ResourceOptions(depends_on=[self.vmss], parent=self),
            )

        self.register_outputs({"vmss_id": self.vmss.id, "identity_id": managed_identity.id})
