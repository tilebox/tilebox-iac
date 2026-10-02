# Repository guidance

## Project overview

Tilebox IaC is a Python Pulumi library for Tilebox runners on AWS, GCP, Azure, and Kubernetes, including CREODIAS.
Examples use the open-source Pulumi CLI with local file state.

## Shared runner contract

- Keep `ghcr.io/tilebox/runner:latest` as the built-in image for every provider.
- Consume the official image anonymously. Do not add image builders, publishing, or registry resources to this library.
- Allow callers to supply a prebuilt image through `runner_image` and use provider-native authentication for private
  ECR, GCR, or Artifact Registry images.
- Require `TILEBOX_API_KEY`. Treat `TILEBOX_CLUSTER` as optional so the account's default cluster remains usable.
- Pass additional runner settings through `environment_variables`; do not add provider-specific runner commands.
- Default AWS/GCP root volumes to 60 GiB and Azure volumes to 40 GiB, keep `root_volume_size_gb` configurable, and delete boot volumes
  with their instances.
- Keep cloud-init templates responsible for pulling and starting the image. The image entrypoint owns the runner
  command and lifecycle.

## Reliability contract

- AWS instances self-report persistent container failures to their Auto Scaling Group. Keep the IAM permission scoped
  to the component's ASG name and account, region, and partition.
- GCP uses a regional HTTP health check on port 8080. Restrict both VPC and COS guest-firewall access to Google Cloud's
  documented health-check ranges.
- GCP low-level automatic healing remains opt-in; new high-level `Cluster` fleets enable it. Existing fleets need a complete template rollout with
  `auto_healing_enabled=False`; enable healing in a separate deployment only after all instances report healthy.
- Health checks currently test whether the Docker container is running. Do not describe them as application-liveness
  or Tilebox-connectivity checks.
- Container-Optimized OS mounts `/usr` read-only and generic `/var` and `/tmp` as non-executable. Put executable
  cloud-init helpers under `/etc` and recreate stateless configuration on every boot.

## Scope

Keep high-level AWS/GCP/Azure cluster components separate from runners that use existing infrastructure. Preserve old
`AutoScalingCluster` imports. CREODIAS cluster and Kubernetes workload examples use separate stacks.

## Development

- Install dependencies with `uv sync`.
- Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check .`, and `uv lock --check` before merging.
- Use `Output.apply(output, callback)` during resource construction to avoid ty's Pulumi method-binding issue
  ([astral-sh/ty#350](https://github.com/astral-sh/ty/issues/350)).
- Follow the existing `ComponentResource`, `TypedDict`, and Jinja2 cloud-init patterns.
- Prefer provider-explicit resources and provider-inheriting invokes so aliased providers and explicit projects work.
- Keep changes provider-local unless they intentionally update the shared contract in `tilebox_iac/release_runner.py`.
