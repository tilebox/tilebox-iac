import base64
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

import pulumi_aws as aws
from jinja2 import Environment, FileSystemLoader
from pulumi import ComponentResource, Input, InvokeOptions, InvokeOutputOptions, Output, ResourceOptions
from pulumi_aws import autoscaling as aws_autoscaling
from pulumi_aws import ec2 as aws_ec2
from pulumi_aws import iam as aws_iam
from typing_extensions import NotRequired

from tilebox_iac.aws.iam_role import IAMRole, IAMRoleConfigDict
from tilebox_iac.aws.secrets import Secret
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
    secret_arn: Input[str]
    rollout_marker: NotRequired[Input[str]]


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the AWS VMs."""
    runner_image = validate_runner_image(kwargs["runner_image"])
    registry_hostname = runner_image.split("/", maxsplit=1)[0]
    registry_parts = registry_hostname.split(".")
    ecr_region = registry_parts[3] if len(registry_parts) > 3 and registry_parts[1:3] == ["dkr", "ecr"] else None
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]
    secret_versions: dict[str, str] = kwargs["secret_versions"]
    for secret in secrets.values():
        if (
            re.fullmatch(r"arn:[a-z0-9-]+:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+", secret)
            is None
        ):
            raise ValueError("secret_arn must be a Secrets Manager ARN")

    return template.render(
        CONTAINER_IMAGE=runner_image,
        ECR_REGION=ecr_region,
        REGISTRY_HOSTNAME=registry_hostname,
        SECRETS=secrets,
        SECRET_VERSIONS=base64.b64encode(json.dumps(secret_versions, sort_keys=True).encode()).decode(),
        ENVIRONMENT_FILE=encode_environment_variables(environment_variables),
    )


class AutoScalingCluster(ComponentResource):
    def __init__(  # noqa: C901, PLR0912, PLR0913, PLR0915
        self,
        name: str,
        instance_type: str,
        cpu_target: float,
        cluster_enabled: bool,
        min_replicas_config: int,
        max_replicas_config: int,
        subnet_ids: Input[Sequence[Input[str]]],
        security_group_ids: Input[Sequence[Input[str]]] | None = None,
        ami_id: Input[str] | None = None,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        iam_config: IAMRoleConfigDict | None = None,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 60,
        opts: ResourceOptions | None = None,
        *,
        secret_environment_variables: dict[str, SecretReference] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Run CPU-autoscaled AWS Spot workers in existing subnets."""
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
        super().__init__("tilebox:aws:AutoScalingCluster", name, opts=opts)

        used_secrets: dict[str, Secret] = {}
        envs: dict[str, Input[str]] = {}

        if environment_variables is not None:
            # Sort keys for deterministic cloud-init output (avoids spurious Pulumi diffs)
            for key in sorted(environment_variables):
                validate_environment_variable_name(key)
                value = environment_variables[key]
                if isinstance(value, Secret):
                    used_secrets[key] = value
                else:
                    envs[key] = value

        # Copy to avoid mutating caller's config (could cause side effects if reused)
        iam_config_copy: IAMRoleConfigDict = iam_config.copy() if iam_config else {}

        secrets_access = list(iam_config_copy.get("secrets_access", []))
        secrets_access.extend(
            {"secret_slug": secret.resource_name, "secret_arn": secret.arn} for secret in used_secrets.values()
        )
        secrets_access.extend(
            {"secret_slug": key, "secret_arn": ref["secret_arn"]} for key, ref in secret_environment_variables.items()
        )
        if secrets_access:
            iam_config_copy["secrets_access"] = secrets_access  # type: ignore[typeddict-item]

        iam_role = IAMRole.from_config(
            name,
            iam_config_copy,
            assume_service="ec2.amazonaws.com",
            opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self),
        )
        self.iam_role = iam_role

        self.asg: aws_autoscaling.Group | None = None
        self.scaling_policy: aws_autoscaling.Policy | None = None
        if not cluster_enabled:
            self.register_outputs({"asg_name": None, "asg_arn": None})
            return

        invoke_opts = InvokeOutputOptions(parent=self)
        asg_arn = Output.apply(
            Output.all(
                partition=aws.get_partition_output(opts=invoke_opts).partition,
                region=aws.get_region_output(opts=invoke_opts).region,
                account_id=aws.get_caller_identity_output(opts=invoke_opts).account_id,
            ),
            lambda values: (
                f"arn:{values['partition']}:autoscaling:{values['region']}:{values['account_id']}:"
                f"autoScalingGroup:*:autoScalingGroupName/{name}-*"
            ),
        )
        health_policy = aws_iam.RolePolicy(
            f"{name}-set-instance-health",
            role=iam_role.role.name,
            policy=Output.apply(
                asg_arn,
                lambda arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "autoscaling:SetInstanceHealth",
                                "Resource": arn,
                            }
                        ],
                    }
                ),
            ),
            opts=ResourceOptions(parent=self),
        )

        secrets: dict[str, Input[str]] = {key: ref["secret_arn"] for key, ref in secret_environment_variables.items()}
        # Include version IDs so secret value changes trigger Launch Template updates
        secret_versions: dict[str, Input[str]] = {
            key: ref.get("rollout_marker", "") for key, ref in secret_environment_variables.items()
        }
        for secret_env_var, secret in used_secrets.items():
            secrets[secret_env_var] = secret.arn
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

        user_data = Output.apply(cloud_init_config, lambda c: base64.b64encode(c.encode()).decode())

        resolved_ami_id: Input[str]
        if ami_id is not None:
            resolved_ami_id = ami_id
        else:
            ami = aws_ec2.get_ami(
                most_recent=True,
                owners=["amazon"],
                filters=[
                    aws_ec2.GetAmiFilterArgs(name="name", values=["al2023-ami-*-x86_64"]),
                    aws_ec2.GetAmiFilterArgs(name="virtualization-type", values=["hvm"]),
                ],
                opts=InvokeOptions(parent=self),
            )
            resolved_ami_id = ami.id

        launch_template = aws_ec2.LaunchTemplate(
            f"{name}-lt",
            name_prefix=f"{name}-",
            image_id=resolved_ami_id,
            instance_type=instance_type,
            user_data=user_data,
            block_device_mappings=[
                aws_ec2.LaunchTemplateBlockDeviceMappingArgs(
                    device_name="/dev/xvda",
                    ebs=aws_ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                        delete_on_termination="true",
                        encrypted="true",
                        volume_size=root_volume_size_gb,
                        volume_type="gp3",
                    ),
                )
            ],
            vpc_security_group_ids=security_group_ids if security_group_ids is not None else None,
            iam_instance_profile=aws_ec2.LaunchTemplateIamInstanceProfileArgs(
                arn=iam_role.instance_profile_arn,
            ),
            instance_market_options=aws_ec2.LaunchTemplateInstanceMarketOptionsArgs(
                market_type="spot",
                spot_options=aws_ec2.LaunchTemplateInstanceMarketOptionsSpotOptionsArgs(
                    spot_instance_type="one-time",
                ),
            ),
            monitoring=aws_ec2.LaunchTemplateMonitoringArgs(enabled=True),
            # Enforce IMDSv2 for security (cloud-init script already uses IMDSv2 tokens)
            metadata_options=aws_ec2.LaunchTemplateMetadataOptionsArgs(
                http_tokens="required",
                http_endpoint="enabled",
            ),
            tag_specifications=[
                aws_ec2.LaunchTemplateTagSpecificationArgs(
                    resource_type="instance",
                    tags={"Name": f"{name}-instance", **(tags or {})},
                ),
            ],
            opts=ResourceOptions(depends_on=[iam_role, health_policy], parent=self),
        )

        self.asg = aws_autoscaling.Group(
            f"{name}-asg",
            name_prefix=f"{name}-",
            min_size=min_replicas_config,
            max_size=max_replicas_config,
            desired_capacity=min_replicas_config,
            vpc_zone_identifiers=subnet_ids,
            launch_template=aws_autoscaling.GroupLaunchTemplateArgs(
                id=launch_template.id,
                version=Output.apply(launch_template.latest_version, str),
            ),
            health_check_type="EC2",
            health_check_grace_period=300,
            default_instance_warmup=60,
            # Proactively replace Spot instances when AWS signals upcoming interruption
            capacity_rebalance=True,
            # Terminate oldest first to ensure instances pick up latest Launch Template changes
            termination_policies=["OldestInstance", "Default"],
            # Automatically roll instances when Launch Template changes (image/env/user-data updates).
            instance_refresh=aws_autoscaling.GroupInstanceRefreshArgs(
                strategy="Rolling",
                preferences=aws_autoscaling.GroupInstanceRefreshPreferencesArgs(
                    min_healthy_percentage=0,
                    instance_warmup="60",
                ),
            ),
            tags=[
                aws_autoscaling.GroupTagArgs(key=key, value=value, propagate_at_launch=True)
                for key, value in {"Name": f"{name}-instance", **(tags or {})}.items()
            ],
            # Ignore desired_capacity changes to avoid overriding autoscaler decisions on pulumi up
            opts=ResourceOptions(
                depends_on=[launch_template],
                parent=self,
                ignore_changes=["desired_capacity"],
            ),
        )

        self.scaling_policy = aws_autoscaling.Policy(
            f"{name}-cpu-policy",
            autoscaling_group_name=self.asg.name,
            policy_type="TargetTrackingScaling",
            estimated_instance_warmup=60,
            target_tracking_configuration=aws_autoscaling.PolicyTargetTrackingConfigurationArgs(
                predefined_metric_specification=aws_autoscaling.PolicyTargetTrackingConfigurationPredefinedMetricSpecificationArgs(
                    predefined_metric_type="ASGAverageCPUUtilization",
                ),
                target_value=cpu_target * 100,
            ),
            opts=ResourceOptions(depends_on=[self.asg], parent=self),
        )

        self.register_outputs({"asg_name": self.asg.name, "asg_arn": self.asg.arn})
