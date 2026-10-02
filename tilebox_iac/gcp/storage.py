from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_gcp import storage


class BlobStorage(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        location: Input[str],
        bucket_name: Input[str] | None = None,
        opts: ResourceOptions | None = None,
        *,
        project: Input[str] | None = None,
        public_read: bool = False,
        expiration_days: int | None = None,
        expiration_prefix: str = "",
    ) -> None:
        """Create a GCS bucket; public_read exposes object URLs for anonymous reads, not lists or writes."""
        if expiration_days is not None and (type(expiration_days) is not int or expiration_days < 1):
            raise ValueError("expiration_days must be a positive integer or None")
        if expiration_prefix and expiration_days is None:
            raise ValueError("expiration_prefix requires expiration_days")
        super().__init__("tilebox:gcp:BlobStorage", name, opts=opts)
        self.public_read = public_read
        self.bucket = storage.Bucket(
            name,
            name=bucket_name,
            project=project,
            location=location,
            uniform_bucket_level_access=True,
            public_access_prevention="inherited" if public_read else "enforced",
            versioning={"enabled": True},
            lifecycle_rules=(
                [
                    storage.BucketLifecycleRuleArgs(
                        action=storage.BucketLifecycleRuleActionArgs(type="Delete"),
                        condition=storage.BucketLifecycleRuleConditionArgs(
                            age=expiration_days,
                            with_state="ANY",
                            matches_prefixes=[expiration_prefix] if expiration_prefix else None,
                        ),
                    )
                ]
                if expiration_days is not None
                else None
            ),
            opts=ResourceOptions(parent=self),
        )
        if public_read:
            storage.BucketIAMMember(
                f"{name}-public-read",
                bucket=self.bucket.name,
                role="roles/storage.legacyObjectReader",
                member="allUsers",
                opts=ResourceOptions(parent=self, protect=False),
            )
        self.bucket_name = self.bucket.name
        self.register_outputs({"bucket_name": self.bucket_name})
