# AWS runners

`aws.Cluster(name, tilebox_api_key)` creates a VPC, two public subnets with outbound internet access, a security group
with no inbound access, a Secrets Manager secret, an instance role, and a Spot Auto Scaling Group.
Defaults are `m7i.large`, 60-GiB encrypted disks, one to ten instances, and a 20% CPU target.

Pass additional secret values to `Cluster` with `secret_environment_variables={"SERVICE_API_KEY": config.require_secret("serviceApiKey")}`.
It creates Secrets Manager secrets using `secret_recovery_window_days` and grants the runner read access.
Values are fetched at startup; new secret versions trigger worker replacement. Keep `TILEBOX_API_KEY` in
`tilebox_api_key`, and do not repeat keys in `environment_variables`.

Use `cache=True, cache_expiration_days=7` to create a private S3 cache, or `cache=existing_storage` to reuse an
`aws.BlobStorage`. The cluster sets `TILEBOX_WORKER_CACHE=s3://<bucket>/jobs` and grants bucket-scoped read/write access.
Storage stays in place when `enabled=False`; `cluster.cache_uri` exposes the URI. Configure expiry on reused storage
with `expiration_days=7, expiration_prefix="jobs/"`. Expiry covers current objects, noncurrent versions, and delete markers.

Use `aws.runner.AutoScalingCluster` with existing subnets and security groups. The security groups must permit
outbound traffic for image pulls and Tilebox access. `aws.Network` remains available for a private subnet with NAT.

```python
from tilebox_iac.aws.runner import AutoScalingCluster

cluster = AutoScalingCluster(
    "runners",
    instance_type="m7i.large",
    cpu_target=0.2,
    cluster_enabled=True,
    min_replicas_config=1,
    max_replicas_config=10,
    subnet_ids=subnet_ids,
    security_group_ids=security_group_ids,
    secret_environment_variables={
        "TILEBOX_API_KEY": {"secret_arn": api_key_arn, "rollout_marker": "v1"},
    },
    iam_config={
        "existing_role_name": role_name,
        "existing_instance_profile_name": instance_profile_name,
    },
)
```

Omit the existing role/profile pair to create them. The component manages the runner's IAM grants even when the
identity already exists. Add `secret_kms_key_arns` for secrets encrypted with customer-managed KMS keys.
Change `rollout_marker` after rotating an external secret to replace workers. Library-managed `Secret` versions
trigger this automatically.

Set `enabled=False` on `Cluster`, or `cluster_enabled=False` on `AutoScalingCluster`, to delete the Auto Scaling Group,
its VMs and boot disks, launch template, and scaling policy. Networks, identities, secrets, and cache storage remain.
Re-enabling creates a new fleet. `runner.asg` is `None` while disabled.

The runner checks its container once a minute and reports itself unhealthy after ten failures. Its IAM permission
is scoped to the component's Auto Scaling Group. Template changes trigger a rolling instance refresh.
