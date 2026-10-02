from collections.abc import Mapping

from pulumi import ComponentResource, Input, InvokeOptions, Output, ResourceOptions
from pulumi_azure import authorization, core, keyvault

from tilebox_iac.azure._naming import resource_name
from tilebox_iac.azure.network import Network
from tilebox_iac.azure.runner import AutoScalingCluster, RoleAssignmentConfig
from tilebox_iac.azure.secrets import Secret
from tilebox_iac.azure.storage import BlobStorage
from tilebox_iac.release_runner import RUNNER_IMAGE, validate_cluster_environment_variables


class Cluster(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        tilebox_api_key: Input[str],
        *,
        ssh_public_key: Input[str],
        location: Input[str] = "westeurope",
        instance_type: Input[str] = "Standard_D8s_v5",
        cpu_target: float = 0.6,
        min_replicas: int = 1,
        max_replicas: int = 2,
        enabled: bool = True,
        runner_image: Input[str] = RUNNER_IMAGE,
        root_volume_size_gb: int = 40,
        environment_variables: dict[str, Input[str] | Secret] | None = None,
        secret_environment_variables: Mapping[str, Input[str]] | None = None,
        cache: bool | BlobStorage = False,
        cache_expiration_days: int | None = None,
        blob_container_ids: Mapping[str, Input[str]] | None = None,
        roles: Mapping[str, RoleAssignmentConfig] | None = None,
        spot: bool = False,
        container_registry_id: Input[str] | None = None,
        container_registry_server: Input[str] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create an Azure resource group, network, Key Vault secrets, identity, and runner fleet."""
        environment_variables = environment_variables or {}
        secret_environment_variables = secret_environment_variables or {}
        if not isinstance(cache, (bool, BlobStorage)):
            raise TypeError("cache must be a bool or an Azure BlobStorage component")
        if cache_expiration_days is not None and cache is not True:
            raise ValueError("cache_expiration_days applies only when cache=True; configure reused storage directly")
        if isinstance(cache, BlobStorage) and cache.public_read:
            raise ValueError("Cache storage must be private")
        if cache is not False and blob_container_ids and "local-cache" in blob_container_ids:
            raise ValueError("The local-cache key in blob_container_ids is reserved when a cache is configured")
        validate_cluster_environment_variables(
            environment_variables, secret_environment_variables, cache_enabled=cache is not False
        )
        if "AZURE_CLIENT_ID" in environment_variables or "AZURE_CLIENT_ID" in secret_environment_variables:
            raise ValueError("AZURE_CLIENT_ID is set by the cluster's managed identity")
        if len({key.lower() for key in secret_environment_variables}) != len(secret_environment_variables):
            raise ValueError("Key Vault secret environment variable names must not differ only by case")
        super().__init__("tilebox:azure:Cluster", name, opts=opts)
        child = ResourceOptions(parent=self)
        current = core.get_client_config(opts=InvokeOptions(parent=self))
        self.resource_group = core.ResourceGroup(resource_name(name, 82), location=location, opts=child)
        self.network = Network(name, self.resource_group.name, location, opts=child)
        self.vault = keyvault.KeyVault(
            resource_name(f"{name}-vault", 17),
            resource_group_name=self.resource_group.name,
            location=location,
            tenant_id=current.tenant_id,
            sku_name="standard",
            rbac_authorization_enabled=True,
            opts=child,
        )
        writer = authorization.Assignment(
            f"{name}-secret-writer",
            scope=self.vault.id,
            principal_id=current.object_id,
            role_definition_name="Key Vault Secrets Officer",
            opts=child,
        )
        self.api_key = Secret(
            resource_name(f"{name}-tilebox-api-key", 127),
            vault_id=self.vault.id,
            secret_data=tilebox_api_key,
            opts=ResourceOptions(parent=self, depends_on=[writer]),
        )
        secrets = {
            key: Secret(
                resource_name(f"{name}-secret-{key.replace('_', '-')}", 127),
                vault_id=self.vault.id,
                secret_data=value,
                opts=ResourceOptions(parent=self, depends_on=[writer]),
            )
            for key, value in sorted(secret_environment_variables.items())
        }
        self.cache = cache if isinstance(cache, BlobStorage) else None
        if cache is True:
            self.cache = BlobStorage(
                f"{name}-cache",
                resource_group_name=self.resource_group.name,
                location=location,
                container_name="worker-cache",
                expiration_days=cache_expiration_days,
                expiration_prefix="jobs/" if cache_expiration_days is not None else "",
                opts=child,
            )
        self.cache_uri = (
            Output.concat("az://", self.cache.account.name, "/", self.cache.container_name, "/jobs")
            if self.cache is not None
            else None
        )
        cache_environment = {"TILEBOX_WORKER_CACHE": self.cache_uri} if self.cache_uri is not None else {}
        containers = dict(blob_container_ids or {})
        if self.cache is not None:
            containers["local-cache"] = self.cache.container_resource_id
        self.runner = AutoScalingCluster(
            name,
            self.resource_group.name,
            location,
            subnet_id=self.network.subnet_id,
            ssh_public_key=ssh_public_key,
            instance_type=instance_type,
            cpu_target=cpu_target,
            cluster_enabled=enabled,
            min_replicas_config=min_replicas,
            max_replicas_config=max_replicas,
            environment_variables={
                **environment_variables,
                **secrets,
                **cache_environment,
                "TILEBOX_API_KEY": self.api_key,
            },
            runner_image=runner_image,
            root_volume_size_gb=root_volume_size_gb,
            blob_container_ids=containers,
            roles=roles,
            spot=spot,
            container_registry_id=container_registry_id,
            container_registry_server=container_registry_server,
            auto_healing_enabled=True,
            opts=ResourceOptions(parent=self, depends_on=[self.network, self.api_key, *secrets.values()]),
        )
        self.register_outputs(
            {
                "resource_group_name": self.resource_group.name,
                "scale_set_id": self.runner.scale_set.id if self.runner.scale_set is not None else None,
                "client_id": self.runner.identity.client_id,
                "cache_uri": self.cache_uri,
            }
        )
