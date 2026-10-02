from collections.abc import Mapping

from pulumi import ComponentResource, Input, InvokeOptions, Output, ResourceOptions
from pulumi_aws import ec2, get_availability_zones

from tilebox_iac.aws.runner import AutoScalingCluster
from tilebox_iac.aws.secrets import Secret
from tilebox_iac.aws.storage import BlobStorage
from tilebox_iac.release_runner import RUNNER_IMAGE, validate_cluster_environment_variables


class Cluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        tilebox_api_key: Input[str],
        *,
        instance_type: str = "m7i.large",
        cpu_target: float = 0.2,
        min_replicas: int = 1,
        max_replicas: int = 10,
        enabled: bool = True,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 60,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        secret_environment_variables: Mapping[str, Input[str]] | None = None,
        secret_recovery_window_days: int = 7,
        cache: bool | BlobStorage = False,
        cache_expiration_days: int | None = None,
        tags: dict[str, str] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create an AWS runner fleet with networking, identity, and Secrets Manager secrets."""
        environment_variables = environment_variables or {}
        secret_environment_variables = secret_environment_variables or {}
        if not isinstance(cache, (bool, BlobStorage)):
            raise TypeError("cache must be a bool or an AWS BlobStorage component")
        if cache_expiration_days is not None and cache is not True:
            raise ValueError("cache_expiration_days applies only when cache=True; configure reused storage directly")
        if isinstance(cache, BlobStorage) and cache.public_read:
            raise ValueError("Cache storage must be private")
        validate_cluster_environment_variables(
            environment_variables, secret_environment_variables, cache_enabled=cache is not False
        )
        super().__init__("tilebox:aws:Cluster", name, opts=opts)
        child = ResourceOptions(parent=self)
        self.vpc = ec2.Vpc(
            name, cidr_block="10.42.0.0/16", enable_dns_support=True, enable_dns_hostnames=True, opts=child
        )
        gateway = ec2.InternetGateway(name, vpc_id=self.vpc.id, opts=child)
        route_table = ec2.RouteTable(
            name,
            vpc_id=self.vpc.id,
            routes=[{"cidr_block": "0.0.0.0/0", "gateway_id": gateway.id}],
            opts=child,
        )
        zones = get_availability_zones(state="available", opts=InvokeOptions(parent=self)).names[:2]
        if len(zones) < 2:
            raise ValueError("The AWS quickstart requires two available zones")
        self.subnets = []
        routes = []
        for index, zone in enumerate(zones):
            subnet = ec2.Subnet(
                f"{name}-{index}",
                vpc_id=self.vpc.id,
                availability_zone=zone,
                cidr_block=f"10.42.{index}.0/24",
                map_public_ip_on_launch=True,
                opts=child,
            )
            self.subnets.append(subnet)
            routes.append(
                ec2.RouteTableAssociation(
                    f"{name}-{index}",
                    subnet_id=subnet.id,
                    route_table_id=route_table.id,
                    opts=child,
                )
            )
        self.security_group = ec2.SecurityGroup(
            name,
            vpc_id=self.vpc.id,
            ingress=[],
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
            opts=child,
        )
        self.api_key = Secret(
            f"{name}-tilebox-api-key",
            tilebox_api_key,
            recovery_window_in_days=secret_recovery_window_days,
            opts=child,
        )
        secrets = {
            key: Secret(
                f"{name}-secret-{key}",
                value,
                recovery_window_in_days=secret_recovery_window_days,
                opts=child,
            )
            for key, value in sorted(secret_environment_variables.items())
        }
        self.cache = cache if isinstance(cache, BlobStorage) else None
        if cache is True:
            self.cache = BlobStorage(
                f"{name}-cache",
                expiration_days=cache_expiration_days,
                expiration_prefix="jobs/" if cache_expiration_days is not None else "",
                opts=child,
            )
        self.cache_uri = Output.concat("s3://", self.cache.bucket_name, "/jobs") if self.cache is not None else None
        cache_environment = {"TILEBOX_WORKER_CACHE": self.cache_uri} if self.cache_uri is not None else {}
        self.runner = AutoScalingCluster(
            name,
            instance_type,
            cpu_target,
            enabled,
            min_replicas,
            max_replicas,
            subnet_ids=[subnet.id for subnet in self.subnets],
            security_group_ids=[self.security_group.id],
            environment_variables={
                **environment_variables,
                **secrets,
                **cache_environment,
                "TILEBOX_API_KEY": self.api_key,
            },
            iam_config=(
                {
                    "bucket_access": [
                        {"bucket_slug": "cache", "bucket_arn": self.cache.bucket_arn, "access_level": "readwrite"}
                    ]
                }
                if self.cache is not None
                else None
            ),
            runner_image=runner_image,
            root_volume_size_gb=root_volume_size_gb,
            tags=tags,
            opts=ResourceOptions(parent=self, depends_on=[*routes, self.security_group]),
        )
        self.register_outputs(
            {
                "autoscaling_group_name": self.runner.asg.name if self.runner.asg is not None else None,
                "vpc_id": self.vpc.id,
                "cache_uri": self.cache_uri,
            }
        )
