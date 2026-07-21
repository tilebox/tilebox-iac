# Repository guidance

## Project overview

Tilebox IaC is a Python Pulumi library for autoscaling Tilebox runner clusters on AWS and GCP. Cloud-specific
components live under `tilebox_iac/aws` and `tilebox_iac/gcp`.

## Shared runner contract

- Keep `ghcr.io/tilebox/runner:latest` as the built-in image for every provider.
- Consume the official image anonymously. Do not add image builders, publishing, or registry resources to this library.
- Allow callers to supply a prebuilt image through `runner_image` and use provider-native authentication for private
  ECR, GCR, or Artifact Registry images.
- Require `TILEBOX_API_KEY`. Treat `TILEBOX_CLUSTER` as optional so the account's default cluster remains usable.
- Pass additional runner settings through `environment_variables`; do not add provider-specific runner commands.
- Default root volumes to 40 GiB, keep the size configurable through `root_volume_size_gb`, and delete boot volumes
  with their instances.
- Keep cloud-init templates responsible for pulling and starting the image. The image entrypoint owns the runner
  command and lifecycle.

## Reliability contract

- AWS instances self-report persistent container failures to their Auto Scaling Group. Keep the IAM permission scoped
  to the component's ASG name and account, region, and partition.
- GCP uses a regional HTTP health check on port 8080. Restrict both VPC and COS guest-firewall access to Google Cloud's
  documented health-check ranges.
- GCP automatic healing must remain opt-in by default. Existing fleets first need a complete template rollout with
  `auto_healing_enabled=False`; enable healing in a separate deployment only after all instances report healthy.
- Health checks currently test whether the Docker container is running. Do not describe them as application-liveness
  or Tilebox-connectivity checks.
- Container-Optimized OS mounts `/usr` read-only and generic `/var` and `/tmp` as non-executable. Put executable
  cloud-init helpers under `/etc` and recreate stateless configuration on every boot.

## Scope

AWS and GCP are the supported providers on `main`. Azure support is deferred and should be developed separately rather
than mixed into AWS/GCP changes.

## Development

- Install dependencies with `uv sync`.
- Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright .`, and `uv lock --check` before merging.
- Follow the existing `ComponentResource`, `TypedDict`, and Jinja2 cloud-init patterns.
- Prefer provider-explicit resources and provider-inheriting invokes so aliased providers and explicit projects work.
- Keep changes provider-local unless they intentionally update the shared contract in `tilebox_iac/release_runner.py`.
