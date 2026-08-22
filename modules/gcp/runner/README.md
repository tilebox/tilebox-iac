# Low-level Tilebox runner module for Google Cloud

This module deploys an autoscaling regional managed instance group of Spot VMs that run the prebuilt Tilebox runner
image. It uses an existing project, VPC, and regional subnetwork. It does not create or manage networking, Cloud
NAT, secrets, APIs, or other project-wide infrastructure.

## What it creates

- a Container-Optimized OS instance template with a 60 GiB auto-deleted boot disk by default;
- a regional managed instance group and CPU autoscaler;
- a runner service account, or the required roles on an existing service account;
- per-secret `roles/secretmanager.secretAccessor` grants and `roles/monitoring.metricWriter`;
- a regional HTTP health check on port 8080 plus a VPC firewall restricted to Google's probe ranges;
- cloud-init and systemd configuration that pulls and restarts the runner container.

The health endpoint only proves that Docker reports the runner container as running. It does not test Tilebox API
connectivity or task execution.

## Existing infrastructure and identity

Pass full network and subnetwork self-links to avoid resolving resources in the wrong project. For Shared VPC, set
`health_check_network_project_id` to the host project and `health_check_network_self_link` to the host network. The
credentials used by the inherited Google provider need permission in every referenced project.

By default, the module creates a service account. Set `service_account_email` to use an existing identity. The module
grants only the required Monitoring and Secret Manager roles. Configure Cloud Storage, Cloud Run, and Artifact Registry
roles separately.

## Secrets and state

`TILEBOX_API_KEY` is required in exactly one of `environment_variables` or `secret_environment_variables`.
Use `secret_environment_variables` to keep secret values out of state. Instances fetch `versions/latest` on every
service start. Plain environment values are embedded in instance metadata and Terraform/OpenTofu state. Sensitive
inputs are redacted, not omitted from state. Set a secret's optional `rollout_marker` to its version ID when rotation
should replace the runner VMs.

## Auto-healing

Automatic healing replaces VMs with persistent container failures. The module creates the health check, firewall, and
managed instance group configuration required for automatic healing.

The VPC firewall and COS guest firewall both allow port 8080 only from `130.211.0.0/22` and `35.191.0.0/16`.

## Operational notes

- Existing networking must provide outbound access to the configured registry, Google APIs, and Tilebox. No external
  IP is attached by default.
- CPU autoscaling cannot scale from zero, so `min_replicas` must be at least one while enabled.
- Disabled mode removes the autoscaler and resizes the managed instance group to zero. Re-enabling creates the
  autoscaler with `min_replicas` as its minimum size.
- GCR and Artifact Registry images use `docker-credential-gcr`; the runner service account still needs pull access.
- Executable COS helpers live under `/etc` because `/usr` is read-only and generic `/var` and `/tmp` mounts are
  non-executable.

Use [`modules/gcp`](..) or [`examples/gcp/quickstart`](../../../examples/gcp/quickstart) to create networking and an
API-key secret. Use [`examples/gcp/existing-infrastructure`](../../../examples/gcp/existing-infrastructure) with
existing networking and secrets.
