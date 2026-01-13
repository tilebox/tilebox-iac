from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_aws.secretsmanager import Secret as _Secret
from pulumi_aws.secretsmanager import SecretVersion


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        secret_data: Input[str] | None = None,
        is_secret_data_base64: bool | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A secret stored in AWS Secrets Manager.

        Args:
            name: Secret name.
            secret_data: The secret value, in plaintext, or a base64-encoded.
            is_secret_data_base64: Whether the secret data is base64-encoded.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:aws:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = _Secret(
            name,
            name=name,
            opts=ResourceOptions(parent=self),
        )

        secret_kwargs = {}
        if is_secret_data_base64:
            secret_kwargs["secret_binary"] = secret_data
        else:
            secret_kwargs["secret_string"] = secret_data

        self.version = SecretVersion(
            f"{name}-v1",
            secret_id=self.secret.id,
            **secret_kwargs,
            opts=ResourceOptions(depends_on=[self.secret], parent=self),
        )

        self.id = self.secret.id
        self.arn = self.secret.arn
        self.secret_arn = self.secret.arn
        self.name = self.secret.name
        self.latest_version = self.version.version_id
        self.register_outputs(
            {
                "id": self.id,
                "arn": self.arn,
                "name": self.name,
                "latest_version": self.latest_version,
            }
        )
