import re
from collections.abc import Sequence
from typing import TypedDict

from pulumi import Alias, ComponentResource, Output, ResourceOptions
from pulumi_gcp.artifactregistry import Repository, RepositoryIamMember
from pulumi_gcp.cloudrun import IamMember as CloudrunServiceIamMember
from pulumi_gcp.cloudrunv2 import Service
from pulumi_gcp.projects import IAMMember
from pulumi_gcp.secretmanager import Secret, SecretIamMember
from pulumi_gcp.serviceaccount import Account
from pulumi_gcp.storage import AwaitableGetBucketResult, Bucket, BucketIAMMember
from typing_extensions import NotRequired


class BucketRoleDict(TypedDict):
    """Same as BucketRole, but as a typed dictionary."""

    bucket_slug: str
    bucket: Bucket | AwaitableGetBucketResult
    role: str


class ServiceRoleDict(TypedDict):
    """Same as ServiceRole, but as a typed dictionary."""

    service_slug: str
    service: Service
    role: str


class RepositoryRoleDict(TypedDict):
    """Same as RepositoryRole, but as a typed dictionary."""

    repository_slug: str
    repository: Repository
    role: str


class SecretRoleDict(TypedDict):
    """Same as SecretRole, but as a typed dictionary."""

    secret_slug: str
    secret: Secret
    role: str


class ServiceAccountConfigDict(TypedDict):
    """Same as ServiceAccountConfig, but as a typed dictionary."""

    roles: NotRequired[Sequence[str]]
    bucket_roles: NotRequired[Sequence[BucketRoleDict]]
    service_roles: NotRequired[Sequence[ServiceRoleDict]]
    repository_roles: NotRequired[Sequence[RepositoryRoleDict]]
    secret_roles: NotRequired[Sequence[SecretRoleDict]]


class ServiceAccount(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        gcp_project: str,
        roles: Sequence[str] | None = None,
        bucket_roles: Sequence[BucketRoleDict] | None = None,
        service_roles: Sequence[ServiceRoleDict] | None = None,
        repository_roles: Sequence[RepositoryRoleDict] | None = None,
        secret_roles: Sequence[SecretRoleDict] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create a service account with given roles.

        Args:
            name: Service account name.
            gcp_project: GCP project ID.
            roles: IAM project roles to assign to the service account.
            bucket_roles: Bucket specific roles for certain buckets.
            service_roles: Service specific roles for certain cloud run services.
            repository_roles: Repository specific roles for certain artifact registry repositories.
            secret_roles: Secret specific roles for certain secrets.
            opts: Pulumi resource options.
        """
        opts = ResourceOptions.merge(
            opts, ResourceOptions(aliases=[Alias(type_="tilebox:service_account:ServiceAccount")])
        )
        super().__init__("tilebox:gcp:ServiceAccount", name, opts=opts)

        self.service_account = Account(
            f"{name}-service-account",
            account_id=name,
            display_name=f"Tilebox {name} Service Account",
            opts=ResourceOptions(parent=self),
        )

        service_account_member = Output.concat("serviceAccount:", self.service_account.email)

        self.roles = []
        for role in roles or []:
            self.roles.append(
                IAMMember(
                    f"{name}-role-{_role_to_slug(role)}",
                    role=role,
                    member=service_account_member,
                    project=gcp_project,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.bucket_roles = []
        for bucket_role in bucket_roles or []:
            self.bucket_roles.append(
                BucketIAMMember(
                    f"{name}-bucket-{bucket_role['bucket_slug']}-role-{_role_to_slug(bucket_role['role'])}",
                    bucket=bucket_role["bucket"].name,
                    role=bucket_role["role"],
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.service_roles = []
        for service_role in service_roles or []:
            self.service_roles.append(
                CloudrunServiceIamMember(
                    f"{name}-service-{service_role['service_slug']}-role-{_role_to_slug(service_role['role'])}",
                    service=service_role["service"].name,
                    role=service_role["role"],
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.repository_roles = []
        for repository_role in repository_roles or []:
            repository = repository_role["repository"]
            self.repository_roles.append(
                RepositoryIamMember(
                    f"{name}-repository-{repository_role['repository_slug']}-role-{_role_to_slug(repository_role['role'])}",
                    project=repository.project,
                    location=repository.location,
                    repository=repository.name,
                    role=repository_role["role"],
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.secret_roles = []
        for secret_role in secret_roles or []:
            self.secret_roles.append(
                SecretIamMember(
                    f"{name}-secret-{secret_role['secret_slug']}-role-{_role_to_slug(secret_role['role'])}",
                    secret_id=secret_role["secret"].id,
                    role=secret_role["role"],
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.id = self.service_account.id
        self.email = self.service_account.email
        self.register_outputs(
            {
                "id": self.service_account.id,
                "email": self.service_account.email,
            }
        )

    @classmethod
    def from_config(
        cls,
        name: str,
        gcp_project: str,
        config: ServiceAccountConfigDict | None,
        opts: ResourceOptions | None = None,
    ) -> "ServiceAccount":
        """Create a service account from a config."""
        if config is None:
            return cls(name, gcp_project, opts=opts)

        return cls(
            name,
            gcp_project=gcp_project,
            roles=config.get("roles"),
            bucket_roles=config.get("bucket_roles"),
            service_roles=config.get("service_roles"),
            repository_roles=config.get("repository_roles"),
            secret_roles=config.get("secret_roles"),
            opts=opts,
        )


def _role_to_slug(role: str) -> str:
    """Convert a role to a slug."""
    parts = role.removeprefix("roles/").split(".")
    parts = [re.sub(r"(?<!^)(?=[A-Z])", "-", part).lower() for part in parts]
    return "-".join(parts)
