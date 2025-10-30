from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_gcp.secretmanager import Secret as GCPSecret
from pulumi_gcp.secretmanager import SecretVersion


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        secret_data: Input[str] | None = None,
        is_secret_data_base64: bool | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("tilebox:secrets:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = GCPSecret(
            name,
            secret_id=name,
            replication={"auto": {}},
            opts=ResourceOptions(parent=self),
        )
        self.version = SecretVersion(
            f"{name}-v1",
            secret=self.secret.id,
            secret_data=secret_data,
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
