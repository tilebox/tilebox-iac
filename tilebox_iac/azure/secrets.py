from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure import keyvault


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        vault_id: Input[str],
        secret_data: Input[str],
        opts: ResourceOptions | None = None,
    ) -> None:
        """Store a secret in an existing RBAC-enabled Key Vault for the runner to fetch at startup."""
        super().__init__("tilebox:azure:Secret", name, opts=opts)
        self.resource_name = name
        self.secret = keyvault.Secret(
            name,
            name=name,
            key_vault_id=vault_id,
            value=Output.secret(secret_data),
            opts=ResourceOptions(parent=self, depends_on=opts.depends_on if opts is not None else None),
        )
        self.url = self.secret.id
        self.scope = Output.concat(vault_id, "/secrets/", self.secret.name)
        self.register_outputs({"url": self.url, "scope": self.scope})
