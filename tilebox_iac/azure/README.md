# Azure runners and storage

The Azure components create runner VM Scale Sets with CPU autoscaling, managed identities, and Key Vault secrets.
Blob Storage can also be used separately with workers outside Azure.

## Setup

Install the Pulumi CLI, Azure CLI, Python, and uv. Create a Python project and install this library from GitHub:

```bash
mkdir azure-runners
cd azure-runners
uv init --bare
uv add git+https://github.com/tilebox/tilebox-iac.git
```

Create `Pulumi.yaml` in that directory to tell Pulumi how to run the Python program:

```yaml
name: azure-runners
runtime:
  name: python
  options:
    toolchain: uv
```

Use the open-source Pulumi CLI with local file state. Create a stack and configure Azure access:

```bash
pulumi login --local
pulumi stack init dev
az login
pulumi config set azure:subscriptionId "$(az account show --query id --output tsv)"
pulumi config set location westeurope
pulumi config set sshPublicKey "$(cat ~/.ssh/id_rsa.pub)"
pulumi config set --secret tileboxApiKey
```

The subscription ID identifies the Azure account to bill. The Azure provider requires it; the command reads it
from your active Azure CLI subscription. Use `az account set --subscription <name-or-id>` first if you have several.
Your Azure identity needs permission to create resources and assign roles.

Choose a region near your data. `westeurope` hosts most of the
[Planetary Computer catalog](https://planetarycomputer.microsoft.com/docs/concepts/computing/).
Azure requires an SSH public key for these password-disabled VMs, although the network does not allow inbound SSH.
Use an existing RSA public key, or create one with `ssh-keygen -t rsa -b 4096`.

## Create a cluster

`azure.Cluster` creates the resource group, network, Key Vault secrets, identity, and runners.
Save this as `__main__.py`:

```python
import pulumi
import pulumi_azure as az

from tilebox_iac import azure

config = pulumi.Config()
location = config.require("location")
provider = az.Provider(
    "azure",
    subscription_id=pulumi.Config("azure").require("subscriptionId"),
    features=az.ProviderFeaturesArgs(
        storage=az.ProviderFeaturesStorageArgs(data_plane_available=False),
        virtual_machine_scale_set=az.ProviderFeaturesVirtualMachineScaleSetArgs(
            roll_instances_when_required=True,
            reimage_on_manual_upgrade=True,
        ),
    ),
)
opts = pulumi.ResourceOptions(provider=provider)
cluster = azure.Cluster(
    "runners",
    tilebox_api_key=config.require_secret("tileboxApiKey"),
    location=location,
    ssh_public_key=config.require("sshPublicKey"),
    opts=opts,
)
pulumi.export("scaleSetName", cluster.runner.scale_set.name if cluster.runner.scale_set is not None else None)
pulumi.export("resourceGroupName", cluster.resource_group.name)
```

Run `pulumi up` to review and deploy. New role assignments can take time to apply; if the first secret write fails
with a permissions error, wait for the assignment to take effect and rerun it.

Use these feature settings on the provider you pass to the components. `data_plane_available=False` keeps storage
management on ARM: the provider's default Shared Key probes fail because this storage component disables shared keys.
The VMSS settings let Pulumi update and reimage existing workers automatically when needed. Components inherit your
provider; they do not replace it or change its authentication settings.

Result storage and ACR remain separate. Pass their IDs through `blob_container_ids` and `container_registry_id` when needed.
`Cluster` uses `enabled`, `min_replicas`, and `max_replicas`, matching the AWS/GCP high-level API.
Use it for new fleets; replacing an existing low-level component with it changes resource ownership.

Pass additional credentials with `secret_environment_variables={"SERVICE_API_KEY": config.require_secret("serviceApiKey")}`.
`Cluster` writes them to its Key Vault after creating the deployer's writer grant and gives the runner read access.
Values are fetched at startup, not placed in VM custom data; changing a value triggers a worker update through its
versioned secret URL. Keep `TILEBOX_API_KEY` in `tilebox_api_key`, and do not repeat keys in `environment_variables`.
Azure reserves `AZURE_CLIENT_ID` for managed identity. Additional secret keys must not differ only by case because
Key Vault secret names are case-insensitive.

For a private worker cache with seven-day expiry, add `cache=True, cache_expiration_days=7` to `Cluster`.
It creates a `worker-cache` container in the cluster's resource group, sets
`TILEBOX_WORKER_CACHE=az://<account>/worker-cache/jobs`, and grants its managed identity access to that container.
The cache and its expiry policy remain when `enabled=False` deletes the worker fleet.

Pass `cache=existing_storage` to reuse a private `azure.BlobStorage` instead. Keep its original resource group and
configure `expiration_days=7, expiration_prefix="jobs/"` on that component. Do not also set `TILEBOX_WORKER_CACHE`
or use the reserved `local-cache` key in `blob_container_ids`. Read the URI from `cluster.cache_uri`.
Moving an existing standalone cache to `cache=True` does not automatically adopt its resources.

## Use existing infrastructure

`azure.runner.AutoScalingCluster` accepts an existing resource group and subnet, and creates only the runner fleet,
identity, and grants. The existing `azure.AutoScalingCluster` import still works.

```python
from tilebox_iac.azure.runner import AutoScalingCluster

cluster = AutoScalingCluster(
    "runners",
    resource_group_name=resource_group_name,
    location=location,
    subnet_id=subnet_id,
    ssh_public_key=ssh_public_key,
    environment_variables={"TILEBOX_API_KEY": api_key_secret},
    opts=opts,
)
```

Here `api_key_secret` is an `azure.Secret` in your existing Key Vault. Subnets need outbound access to pull images
and reach Tilebox and Azure APIs. The same provider settings apply to both levels.

The default cluster uses regular `Standard_D8s_v5` VMs, 40-GiB disks, and one to two replicas. Set `instance_type`,
`root_volume_size_gb`, and the replica bounds for your workload. Set `spot=True` to use Spot instances.
The default image is `ghcr.io/tilebox/runner:latest`. Set `runner_image` only for a custom image.
The image controls the container command and user.

For a private Azure Container Registry, pass both `container_registry_id=registry.id` and
`container_registry_server=registry.login_server`, and set `runner_image` to an image in that registry.
Tags and immutable digests are supported. The library grants the VM identity `AcrPull` on that registry and logs
Docker in before each pull using IMDS and ACR OAuth. No Azure CLI or shared password is installed on the VM.
Docker credentials stay in a root-only runtime directory and are removed after the pull.

Create and build the registry outside this library with admin access disabled and registry RBAC permissions mode;
`AcrPull` does not apply to ABAC repository permissions mode. Supply the bare `*.azurecr.io` login hostname, without
an HTTPS prefix or path. This integration supports Azure public cloud. Omit both inputs for anonymous pulls.
Keep the registry's authentication-as-ARM policy enabled: the IMDS exchange uses an ARM-audience token.

## Storage and secrets

Runners use their managed identity to access the supplied blob containers and fetch Key Vault secrets at startup.
Use `azure.Secret` for credentials: passing strings directly puts their values in VM startup configuration.
For other Azure permissions, pass `roles={"data-reader": {"scope": resource_id, "role_definition_name": "..."}}`.
Keep the keys in `roles` and `blob_container_ids` stable when adding or removing permissions. They name the grants,
so inserting a permission does not rename existing assignments. This replaces the earlier unreleased list API;
existing deployed list-based grants need Pulumi aliases or a state migration before changing their names.

Storage requires HTTPS and defaults to private access. Set `public_read=True` on `BlobStorage` to let anyone with a
blob URL read its contents without authentication. This exposes existing and future blobs in that container;
anonymous listing and writes remain disabled. Writes still require an authorized identity, and shared keys stay disabled.
`protect=True` prevents Pulumi from deleting the account or container in either mode. This option does not change ACR access.
Optional `expiration_days` deletes matching current block blobs, old versions, and snapshots; `expiration_prefix`
is relative to the container. Seven-day soft-delete retention remains enabled, so physical removal can happen later.
This component manages the account's lifecycle policy when expiry is set; do not declare a second `ManagementPolicy`
for the same account. Lifecycle deletion still applies to storage protected from Pulumi deletion.
For workers outside Azure, create only `BlobStorage` and grant their Azure identity Storage Blob Data Contributor
on `storage.container_resource_id`. Authenticate with the Azure SDK's `DefaultAzureCredential`.

## Instance health

Systemd restarts failed containers. Azure's Application Health extension checks whether the runner container is
running through a local HTTP endpoint on `127.0.0.1:8080/health`. No inbound network access is needed. Three consecutive
failed probes, taken 30 seconds apart, mark the VM unhealthy. The 90-second probe settling period is below the
extension's 120-second limit. Azure replaces unhealthy instances using the current scale-set configuration,
with a separate 30-minute repair grace period after instance creation or updates complete.
The check tests container state, not task progress or Tilebox connectivity.

Repairs are enabled by default. For an existing fleet, first deploy with `auto_healing_enabled=False` and let Pulumi
update and reimage its instances. Once every instance shows **Healthy** in the Azure portal's
scale-set **Instances** page, set `auto_healing_enabled=True` and deploy again.

## Scaling and updates

CPU autoscaling keeps the cluster between `min_replicas_config` and `max_replicas_config`. Enabled clusters need
at least one VM. Tilebox automatically retries tasks after
[runner crashes](https://docs.tilebox.com/workflows/concepts/runners#runner-crashes).

Set `enabled=False` on `Cluster`, or `cluster_enabled=False` on `AutoScalingCluster`, to delete the autoscaler
and scale set, including its VMs and boot disks. Pulumi deletes the autoscaler before the scale set.
The resource group, network, identity, access grants, secrets, and cache remain. Re-enabling creates a new fleet.
`runner.scale_set` is `None` while disabled.

After changing an image reference or startup settings, `pulumi up` updates the scale-set model and the provider
updates and reimages existing instances when required. Azure's upgrade mode remains `Manual` because the provider
performs this work. With the provider settings above, no separate `az vmss` commands are needed.

Reimaging clears local files and interrupts running tasks; Tilebox retries those tasks. Store results outside the VM.
This is not a task-draining or health-gated, one-at-a-time rollout, and several workers may restart together.
Use a new image tag or digest for each build so Pulumi detects the change.
