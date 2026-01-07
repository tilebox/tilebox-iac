from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_aws.secretsmanager import Secret as AWSSecretResource
from pulumi_aws.secretsmanager import SecretVersion as AWSSecretVersion


class AWSSecret(ComponentResource):
    def __init__(
        self,
        name: str,
        secret_string: Input[str] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A secret stored in AWS Secrets Manager.

        Args:
            name: Secret name.
            secret_string: The secret value.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:aws:Secret", name, opts=opts)

        self.resource_name = name
        self.secret = AWSSecretResource(
            name,
            name=name,
            opts=ResourceOptions(parent=self),
        )
        self.version = AWSSecretVersion(
            f"{name}-v1",
            secret_id=self.secret.id,
            secret_string=secret_string,
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
