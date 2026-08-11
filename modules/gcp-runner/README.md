# Low-level Tilebox runner module for Google Cloud

This module deploys an autoscaling regional managed instance group of Spot VMs that run the prebuilt Tilebox runner
image. It consumes an existing project, VPC, and regional subnetwork. It does not create or manage networking, Cloud
NAT, secrets, APIs, or a customer landing zone.

## What it creates

- a Container-Optimized OS instance template with a 40 GiB auto-deleted boot disk by default;
- a regional managed instance group and CPU autoscaler;
- either a minimal runner service account or required grants for an existing service account;
- per-secret `roles/secretmanager.secretAccessor` grants and `roles/monitoring.metricWriter`;
- a regional HTTP health check on port 8080 plus a VPC firewall restricted to Google's probe ranges;
- cloud-init/systemd integration that pulls and restarts the runner container.

The health endpoint only proves that Docker reports the runner container as running. It does not test Tilebox API
connectivity or task execution.

## Existing infrastructure and identity

Pass full network and subnetwork self-links to avoid resolving resources in the wrong project. For Shared VPC, set
`health_check_network_project_id` to the host project and `health_check_network_self_link` to the host network. The
credentials used by the inherited Google provider need permission in every referenced project.

By default, the module creates a service account. Set `service_account_email` to use an existing identity. The module
manages only its mandatory Monitoring and Secret Manager memberships. The caller owns broader workload, Cloud Storage,
Cloud Run, and Artifact Registry permissions.

## Secrets and state

`TILEBOX_API_KEY` is required in exactly one of `environment_variables` or `secret_environment_variables`.
Secret references are preferred: instances fetch `versions/latest` on every service start. Plain environment values
are embedded in instance metadata and Terraform/OpenTofu state. Sensitive inputs are redacted, not omitted from state.
Set a secret's optional `rollout_marker` to its version ID when rotation should replace the runner VMs.

## Auto-healing

Automatic healing replaces VMs with persistent container failures. The module creates the health-capable template,
restricted firewall, health check, and MIG together.

The VPC firewall and COS guest firewall both allow port 8080 only from `130.211.0.0/22` and `35.191.0.0/16`.

## Operational notes

- Existing networking must provide outbound access to the configured registry, Google APIs, and Tilebox. No external
  IP is attached by default.
- CPU autoscaling cannot scale from zero, so `min_replicas` must be at least one while enabled.
- Disabled mode removes the autoscaler and explicitly resizes the managed instance group to zero. Re-enabling creates
  the autoscaler again with a positive minimum; the module does not claim CPU scale-from-zero.
- GCR and Artifact Registry images use `docker-credential-gcr`; the runner service account still needs pull access.
- Executable COS helpers live under `/etc` because `/usr` is read-only and generic `/var` and `/tmp` mounts are
  non-executable.

Start with [`modules/gcp`](../gcp) or [`examples/gcp/quickstart`](../../examples/gcp/quickstart) for the minimal
batteries-included stack, or
[`examples/gcp/existing-infrastructure`](../../examples/gcp/existing-infrastructure) to integrate the module into
customer-owned networking and secrets.
