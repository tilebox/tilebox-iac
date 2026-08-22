# Repository guidance

## Project overview

Tilebox IaC provides Terraform/OpenTofu modules for autoscaling Tilebox runner clusters on AWS, GCP, and CREODIAS.
Provider-specific modules live under `modules/`; deployable examples live under `examples/`.

## Module boundaries

- Keep the high-level AWS and GCP modules optimized for trivial adoption. They create minimal networking and managed
  secrets, then compose the corresponding low-level runner module.
- Keep the nested low-level runner modules (`modules/aws/runner` and `modules/gcp/runner`)
  existing-infrastructure-first. AWS consumes subnet IDs; GCP consumes project, network, and subnetwork inputs;
  CREODIAS consumes optional shared network IDs.
- Do not add project or organization creation, or manage infrastructure beyond what the runner fleet requires. The
  high-level modules own only the minimal provider-local infrastructure required by their runner fleet.
- Quickstart examples should remain thin roots that call the same high-level modules users call directly.
- Configure providers in root configurations. Child modules declare requirements and inherit provider configurations.
- Keep cloud-provider and Kubernetes resources for CREODIAS in separate modules and states. Apply cluster then runner;
  destroy runner then cluster. Do not pass kubeconfig through `terraform_remote_state`.
- Keep `registry.terraform.io/CloudFerro/cloudferro` pinned exactly to `0.1.3`; it is not mirrored by OpenTofu.

## Shared runner contract

- Keep `ghcr.io/tilebox/runner:latest` as the built-in image for every provider.
- Consume the official image anonymously. Do not add image builders, publishing, or registry resources.
- Allow callers to supply a prebuilt image through `runner_image` and use provider-native authentication for private
  ECR, GCR, Artifact Registry, or Kubernetes registry images.
- Require `TILEBOX_API_KEY`. Treat `TILEBOX_CLUSTER` as optional so the account's default cluster remains usable.
- Pass additional runner settings through `environment_variables`; do not add provider-specific runner commands.
- Use `us-west-2`, the AWS Open Data Sponsorship Program default for geospatial datasets, for AWS region defaults and
  example values.
- Default AWS and GCP boot volumes to 60 GiB, keep the size configurable through `root_volume_size_gb`, and delete boot
  volumes with their instances.
- Encrypt AWS root volumes with the account's default EBS KMS key, even when account-level EBS encryption is disabled.
- Keep startup templates responsible for pulling and starting the image. The image entrypoint owns runner lifecycle.

## Reliability contract

- Keep AWS `autoscaling:SetInstanceHealth` permission scoped to the module's ASG name, account, region, and partition.
- GCP uses a regional HTTP health check on port 8080. Restrict both VPC and COS guest-firewall access to Google's
  documented health-check ranges.
- Keep GCP automatic healing enabled for runner fleets.
- AWS and GCP health checks only test whether the Docker container is running. Do not describe them as application
  liveness, Tilebox connectivity, or task execution checks.
- Container-Optimized OS mounts `/usr` read-only and generic `/var` and `/tmp` as non-executable. Put executable startup
  helpers under `/etc` and recreate stateless configuration on every boot.
- Preserve the CREODIAS runner's required one-pod-per-host anti-affinity, dedicated runner pool label/taint, zero-surge
  rollout, HPA scale-down stabilization, and disabled service-account token.

## State and secrets

- Treat kubeconfig, Kubernetes Secret values, plans, variable files, and state as sensitive.
- Existing-infrastructure AWS and GCP modules should consume secret identifiers and fetch values at runtime.
- Note that high-level-module secret payloads enter state, without overwhelming the quickstart documentation.
- Never add real credentials, `.tfvars`, plans, state, or kubeconfigs to the repository.

## Documentation

- Use precise, plain technical English in README files. Name the resources and behavior directly. Avoid marketing
  language, idioms, and consulting jargon.

## Development

- Support Terraform and OpenTofu 1.5 or newer.
- Run `terraform fmt -check -recursive .` and `tofu fmt -check -recursive .`.
- Run `init -backend=false -input=false` and `validate` with both engines in every module and example root containing a
  `versions.tf` file.
- Remove generated `.terraform` directories and `.terraform.lock.hcl` files after local validation.
- Keep changes provider-local unless they intentionally update the shared runner contract.
