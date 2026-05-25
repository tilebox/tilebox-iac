import uuid
from collections.abc import Sequence
from typing import TypedDict

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import authorization, managedidentity
from typing_extensions import NotRequired


class ScopeRoleDict(TypedDict):
    scope_slug: str
    scope: Input[str]
    role_definition_id: Input[str]


class ManagedIdentityConfigDict(TypedDict):
    scope_roles: NotRequired[Sequence[ScopeRoleDict]]


class ManagedIdentity(ComponentResource):
    def __init__(
        self,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        scope_roles: Sequence[ScopeRoleDict] | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create a user-assigned managed identity and optional Azure role assignments."""
        super().__init__("tilebox:azure:ManagedIdentity", name, opts=opts)

        self.identity = managedidentity.UserAssignedIdentity(
            f"{name}-identity",
            resource_group_name=resource_group_name,
            resource_name_=f"{name}-identity",
            location=location,
            opts=ResourceOptions(parent=self),
        )

        self.role_assignments = []
        for role in scope_roles or []:
            assignment_name = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{name}:{role['scope_slug']}"))
            self.role_assignments.append(
                authorization.RoleAssignment(
                    f"{name}-role-{role['scope_slug']}",
                    principal_id=self.identity.principal_id,
                    principal_type="ServicePrincipal",
                    role_assignment_name=assignment_name,
                    role_definition_id=role["role_definition_id"],
                    scope=role["scope"],
                    opts=ResourceOptions(depends_on=[self.identity], parent=self),
                )
            )

        self.id: Output[str] = self.identity.id
        self.client_id: Output[str] = self.identity.client_id
        self.principal_id: Output[str] = self.identity.principal_id
        self.register_outputs(
            {
                "id": self.id,
                "client_id": self.client_id,
                "principal_id": self.principal_id,
            }
        )

    @classmethod
    def from_config(
        cls,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        config: ManagedIdentityConfigDict | None,
        opts: ResourceOptions | None = None,
    ) -> "ManagedIdentity":
        if config is None:
            return cls(name, resource_group_name, location, opts=opts)

        return cls(
            name,
            resource_group_name=resource_group_name,
            location=location,
            scope_roles=config.get("scope_roles"),
            opts=opts,
        )
