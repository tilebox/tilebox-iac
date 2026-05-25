from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_azure_native import keyvault


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        resource_group_name: Input[str],
        vault_name: Input[str],
        secret_data: Input[str] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A secret stored in Azure Key Vault."""
        super().__init__("tilebox:azure:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = keyvault.Secret(
            name,
            resource_group_name=resource_group_name,
            vault_name=vault_name,
            secret_name=name,
            properties=keyvault.SecretPropertiesArgs(value=secret_data),
            opts=ResourceOptions(parent=self),
        )

        self.id = self.secret.id
        self.name = self.secret.name
        self.secret_uri = self.secret.properties.apply(lambda properties: properties.secret_uri)
        self.register_outputs(
            {
                "id": self.id,
                "name": self.name,
                "secret_uri": self.secret_uri,
            }
        )
