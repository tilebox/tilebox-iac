# Tilebox runner infrastructure

Terraform and OpenTofu modules for autoscaling [Tilebox](https://tilebox.com/) runner clusters on AWS, Google Cloud,
and CREODIAS (CloudFerro Managed Kubernetes).

The modules are designed to fit into an existing environment. AWS consumes subnet IDs, GCP consumes an existing
project/network/subnetwork, and CREODIAS consumes optional shared network IDs. They do not create or take ownership of
a customer's landing zone. Small greenfield examples are included for evaluation and disposable deployments only.

## Modules

| Module | Creates | Existing infrastructure it consumes |
| --- | --- | --- |
| [`modules/aws`](modules/aws) | Spot EC2 Auto Scaling Group, launch template, autoscaler, and optional workload identity | Subnets and optional security groups |
| [`modules/gcp`](modules/gcp) | Spot regional MIG, instance template, autoscaler, health check, and optional workload identity | Project, VPC network, and regional subnetwork |
| [`modules/creodias`](modules/creodias) | CloudFerro Managed Kubernetes cluster and autoscaled runner worker pool | Optional shared OpenStack network IDs |
| [`modules/kubernetes-runner`](modules/kubernetes-runner) | Runner Deployment, Secret, ServiceAccount, and HPA | An existing Kubernetes cluster and provider configuration |

Every provider uses `ghcr.io/tilebox/runner:latest` by default. The image is pulled anonymously and this repository
does not build, publish, or mirror it. Set `runner_image` to use a prebuilt custom image and configure the provider's
native registry authentication and workload permissions separately.

## Get started

Start with the example matching your environment:

- [AWS with existing infrastructure](examples/aws/existing-infrastructure)
- [GCP with existing infrastructure](examples/gcp/existing-infrastructure)
- [CREODIAS cluster and runner](examples/creodias)
- [Disposable AWS greenfield example](examples/aws/greenfield)
- [Disposable GCP greenfield example](examples/gcp/greenfield)

Copy an example into your own root configuration, replace its local module source with a pinned release or commit,
and configure a remote backend. For example:

```hcl
module "runner" {
  source = "git::https://github.com/tilebox/tilebox-iac.git//modules/aws?ref=<release-or-commit>"

  # See examples/aws/existing-infrastructure for the required inputs.
}
```

Then initialize and validate with either OpenTofu or Terraform:

```bash
tofu init
tofu validate
tofu plan
```

Replace `tofu` with `terraform` to use Terraform. Root configurations should commit their generated provider lock
file. This multi-root module repository does not commit generated lock files.

## Runner configuration

`TILEBOX_API_KEY` is required. AWS and GCP receive a reference to an existing Secrets Manager or Secret Manager
secret, respectively, and fetch its latest value at boot. `TILEBOX_CLUSTER` is optional; omitting it uses the Tilebox
account's default cluster. Add other runner settings through `environment_variables`.

AWS and GCP default their boot volume to 40 GiB, expose `root_volume_size_gb`, and delete the volume with the instance.
Their health checks report whether the Docker container is running. They do not test Tilebox connectivity or task
execution.

AWS instances report persistent container failures to their own Auto Scaling Group. GCP exposes an HTTP endpoint on
port 8080 only to Google Cloud's documented health-check ranges and replaces persistently unhealthy VMs.

## CREODIAS deployment order

CREODIAS uses two root configurations and two independent states:

1. Apply [`examples/creodias/cluster`](examples/creodias/cluster) to create the managed cluster and worker pool.
2. Store its sensitive `kubeconfig` output outside Terraform remote state sharing, then apply
   [`examples/creodias/runner`](examples/creodias/runner) against the cluster.

Destroy in the reverse order: runner first, then cluster. This prevents Terraform from trying to configure Kubernetes
through a cluster created during the same plan and prevents a destroyed cluster from stranding Kubernetes resources in
state.

The runner HPA scales pods by CPU. Required one-runner-per-host anti-affinity leaves additional pods Pending, and the
CloudFerro cluster autoscaler responds by adding worker VMs. The Kubernetes Metrics API must be available for HPA.
CloudFerro does not document scale-to-zero, so the minimum runner/worker count is one and the managed control plane
remains allocated.

CloudFerro's provider is not mirrored by the OpenTofu registry. The CREODIAS module and example therefore retain this
exact, fully qualified requirement:

```hcl
source  = "registry.terraform.io/CloudFerro/cloudferro"
version = "= 0.1.3"
```

Configure the provider in the root module with `CLOUDFERRO_TOKEN` or its `token` argument. Child modules intentionally
inherit provider configurations from their callers.

## State and secrets

Treat every state file as sensitive and use an encrypted remote backend with narrowly scoped access:

- CREODIAS cluster state contains the sensitive kubeconfig.
- The Kubernetes runner state contains the runner environment, including `TILEBOX_API_KEY`.
- The disposable greenfield examples create secret versions, so their API-key values enter state.
- AWS and GCP existing-infrastructure examples pass only existing secret identifiers to their runner modules.

Never commit real `.tfvars`, state, plans, kubeconfigs, or credentials. The sample variable files contain placeholders
and are safe to copy before filling in locally.

## Compatibility and development

Modules require Terraform or OpenTofu 1.5 or newer. Provider constraints are documented in each module's
`versions.tf`; the CloudFerro provider is intentionally pinned exactly as described above.

Run formatting and validation before submitting changes:

```bash
tofu fmt -check -recursive .

find modules examples -name versions.tf -print | while read -r file; do
  directory=${file%/versions.tf}
  tofu -chdir="$directory" init -backend=false -input=false
  tofu -chdir="$directory" validate
  rm -rf "$directory/.terraform" "$directory/.terraform.lock.hcl"
done
```

Run the same commands with `terraform` to verify both engines.
