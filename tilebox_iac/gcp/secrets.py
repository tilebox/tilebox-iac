from pulumi import Alias, ComponentResource, Input, Output, ResourceOptions
from pulumi_gcp.secretmanager import Secret as GCPSecret
from pulumi_gcp.secretmanager import SecretVersion


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        secret_data: Input[str] | None = None,
        is_secret_data_base64: bool | None = None,
        opts: ResourceOptions | None = None,
        *,
        gcp_project: Input[str] | None = None,
    ) -> None:
        """Store a versioned value in GCP Secret Manager."""
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:secrets:Secret")]))
        super().__init__("tilebox:gcp:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = GCPSecret(
            name,
            secret_id=name,
            project=gcp_project,
            replication={"auto": {}},
            opts=ResourceOptions(parent=self),
        )
        self.version = SecretVersion(
            f"{name}-v1",
            secret=self.secret.id,
            secret_data=Output.secret(secret_data) if secret_data is not None else None,
            is_secret_data_base64=is_secret_data_base64,
            opts=ResourceOptions(depends_on=[self.secret], parent=self),
        )

        self.id = self.secret.secret_id
        self.name = self.secret.name
        self.latest_version = self.version.name
        self.register_outputs(
            {
                "id": self.id,
                "name": self.name,
                "latest_version": self.version.name,
            }
        )
