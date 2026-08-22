# Tilebox runner infrastructure

Terraform and OpenTofu modules for autoscaling [Tilebox](https://tilebox.com/) runner clusters on AWS, Google Cloud,
and CREODIAS (CloudFerro Managed Kubernetes).

Most users should use the high-level AWS or GCP module. Each creates networking, an API-key secret, and an autoscaling
runner fleet in the caller's cloud account or project. Use the corresponding low-level runner module with existing
networking and secrets.

## Modules

| Module | Layer | Creates or consumes |
| --- | --- | --- |
| [`modules/aws`](modules/aws) | High-level default | VPC, public subnets, managed secret, and Spot runner fleet |
| [`modules/aws/runner`](modules/aws/runner) | Low-level | Runner fleet using existing subnets, security groups, and secret identifiers |
| [`modules/gcp`](modules/gcp) | High-level default | APIs, VPC/NAT, managed secret, and auto-healed Spot runner fleet inside an existing project |
| [`modules/gcp/runner`](modules/gcp/runner) | Low-level | Runner fleet using an existing project, VPC, subnetwork, and secret identifiers |
| [`modules/creodias`](modules/creodias) | Cluster | CloudFerro Managed Kubernetes cluster and autoscaled runner worker pool, optionally using shared network IDs |
| [`modules/kubernetes-runner`](modules/kubernetes-runner) | Workload | Runner Deployment, Secret, ServiceAccount, and HPA on an existing Kubernetes cluster |

Every provider uses `ghcr.io/tilebox/runner:latest` by default. The image is pulled anonymously and this repository
does not build, publish, or mirror it. Set `runner_image` to use a prebuilt custom image. Configure registry
authentication and image-pull permissions in the cloud provider.

## Quickstart

AWS requires configured provider credentials and a Tilebox API key. The complete module call is:

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/aws?ref=v0.1.0"
  tilebox_api_key = var.tilebox_api_key
}
```

The ready-to-run example wraps that call with an AWS provider:

```bash
cd examples/aws/quickstart
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

Google Cloud additionally needs the ID of an existing project with billing enabled:

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/gcp?ref=v0.1.0"
  project_id      = "my-project"
  tilebox_api_key = var.tilebox_api_key
}
```

The ready-to-run example is applied the same way:

```bash
cd examples/gcp/quickstart
export TF_VAR_project_id='replace-with-your-project-id'
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init && tofu apply
```

Both high-level modules create only the networking, secret, and compute resources required by the runner fleet. They do
not configure other account or project networking, security, or organization settings. Each stack is created by one
`terraform apply` or `tofu apply`.

To use existing networking and secrets, start with:

- [AWS with existing infrastructure](examples/aws/existing-infrastructure)
- [GCP with existing infrastructure](examples/gcp/existing-infrastructure)
- [CREODIAS cluster and runner](examples/creodias)

Copy an example into your own root configuration, replace its local module source with a pinned release or commit,
and configure a remote backend. For example:

```hcl
module "runner" {
  source = "git::https://github.com/tilebox/tilebox-iac.git//modules/aws/runner?ref=<release-or-commit>"

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

`TILEBOX_API_KEY` is required. The high-level modules create its cloud secret; the low-level modules accept references
to existing Secrets Manager or Secret Manager secrets. Runner instances fetch the secret value at boot.
`TILEBOX_CLUSTER` is optional; omitting it uses the Tilebox account's default cluster. Add it and other runner settings
through `environment_variables`.

AWS and GCP use a 60 GiB boot volume by default. Set `root_volume_size_gb` to change the size. The volume is deleted
with the instance. Their health checks report whether the Docker container is running. They do not test Tilebox
connectivity or task execution.

AWS instances report persistent container failures to their own Auto Scaling Group. GCP exposes an HTTP endpoint on
port 8080 only to Google Cloud's documented health-check ranges and replaces persistently unhealthy VMs.

## CREODIAS deployment order

CREODIAS uses two root configurations and two independent states:

1. Apply [`examples/creodias/cluster`](examples/creodias/cluster) to create the managed cluster and worker pool.
2. Write its sensitive `kubeconfig` output to a local file with restricted permissions, then apply
   [`examples/creodias/runner`](examples/creodias/runner) to the cluster.

Destroy in the reverse order: runner first, then cluster. Terraform cannot configure Kubernetes through a cluster
created during the same plan. If the cluster is destroyed first, the runner state still records Kubernetes resources
that Terraform can no longer delete.

The runner HPA scales pods by CPU. Required one-runner-per-host anti-affinity leaves additional pods Pending, and the
CloudFerro cluster autoscaler responds by adding worker VMs. The Kubernetes Metrics API must be available for HPA.
CloudFerro does not document scale-to-zero, so the minimum runner/worker count is one and the managed control plane
remains allocated.

CloudFerro's provider is not mirrored by the OpenTofu registry. The CREODIAS module and example use this source and
version:

```hcl
source  = "registry.terraform.io/CloudFerro/cloudferro"
version = "= 0.1.3"
```

Configure the provider in the root module with `CLOUDFERRO_TOKEN` or its `token` argument. Child modules inherit the
provider configuration from the root module.

## State and secrets

Treat every state file as sensitive. Encrypt the remote backend and grant access only to the users and services that
need it:

- The high-level AWS and GCP modules manage the API-key secret payload, so its value enters state. To keep the API key
  out of state, use a low-level module with an existing secret.
- CREODIAS cluster state contains the sensitive kubeconfig.
- The Kubernetes runner state contains the runner environment, including `TILEBOX_API_KEY`.
- AWS and GCP existing-infrastructure examples pass only existing secret identifiers to their runner modules.

Never commit real `.tfvars`, state, plans, kubeconfigs, or credentials. The sample variable files contain placeholders
and are safe to copy before filling in locally.

## Compatibility and development

Modules require Terraform or OpenTofu 1.5 or newer. Provider constraints are documented in each module's
`versions.tf`; the CloudFerro provider is pinned as described above.

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
