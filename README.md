# Tilebox infrastructure components

Python components for running Tilebox workers on AWS, GCP, Azure, and Kubernetes, including CREODIAS.
They use the open-source [Pulumi CLI](https://www.pulumi.com/docs/install/) with local file state.
No hosted Pulumi account is needed. You can choose another Pulumi backend later.

## Start with a cluster

Create a Python project and install the library from GitHub:

```bash
mkdir tilebox-runners
cd tilebox-runners
uv init --bare
uv add git+https://github.com/tilebox/tilebox-iac.git
```

Save this as `Pulumi.yaml`:

```yaml
name: tilebox-runners
runtime:
  name: python
  options:
    toolchain: uv
```

For AWS, save this as `__main__.py`:

```python
import pulumi
from tilebox_iac import aws

cluster = aws.Cluster("runners", pulumi.Config().require_secret("tileboxApiKey"))
pulumi.export("autoscalingGroupName", cluster.runner.asg.name if cluster.runner.asg is not None else None)
```

Authenticate to AWS, then configure and deploy:

```bash
pulumi login --local
pulumi stack init dev
pulumi config set aws:region us-west-2
pulumi config set --secret tileboxApiKey
pulumi up
```

Pulumi keeps state on your machine and prompts for a passphrase to encrypt secrets.
`pulumi up` previews changes before asking to apply them.

## Components

| Component | Purpose |
| --- | --- |
| `aws.Cluster` | Create a VPC, two public subnets, identity, API-key secret, and Spot runners. |
| `gcp.Cluster` | Enable APIs and create a private network with NAT, identity, API-key secret, and Spot runners. |
| `azure.Cluster` | Create a resource group, network with NAT, Key Vault API-key secret, identity, and runners. |
| `aws.runner.AutoScalingCluster` | Run workers in existing AWS infrastructure. |
| `gcp.runner.AutoScalingCluster` | Run workers in existing GCP infrastructure. |
| `azure.runner.AutoScalingCluster` | Run Azure workers in existing infrastructure, with optional Spot instances. |
| `azure.BlobStorage` | Create authenticated Blob Storage for Azure or on-prem workers. |
| `aws.BlobStorage`, `gcp.BlobStorage` | Create S3 or GCS storage with optional anonymous object reads. |
| `creodias.Cluster` | Create a CloudFerro Kubernetes cluster and autoscaled worker pool. |
| `kubernetes.Runner` | Run CPU-autoscaled pods on a labelled Kubernetes worker pool. |

All three clouds expose `Network` and `Secret` components; AWS/GCP also expose identity components. Existing
`aws.AutoScalingCluster`, `gcp.AutoScalingCluster`, and `azure.AutoScalingCluster` imports still work.
Changing an existing stack to the new `Cluster` component changes resource
ownership; use it for new fleets rather than as a drop-in replacement.

See [examples](examples/README.md), the [AWS guide](tilebox_iac/aws/README.md),
[GCP guide](tilebox_iac/gcp/README.md), and [Azure guide](tilebox_iac/azure/README.md).

## Runner settings

The default image is `ghcr.io/tilebox/runner:latest`, pulled anonymously. Set `runner_image` for a prebuilt custom image.
The library preserves its entrypoint, command, and user. It does not build or publish images.
AWS supports private ECR images with IAM pull permissions; GCP supports GCR and Artifact Registry with reader roles.
Azure supports private ACR images through managed identity; Kubernetes accepts `image_pull_secret_names`.

`TILEBOX_API_KEY` is required. `TILEBOX_CLUSTER` is optional and defaults to the account's default cluster.
Pass other settings through `environment_variables`. Use provider `Secret` components or existing secret references
for VM credentials so values are fetched at startup instead of placed in cloud-init.

All three high-level `Cluster` components accept `secret_environment_variables`, a mapping of environment-variable
names to Pulumi string inputs. They create secrets in AWS Secrets Manager, GCP Secret Manager, or the cluster's Azure
Key Vault and grant the runner access. For example:

```python
cluster = aws.Cluster(
    "runners",
    tilebox_api_key=pulumi.Config().require_secret("tileboxApiKey"),
    secret_environment_variables={"SERVICE_API_KEY": pulumi.Config().require_secret("serviceApiKey")},
)
```

Keep `TILEBOX_API_KEY` in the dedicated `tilebox_api_key` input. Keys cannot overlap with `environment_variables`.
Existing `Secret` objects in `environment_variables` remain supported. Updating a managed secret value changes the
runner template so workers fetch the new version during rollout. The low-level AWS/GCP runners' same-named input
continues to accept existing secret references, not values.

AWS/GCP clusters default to 60-GiB disks, one to ten replicas, and a CPU target of 20%. Azure defaults to 40-GiB disks
and one to two replicas. Set `root_volume_size_gb` and replica bounds for your workload. Boot disks are deleted with VMs.
Enabled VM fleets need at least one replica; CPU autoscaling cannot wake a fleet from zero.

Set `enabled=False` on `Cluster`, or `cluster_enabled=False` on a low-level runner, to delete the fleet,
including its VMs and boot disks. Networks, identities, secrets, and cache storage remain; retained resources
such as NAT gateways and storage can still incur charges. Re-enabling creates a new fleet.
The runner's `asg`, `mig`, or `scale_set` attribute is `None` while disabled.

## Object storage

`aws.BlobStorage`, `gcp.BlobStorage`, and `azure.BlobStorage` all default to private storage and accept keyword-only
`public_read=True`. This makes existing and future objects readable by anyone with their URL, without granting
anonymous listing or writes. Image registries remain private. Account or organization policies may block public access;
these components do not change those policies.

```python
aws_results = aws.BlobStorage("results", public_read=True)
gcp_results = gcp.BlobStorage("results", location="europe-west1", public_read=True)
azure_results = azure.BlobStorage("results", group.name, location, public_read=True)
```

Pass `opts=pulumi.ResourceOptions(protect=True)` to prevent Pulumi from deleting the storage resources. Grant writers access through
AWS IAM, GCP bucket IAM, or Azure managed identity. AWS/GCP expose `.bucket` and `.bucket_name`; AWS also exposes
`.bucket_arn`. Azure exposes `.account_url`, `.container_name`, and `.container_resource_id`.
Use the Azure provider feature settings in its guide when creating Blob Storage.

All three `BlobStorage` components accept `expiration_days=7` and `expiration_prefix="jobs/"` to expire matching
objects and old versions. Both are optional: `expiration_days=None` creates no expiry policy, and the default empty
prefix covers the whole bucket or Azure container. Prefixes are object-name prefixes, not storage URIs.
AWS counts current-object age and time since versions became noncurrent; GCP counts each version's creation age.
Azure counts current blobs from their last modification and old versions/snapshots from creation.
Cloud lifecycle processing and soft-delete retention can delay removal. Pulumi protection does not stop lifecycle deletion.

## Worker caches

All three high-level `Cluster` components accept `cache=True` to create private cache storage. Add
`cache_expiration_days=7` to expire objects under `jobs/`; without it, the cache has no expiry policy.
They set `TILEBOX_WORKER_CACHE` to `s3://<bucket>/jobs`, `gs://<bucket>/jobs`, or
`az://<account>/worker-cache/jobs` and grant the runner access to that bucket or container.
The workflow must support the URI scheme and cloud-identity authentication.

To reuse storage, pass `cache=existing_storage`, where `existing_storage` is a private `BlobStorage` component from
the same provider. Configure expiry on that storage component, not the cluster. Reuse keeps its resource ownership,
names, and lifecycle policy; it does not look up storage by URI. Both modes expose `cluster.cache` and `cluster.cache_uri`.

`cache=False` is the default and leaves existing manual cache wiring unchanged. When a cache is configured, neither
environment mapping may set `TILEBOX_WORKER_CACHE`. Setting `enabled=False` retains the cache and its expiry policy
while deleting the worker fleet. Removing a cluster-owned cache from the program or changing it to `cache=False` requests
storage deletion; it is not the way to pause workers. Low-level runners only receive the URI and access grants.

## Health and updates

Systemd restarts failed containers. AWS, GCP, and Azure can replace VMs when the container stays stopped.
These checks measure container state, not task progress or Tilebox connectivity.

New `gcp.Cluster` fleets enable automatic healing. Existing `gcp.AutoScalingCluster` callers retain the default
`auto_healing_enabled=False`: roll out the health endpoint and verify every instance is healthy before enabling it.
Azure repairs are enabled by default; its guide describes the same two-stage rollout for existing fleets.

AWS/GCP roll out template changes automatically. The Azure provider updates and reimages workers automatically with
the settings in its guide; interrupted tasks are retried.
Kubernetes rolls pods when their image or environment changes. Use image tags or digests that change when you publish
an update. Tilebox [retries tasks after runner crashes](https://docs.tilebox.com/workflows/concepts/runners#runner-crashes).
