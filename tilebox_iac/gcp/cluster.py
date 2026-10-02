import re
from collections.abc import Mapping

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_gcp.projects import Service

from tilebox_iac.gcp.network import Network
from tilebox_iac.gcp.runner import AutoScalingCluster
from tilebox_iac.gcp.secrets import Secret
from tilebox_iac.gcp.storage import BlobStorage
from tilebox_iac.release_runner import RUNNER_IMAGE, validate_cluster_environment_variables


class Cluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        project: str,
        tilebox_api_key: Input[str],
        *,
        region: str = "europe-west1",
        machine_type: str = "n2-standard-2",
        cpu_target: float = 0.2,
        min_replicas: int = 1,
        max_replicas: int = 10,
        enabled: bool = True,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 60,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        secret_environment_variables: Mapping[str, Input[str]] | None = None,
        cache: bool | BlobStorage = False,
        cache_expiration_days: int | None = None,
        labels: dict[str, str] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create a GCP runner fleet with networking, identity, APIs, and Secret Manager secrets."""
        if re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", name) is None:
            raise ValueError("name must be a 6-30 character GCP service-account name")
        environment_variables = environment_variables or {}
        secret_environment_variables = secret_environment_variables or {}
        if not isinstance(cache, (bool, BlobStorage)):
            raise TypeError("cache must be a bool or a GCP BlobStorage component")
        if cache_expiration_days is not None and cache is not True:
            raise ValueError("cache_expiration_days applies only when cache=True; configure reused storage directly")
        if isinstance(cache, BlobStorage) and cache.public_read:
            raise ValueError("Cache storage must be private")
        validate_cluster_environment_variables(
            environment_variables, secret_environment_variables, cache_enabled=cache is not False
        )
        super().__init__("tilebox:gcp:Cluster", name, opts=opts)
        services = [
            Service(
                f"{name}-{service}",
                project=project,
                service=f"{service}.googleapis.com",
                disable_on_destroy=False,
                opts=ResourceOptions(parent=self),
            )
            for service in (
                "cloudresourcemanager",
                "compute",
                "iam",
                "monitoring",
                "secretmanager",
                *(("storage",) if cache is True else ()),
            )
        ]
        child = ResourceOptions(parent=self, depends_on=services)
        self.network = Network(name, region, gcp_project=project, opts=child)
        self.api_key = Secret(f"{name}-tilebox-api-key", tilebox_api_key, gcp_project=project, opts=child)
        secrets = {
            key: Secret(f"{name}-secret-{key}", value, gcp_project=project, opts=child)
            for key, value in sorted(secret_environment_variables.items())
        }
        self.cache = cache if isinstance(cache, BlobStorage) else None
        if cache is True:
            self.cache = BlobStorage(
                f"{name}-cache",
                location=region,
                project=project,
                expiration_days=cache_expiration_days,
                expiration_prefix="jobs/" if cache_expiration_days is not None else "",
                opts=child,
            )
        self.cache_uri = Output.concat("gs://", self.cache.bucket_name, "/jobs") if self.cache is not None else None
        cache_environment = {"TILEBOX_WORKER_CACHE": self.cache_uri} if self.cache_uri is not None else {}
        self.runner = AutoScalingCluster(
            name,
            project,
            region,
            machine_type,
            cpu_target,
            enabled,
            min_replicas,
            max_replicas,
            environment_variables={
                **environment_variables,
                **secrets,
                **cache_environment,
                "TILEBOX_API_KEY": self.api_key,
            },
            roles=(
                {
                    "bucket_roles": [
                        {"bucket_slug": "cache", "bucket": self.cache.bucket, "role": "roles/storage.objectUser"}
                    ]
                }
                if self.cache is not None
                else None
            ),
            network_interfaces=[{"network": self.network.id, "subnetwork": self.network.subnet_id}],
            runner_image=runner_image,
            root_volume_size_gb=root_volume_size_gb,
            labels=labels,
            auto_healing_enabled=True,
            opts=ResourceOptions(parent=self, depends_on=[*services, self.network]),
        )
        self.register_outputs(
            {
                "instance_group": self.runner.mig.instance_group if self.runner.mig is not None else None,
                "network_id": self.network.id,
                "cache_uri": self.cache_uri,
            }
        )
