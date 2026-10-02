import json
from collections.abc import Sequence
from typing import TypedDict

from pulumi import ComponentResource, Input, InvokeOutputOptions, Output, ResourceOptions
from pulumi_aws import get_partition_output, get_region_output, iam
from typing_extensions import NotRequired


class BucketAccessDict(TypedDict):
    """Configuration for S3 bucket access."""

    bucket_slug: str
    """Slug for pulumi resource naming."""
    bucket_arn: Input[str]
    """S3 bucket ARN."""
    access_level: str
    """Access level: 'read', 'write', or 'readwrite'."""


class SecretAccessDict(TypedDict):
    """Configuration for Secrets Manager access."""

    secret_slug: str
    """Slug for pulumi resource naming."""
    secret_arn: Input[str]
    """Secrets Manager secret ARN."""


class IAMRoleConfigDict(TypedDict):
    """Configuration for an IAM role."""

    managed_policies: NotRequired[Sequence[str]]
    """AWS managed policy ARNs."""
    bucket_access: NotRequired[Sequence[BucketAccessDict]]
    """S3 bucket access configurations."""
    secrets_access: NotRequired[Sequence[SecretAccessDict]]
    """Secrets Manager access configurations."""
    existing_role_name: NotRequired[str]
    existing_instance_profile_name: NotRequired[str]
    secret_kms_key_arns: NotRequired[Sequence[Input[str]]]


class IAMRole(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        assume_service: str = "ec2.amazonaws.com",
        managed_policies: Sequence[str] | None = None,
        bucket_access: Sequence[BucketAccessDict] | None = None,
        secrets_access: Sequence[SecretAccessDict] | None = None,
        opts: ResourceOptions | None = None,
        *,
        existing_role_name: str | None = None,
        existing_instance_profile_name: str | None = None,
        secret_kms_key_arns: Sequence[Input[str]] = (),
    ) -> None:
        """Create or reuse an instance role and profile, and assign runner permissions."""
        if (existing_role_name is None) != (existing_instance_profile_name is None):
            raise ValueError("Supply both existing_role_name and existing_instance_profile_name")
        super().__init__("tilebox:aws:IAMRole", name, opts=opts)

        assume_role_policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": assume_service},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        )

        self.role = (
            iam.Role.get(f"{name}-role", existing_role_name, opts=ResourceOptions(parent=self))
            if existing_role_name
            else iam.Role(
                f"{name}-role",
                name=name,
                assume_role_policy=assume_role_policy,
                opts=ResourceOptions(parent=self),
            )
        )

        self.policy_attachments = []
        for policy_arn in managed_policies or []:
            policy_slug = policy_arn.split("/")[-1].lower()
            self.policy_attachments.append(
                iam.RolePolicyAttachment(
                    f"{name}-policy-{policy_slug}",
                    role=self.role.name,
                    policy_arn=policy_arn,
                    opts=ResourceOptions(parent=self),
                )
            )

        self.bucket_policies = []
        for bucket in bucket_access or []:
            actions = _get_s3_actions(bucket["access_level"])
            bucket_arn = bucket["bucket_arn"]

            def make_policy_document(arn: str, actions: list[str] = actions) -> str:
                return json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            # Object-level actions require arn/* resource
                            {
                                "Effect": "Allow",
                                "Action": [a for a in actions if a.startswith("s3:") and a != "s3:ListBucket"],
                                "Resource": f"{arn}/*",
                            },
                            # ListBucket requires bucket-level resource (without /*)
                            {
                                "Effect": "Allow",
                                "Action": "s3:ListBucket",
                                "Resource": arn,
                            },
                        ],
                    }
                )

            policy_document = Output.apply(Output.from_input(bucket_arn), make_policy_document)

            self.bucket_policies.append(
                iam.RolePolicy(
                    f"{name}-bucket-{bucket['bucket_slug']}",
                    role=self.role.name,
                    policy=policy_document,
                    opts=ResourceOptions(parent=self),
                )
            )

        self.secret_policies = []
        for secret in secrets_access or []:
            secret_arn = secret["secret_arn"]

            def make_secret_policy_document(arn: str) -> str:
                return json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "secretsmanager:GetSecretValue",
                                    "secretsmanager:DescribeSecret",
                                ],
                                "Resource": arn,
                            }
                        ],
                    }
                )

            policy_document = Output.apply(Output.from_input(secret_arn), make_secret_policy_document)

            self.secret_policies.append(
                iam.RolePolicy(
                    f"{name}-secret-{secret['secret_slug']}",
                    role=self.role.name,
                    policy=policy_document,
                    opts=ResourceOptions(parent=self),
                )
            )

        if secret_kms_key_arns:
            invoke_opts = InvokeOutputOptions(parent=self)
            iam.RolePolicy(
                f"{name}-decrypt-secrets",
                role=self.role.name,
                policy=Output.apply(
                    Output.all(
                        keys=list(secret_kms_key_arns),
                        region=get_region_output(opts=invoke_opts).region,
                        suffix=get_partition_output(opts=invoke_opts).dns_suffix,
                    ),
                    lambda values: json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "kms:Decrypt",
                                    "Resource": values["keys"],
                                    "Condition": {
                                        "StringEquals": {
                                            "kms:ViaService": f"secretsmanager.{values['region']}.{values['suffix']}"
                                        }
                                    },
                                }
                            ],
                        }
                    ),
                ),
                opts=ResourceOptions(parent=self),
            )

        self.instance_profile = (
            iam.InstanceProfile.get(
                f"{name}-instance-profile", existing_instance_profile_name, opts=ResourceOptions(parent=self)
            )
            if existing_instance_profile_name
            else iam.InstanceProfile(
                f"{name}-instance-profile",
                name=name,
                role=self.role.name,
                opts=ResourceOptions(parent=self),
            )
        )

        self.role_arn: Output[str] = self.role.arn
        self.instance_profile_arn: Output[str] = self.instance_profile.arn
        self.instance_profile_name: Output[str] = self.instance_profile.name

        self.register_outputs(
            {
                "role_arn": self.role_arn,
                "instance_profile_arn": self.instance_profile_arn,
                "instance_profile_name": self.instance_profile_name,
            }
        )

    @classmethod
    def from_config(
        cls,
        name: str,
        config: IAMRoleConfigDict | None,
        assume_service: str = "ec2.amazonaws.com",
        opts: ResourceOptions | None = None,
    ) -> "IAMRole":
        """Create an IAM role from a config dictionary."""
        if config is None:
            return cls(name, assume_service=assume_service, opts=opts)

        return cls(
            name,
            assume_service=assume_service,
            managed_policies=config.get("managed_policies"),
            bucket_access=config.get("bucket_access"),
            secrets_access=config.get("secrets_access"),
            opts=opts,
            existing_role_name=config.get("existing_role_name"),
            existing_instance_profile_name=config.get("existing_instance_profile_name"),
            secret_kms_key_arns=config.get("secret_kms_key_arns", ()),
        )


def _get_s3_actions(access_level: str) -> list[str]:
    """Get S3 actions for the given access level."""
    read_actions = ["s3:GetObject", "s3:ListBucket"]
    write_actions = ["s3:PutObject", "s3:DeleteObject"]

    if access_level == "read":
        return read_actions
    if access_level == "write":
        return write_actions
    if access_level == "readwrite":
        return read_actions + write_actions

    msg = f"Invalid access_level: {access_level}. Must be 'read', 'write', or 'readwrite'."
    raise ValueError(msg)
