import base64
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

from jinja2 import Environment, FileSystemLoader
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_aws import autoscaling as aws_autoscaling
from pulumi_aws import ec2 as aws_ec2
from typing_extensions import NotRequired

from tilebox_iac.aws.iam_role import IAMRole, IAMRoleConfigDict
from tilebox_iac.aws.secrets import AWSSecret

env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=True)
template = env.get_template("cloud-init.yaml")


def _get_cloud_init(kwargs: dict[str, Any]) -> str:
    """Render the cloud-init config for the AWS VMs."""
    image: str = kwargs["image"]
    tag: str = kwargs["tag"] or "latest"  # Default empty string to "latest"
    environment_variables: dict[str, str] = kwargs["environment_variables"]
    secrets: dict[str, str] = kwargs["secrets"]
    secret_versions: dict[str, str] = kwargs["secret_versions"]

    return template.render(
        CONTAINER_IMAGE=f"{image}:{tag}",
        REGISTRY_HOSTNAME=image.split("/")[0],
        SECRETS=secrets,
        SECRET_VERSIONS=secret_versions,
        ENVIRONMENT_VARS=environment_variables,
    )


class ContainerConfig(TypedDict):
    image: Input[str]
    tag: NotRequired[Input[str]]


class AutoScalingAWSCluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        container: ContainerConfig,
        instance_type: str,
        cpu_target: float,
        cluster_enabled: bool,
        min_replicas_config: int,
        max_replicas_config: int,
        subnet_ids: Input[Sequence[Input[str]]],
        security_group_ids: Input[Sequence[Input[str]]] | None = None,
        ami_id: Input[str] | None = None,
        environment_variables: dict[str, Input[str] | AWSSecret] | None = None,
        iam_config: IAMRoleConfigDict | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """An auto-scaling cluster of AWS Spot instances running a Docker container.

        Args:
            name: Name of the cluster.
            container: Container image to run (ECR image URL).
            instance_type: EC2 instance type to use.
            cpu_target: CPU target for autoscaling (0.0 to 1.0).
            cluster_enabled: Whether the cluster is enabled.
            min_replicas_config: Minimum number of replicas.
            max_replicas_config: Maximum number of replicas.
            subnet_ids: List of subnet IDs to deploy instances in.
            security_group_ids: Optional list of security group IDs for instances. If omitted, the VPC's
                default security group is used, which must allow outbound internet access for yum/docker pulls.
            ami_id: AMI ID to use. Defaults to latest Amazon Linux 2023.
            environment_variables: Environment variables to pass to the container.
            iam_config: IAM role configuration for bucket and secret access.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:aws:AutoScalingCluster", name, opts=opts)

        used_secrets: dict[str, AWSSecret] = {}
        envs: dict[str, Input[str]] = {}

        if environment_variables is not None:
            # Sort keys for deterministic cloud-init output (avoids spurious Pulumi diffs)
            for key in sorted(environment_variables):
                value = environment_variables[key]
                if isinstance(value, AWSSecret):
                    used_secrets[key] = value
                else:
                    envs[key] = value

        # Copy to avoid mutating caller's config (could cause side effects if reused)
        iam_config_copy: IAMRoleConfigDict = dict(iam_config) if iam_config else {}  # type: ignore[assignment]

        # ECR read access is required for cloud-init to docker pull the container image
        managed_policies = list(iam_config_copy.get("managed_policies", []))
        ecr_policy = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
        if ecr_policy not in managed_policies:
            managed_policies.append(ecr_policy)
        iam_config_copy["managed_policies"] = managed_policies  # type: ignore[typeddict-item]

        secrets_access = list(iam_config_copy.get("secrets_access", []))
        secrets_access.extend(
            {"secret_slug": secret.resource_name, "secret_arn": secret.arn} for secret in used_secrets.values()
        )
        if secrets_access:
            iam_config_copy["secrets_access"] = secrets_access  # type: ignore[typeddict-item]

        iam_role = IAMRole.from_config(
            name,
            iam_config_copy,
            assume_service="ec2.amazonaws.com",
            opts=ResourceOptions(depends_on=[*list(used_secrets.values())], parent=self),
        )

        secrets: dict[str, Input[str]] = {}
        # Include version IDs so secret value changes trigger Launch Template updates
        secret_versions: dict[str, Input[str]] = {}
        for secret_env_var, secret in used_secrets.items():
            secrets[secret_env_var] = secret.arn
            secret_versions[secret_env_var] = secret.latest_version

        cloud_init_config = Output.all(
            image=container["image"],
            tag=container.get("tag", "latest"),
            environment_variables=envs,
            secrets=secrets,
            secret_versions=secret_versions,
        ).apply(_get_cloud_init)

        user_data = cloud_init_config.apply(lambda c: base64.b64encode(c.encode()).decode())

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
            )
            resolved_ami_id = ami.id

        launch_template = aws_ec2.LaunchTemplate(
            f"{name}-lt",
            name_prefix=f"{name}-",
            image_id=resolved_ami_id,
            instance_type=instance_type,
            user_data=user_data,
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
                    tags={"Name": f"{name}-instance"},
                ),
            ],
            opts=ResourceOptions(depends_on=[iam_role], parent=self),
        )

        if cluster_enabled:
            min_size = min_replicas_config
            max_size = max_replicas_config
            desired_capacity = min_replicas_config
        else:
            min_size = 0
            max_size = 0
            desired_capacity = 0

        self.asg = aws_autoscaling.Group(
            f"{name}-asg",
            name_prefix=f"{name}-",
            min_size=min_size,
            max_size=max_size,
            desired_capacity=desired_capacity,
            vpc_zone_identifiers=subnet_ids,
            launch_template=aws_autoscaling.GroupLaunchTemplateArgs(
                id=launch_template.id,
                version="$Latest",
            ),
            health_check_type="EC2",
            health_check_grace_period=300,
            default_instance_warmup=60,
            # Proactively replace Spot instances when AWS signals upcoming interruption
            capacity_rebalance=True,
            # Terminate oldest first to ensure instances pick up latest Launch Template changes
            termination_policies=["OldestInstance", "Default"],
            tags=[
                aws_autoscaling.GroupTagArgs(
                    key="Name",
                    value=f"{name}-instance",
                    propagate_at_launch=True,
                ),
            ],
            # Ignore desired_capacity changes to avoid overriding autoscaler decisions on pulumi up
            opts=ResourceOptions(depends_on=[launch_template], parent=self, ignore_changes=["desired_capacity"]),
        )

        if cluster_enabled:
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
