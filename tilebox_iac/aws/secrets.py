from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_aws.secretsmanager import Secret as _Secret
from pulumi_aws.secretsmanager import SecretVersion


class Secret(ComponentResource):
    def __init__(
        self,
        name: str,
        secret_data: Input[str] | None = None,
        is_secret_data_base64: bool | None = None,
        opts: ResourceOptions | None = None,
        *,
        recovery_window_in_days: int = 7,
    ) -> None:
        """Store a versioned value in AWS Secrets Manager."""
        if recovery_window_in_days != 0 and not 7 <= recovery_window_in_days <= 30:
            raise ValueError("recovery_window_in_days must be 0 or between 7 and 30")
        super().__init__("tilebox:aws:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = _Secret(
            name,
            name=name,
            recovery_window_in_days=recovery_window_in_days,
            opts=ResourceOptions(parent=self),
        )

        secret_kwargs = {}
        if is_secret_data_base64:
            secret_kwargs["secret_binary"] = Output.secret(secret_data)
        else:
            secret_kwargs["secret_string"] = Output.secret(secret_data)

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
