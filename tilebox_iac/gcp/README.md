# GCP runners

`gcp.Cluster(name, project, tilebox_api_key)` enables the required APIs and creates a private VPC with NAT,
a service account, a Secret Manager secret, and a regional Spot instance group.
Defaults are `europe-west1`, `n2-standard-2`, 60-GiB disks, one to ten instances, and a 20% CPU target.

Pass additional secret values to `Cluster` with `secret_environment_variables={"SERVICE_API_KEY": config.require_secret("serviceApiKey")}`.
It creates secrets in the cluster's project and grants the runner read access. Values are fetched at startup;
new secret versions trigger worker replacement. Keep `TILEBOX_API_KEY` in `tilebox_api_key`, and do not repeat keys
in `environment_variables`.

Use `cache=True, cache_expiration_days=7` to create a private GCS cache in the cluster's project and region, or
`cache=existing_storage` to reuse a `gcp.BlobStorage`. The cluster sets `TILEBOX_WORKER_CACHE=gs://<bucket>/jobs` and
grants its service account `roles/storage.objectUser` on that bucket. Storage stays in place when `enabled=False`;
`cluster.cache_uri` exposes the URI. Configure expiry on reused storage with `expiration_days=7, expiration_prefix="jobs/"`.
The age-based deletion rule covers both live and noncurrent versions.

Use `gcp.runner.AutoScalingCluster` with existing infrastructure:

```python
from tilebox_iac.gcp.runner import AutoScalingCluster

cluster = AutoScalingCluster(
    "runners",
    gcp_project=project,
    gcp_region="europe-west1",
    machine_type="n2-standard-2",
    cpu_target=0.2,
    cluster_enabled=True,
    min_replicas_config=1,
    max_replicas_config=10,
    network_interfaces=[{"network": network_id, "subnetwork": subnet_id}],
    roles={"existing_email": service_account_email},
    secret_environment_variables={
        "TILEBOX_API_KEY": {"secret_id": api_key_secret_id, "rollout_marker": "v1"},
    },
)
```

Secret IDs have the form `projects/PROJECT/secrets/SECRET`. Change `rollout_marker` after rotating an external secret
to replace workers. Library-managed `Secret` versions trigger this automatically. Omit `existing_email` to create a
service account. The component manages its IAM grants in either case.

For Shared VPC, set `health_check_network` and `health_check_network_project` to the host network and project.
The deployer's identity needs firewall permissions there. Private subnets need outbound internet access through NAT.
Existing infrastructure also needs the Compute, IAM, Monitoring, Secret Manager, and Cloud Resource Manager APIs.

`Cluster` enables healing for new fleets. Low-level `AutoScalingCluster` leaves it disabled: first deploy with
`auto_healing_enabled=False` and wait for the template rollout and healthy checks, then enable it in a second deployment.
Only Google's health-check ranges can reach port 8080.

Set `enabled=False` on `Cluster`, or `cluster_enabled=False` on `AutoScalingCluster`, to delete the autoscaler,
instance group, VMs and boot disks, instance template, and health-check resources. Pulumi deletes the autoscaler
before the instance group. Networks, identities, secrets, and cache storage remain.
Re-enabling creates a new fleet. `runner.mig` is `None` while disabled.
