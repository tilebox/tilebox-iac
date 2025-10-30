import re
from collections.abc import Sequence
from typing import NotRequired, TypedDict

from attr import dataclass
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_gcp.artifactregistry import Repository, RepositoryIamMember
from pulumi_gcp.cloudrun import IamMember as CloudrunServiceIamMember
from pulumi_gcp.cloudrunv2 import Service
from pulumi_gcp.projects import IAMMember
from pulumi_gcp.secretmanager import Secret, SecretIamMember
from pulumi_gcp.serviceaccount import Account
from pulumi_gcp.storage import AwaitableGetBucketResult, Bucket, BucketIAMMember


@dataclass
class BucketRole:
    bucket_slug: str
    """Slug of the bucket, used as part of the pulumi resource name for the bucket IAM member."""
    bucket: Bucket | AwaitableGetBucketResult
    """The bucket to grant the role for."""
    role: str
    """Bucket role to grant. e.g. `roles/storage.objectUser`"""


class BucketRoleDict(TypedDict):
    """Same as BucketRole, but as a typed dictionary."""

    bucket_slug: str
    bucket: Bucket | AwaitableGetBucketResult
    role: str


@dataclass
class ServiceRole:
    service_slug: str
    """Slug of the service, used as part of the pulumi resource name for the bucket IAM member."""
    service: Service
    """The service to grant the role for."""
    role: str
    """Service role to grant. e.g. `roles/run.invoker`"""


class ServiceRoleDict(TypedDict):
    """Same as ServiceRole, but as a typed dictionary."""

    service_slug: str
    service: Service
    role: str


@dataclass
class RepositoryRole:
    repository_slug: str
    """Slug of the repository, used as part of the pulumi resource name for the repository IAM member."""
    repository: Repository
    """The repository to grant the role for."""
    role: str
    """Repository role to grant. e.g. `roles/artifactregistry.writer`"""


class RepositoryRoleDict(TypedDict):
    """Same as RepositoryRole, but as a typed dictionary."""

    repository_slug: str
    repository: Repository
    role: str


@dataclass
class SecretRole:
    secret_slug: str
    """Slug of the secret, used as part of the pulumi resource name for the secret IAM member."""
    secret: Secret
    """The secret to grant the role for."""
    role: str
    """Secret role to grant. e.g. `roles/secretmanager.secretAccessor`"""


class SecretRoleDict(TypedDict):
    """Same as SecretRole, but as a typed dictionary."""

    secret_slug: str
    secret: Secret
    role: str


@dataclass
class ServiceAccountConfig:
    """Configuration for a service account and its roles."""

    roles: Sequence[str] | None
    bucket_roles: Sequence[BucketRole] | None
    service_roles: Sequence[ServiceRole] | None
    repository_roles: Sequence[RepositoryRole] | None
    secret_roles: Sequence[SecretRole] | None


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
        bucket_roles: Sequence[BucketRole] | Sequence[BucketRoleDict] | None = None,
        service_roles: Sequence[ServiceRole] | Sequence[ServiceRoleDict] | None = None,
        repository_roles: Sequence[RepositoryRole] | Sequence[RepositoryRoleDict] | None = None,
        secret_roles: Sequence[SecretRole] | Sequence[SecretRoleDict] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """
        Create a service account with given roles.

        Args:
            name: Service account name.
            roles: IAM project roles to assign to the service account.
            bucket_roles: Bucket specific roles for certain buckets.
            service_roles: Service specific roles for certain cloud run services.
            repository_roles: Repository specific roles for certain artifact registry repositories.
            secret_roles: Secret specific roles for certain secrets.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:service_account:ServiceAccount", name, opts=opts)

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
            br = bucket_role if isinstance(bucket_role, BucketRole) else BucketRole(**bucket_role)
            self.bucket_roles.append(
                BucketIAMMember(
                    f"{name}-bucket-{br.bucket_slug}-role-{_role_to_slug(br.role)}",
                    bucket=br.bucket.name,
                    role=br.role,
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.service_roles = []
        for service_role in service_roles or []:
            sr = service_role if isinstance(service_role, ServiceRole) else ServiceRole(**service_role)
            self.service_roles.append(
                CloudrunServiceIamMember(
                    f"{name}-service-{sr.service_slug}-role-{_role_to_slug(sr.role)}",
                    service=sr.service.name,
                    role=sr.role,
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.repository_roles = []
        for repository_role in repository_roles or []:
            rr = repository_role if isinstance(repository_role, RepositoryRole) else RepositoryRole(**repository_role)
            self.repository_roles.append(
                RepositoryIamMember(
                    f"{name}-repository-{rr.repository_slug}-role-{_role_to_slug(rr.role)}",
                    project=rr.repository.project,
                    location=rr.repository.location,
                    repository=rr.repository.name,
                    role=rr.role,
                    member=service_account_member,
                    opts=ResourceOptions(depends_on=[self.service_account], parent=self),
                )
            )

        self.secret_roles = []
        for secret_role in secret_roles or []:
            sr = secret_role if isinstance(secret_role, SecretRole) else SecretRole(**secret_role)
            self.secret_roles.append(
                SecretIamMember(
                    f"{name}-secret-{sr.secret_slug}-role-{_role_to_slug(sr.role)}",
                    secret_id=sr.secret.id,
                    role=sr.role,
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
        config: ServiceAccountConfig | ServiceAccountConfigDict | None,
        opts: ResourceOptions | None = None,
    ) -> "ServiceAccount":
        """Create a service account from a config."""

        if config is None:
            return cls(name, gcp_project, opts=opts)

        if not isinstance(config, ServiceAccountConfig):
            config = ServiceAccountConfig(
                roles=config.get("roles", None),
                bucket_roles=[BucketRole(**role) for role in config.get("bucket_roles", [])],
                service_roles=[ServiceRole(**role) for role in config.get("service_roles", [])],
                repository_roles=[RepositoryRole(**role) for role in config.get("repository_roles", [])],
                secret_roles=[SecretRole(**role) for role in config.get("secret_roles", [])],
            )

        return cls(
            name,
            gcp_project=gcp_project,
            roles=config.roles,
            bucket_roles=config.bucket_roles,
            service_roles=config.service_roles,
            repository_roles=config.repository_roles,
            secret_roles=config.secret_roles,
            opts=opts,
        )


def _role_to_slug(role: str) -> str:
    """Convert a role to a slug.

    >>> _role_to_slug("roles/iam.serviceAccountUser")
    >>> "iam-service-account-user"
    """

    parts = role.removeprefix("roles/").split(".")
    # camel case to kebab case
    parts = [re.sub(r"(?<!^)(?=[A-Z])", "-", part).lower() for part in parts]
    return "-".join(parts)
