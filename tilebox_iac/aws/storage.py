import json

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_aws import s3


class BlobStorage(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        bucket_name: Input[str] | None = None,
        opts: ResourceOptions | None = None,
        *,
        public_read: bool = False,
        expiration_days: int | None = None,
        expiration_prefix: str = "",
    ) -> None:
        """Create an S3 bucket; public_read exposes object URLs for anonymous reads, not lists or writes."""
        if expiration_days is not None and (type(expiration_days) is not int or expiration_days < 1):
            raise ValueError("expiration_days must be a positive integer or None")
        if expiration_prefix and expiration_days is None:
            raise ValueError("expiration_prefix requires expiration_days")
        super().__init__("tilebox:aws:BlobStorage", name, opts=opts)
        self.public_read = public_read
        child = ResourceOptions(parent=self)
        self.bucket = s3.Bucket(name, bucket=bucket_name, opts=child)
        ownership = s3.BucketOwnershipControls(
            name, bucket=self.bucket.id, rule={"object_ownership": "BucketOwnerEnforced"}, opts=child
        )
        access = s3.BucketPublicAccessBlock(
            name,
            bucket=self.bucket.id,
            block_public_acls=True,
            ignore_public_acls=True,
            block_public_policy=not public_read,
            restrict_public_buckets=not public_read,
            opts=child,
        )
        versioning = s3.BucketVersioning(
            name, bucket=self.bucket.id, versioning_configuration={"status": "Enabled"}, opts=child
        )
        if expiration_days is not None:
            s3.BucketLifecycleConfiguration(
                name,
                bucket=self.bucket.id,
                rules=[
                    {
                        "id": "expire-objects",
                        "status": "Enabled",
                        "filter": {"prefix": expiration_prefix},
                        "expiration": {"days": expiration_days},
                        "noncurrent_version_expiration": {"noncurrent_days": expiration_days},
                    },
                    {
                        "id": "remove-delete-markers",
                        "status": "Enabled",
                        "filter": {"prefix": expiration_prefix},
                        "expiration": {"expired_object_delete_marker": True},
                    },
                ],
                opts=ResourceOptions(parent=self, depends_on=[versioning], protect=False),
            )
        s3.BucketPolicy(
            name,
            bucket=self.bucket.id,
            policy=Output.apply(
                self.bucket.arn,
                lambda arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Deny",
                                "Principal": "*",
                                "Action": "s3:*",
                                "Resource": [arn, f"{arn}/*"],
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            },
                            *(
                                [
                                    {
                                        "Effect": "Allow",
                                        "Principal": "*",
                                        "Action": "s3:GetObject",
                                        "Resource": f"{arn}/*",
                                    }
                                ]
                                if public_read
                                else []
                            ),
                        ],
                    }
                ),
            ),
            opts=ResourceOptions(parent=self, depends_on=[access, ownership]),
        )
        self.bucket_name = self.bucket.bucket
        self.bucket_arn = self.bucket.arn
        self.register_outputs({"bucket_name": self.bucket_name, "bucket_arn": self.bucket_arn})
