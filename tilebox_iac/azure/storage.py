import hashlib
import re

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure import storage


def _account_resource_name(name: str) -> str:
    """Leave eight characters for the provider's random suffix within Azure's 24-character limit."""
    prefix = re.sub(r"[^a-z0-9]", "", name.lower())
    if len(prefix) <= 16:
        return name
    return prefix[:4] + hashlib.sha256(name.encode()).hexdigest()[:12]


class BlobStorage(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        account_name: str | None = None,
        container_name: str = "results",
        opts: ResourceOptions | None = None,
        *,
        public_read: bool = False,
        expiration_days: int | None = None,
        expiration_prefix: str = "",
    ) -> None:
        """Create identity-protected storage; public_read exposes blob URLs for anonymous reads, not lists or writes."""
        if account_name is not None and not re.fullmatch(r"[a-z0-9]{3,24}", account_name):
            raise ValueError("account_name must contain 3-24 lowercase letters or digits")
        if expiration_days is not None and (type(expiration_days) is not int or expiration_days < 1):
            raise ValueError("expiration_days must be a positive integer or None")
        if expiration_prefix and expiration_days is None:
            raise ValueError("expiration_prefix requires expiration_days")
        super().__init__("tilebox:azure:BlobStorage", name, opts=opts)
        self.public_read = public_read
        self.account = storage.Account(
            _account_resource_name(name) if account_name is None else name,
            name=account_name,
            resource_group_name=resource_group_name,
            location=location,
            account_tier="Standard",
            account_replication_type="LRS",
            account_kind="StorageV2",
            min_tls_version="TLS1_2",
            https_traffic_only_enabled=True,
            allow_nested_items_to_be_public=public_read,
            shared_access_key_enabled=False,
            default_to_oauth_authentication=True,
            blob_properties={
                "versioning_enabled": True,
                "delete_retention_policy": {"days": 7},
                "container_delete_retention_policy": {"days": 7},
            },
            opts=ResourceOptions(parent=self),
        )
        self.container = storage.Container(
            name,
            name=container_name,
            storage_account_id=self.account.id,
            container_access_type="blob" if public_read else "private",
            opts=ResourceOptions(parent=self),
        )
        if expiration_days is not None:
            storage.ManagementPolicy(
                f"{name}-expiration",
                storage_account_id=self.account.id,
                rules=[
                    {
                        "name": "expire-objects",
                        "enabled": True,
                        "filters": {
                            "blob_types": ["blockBlob"],
                            "prefix_matches": [Output.concat(self.container.name, "/", expiration_prefix)],
                        },
                        "actions": {
                            "base_blob": {"delete_after_days_since_modification_greater_than": expiration_days},
                            "version": {"delete_after_days_since_creation": expiration_days},
                            "snapshot": {"delete_after_days_since_creation_greater_than": expiration_days},
                        },
                    }
                ],
                opts=ResourceOptions(parent=self, protect=False),
            )
        self.account_url = self.account.primary_blob_endpoint
        self.container_name = self.container.name
        self.container_resource_id = Output.concat(
            self.account.id, "/blobServices/default/containers/", self.container.name
        )
        self.register_outputs(
            {
                "account_url": self.account_url,
                "container_name": self.container_name,
                "container_resource_id": self.container_resource_id,
            }
        )
