# Tilebox infrastructure components

This Python library provides reusable [Pulumi](https://www.pulumi.com/) components for autoscaling Tilebox
runner clusters on AWS and Google Cloud. Both implementations use Spot instances, CPU-based autoscaling, and the
same runner image and environment configuration.

## Components

The `tilebox_iac.aws` and `tilebox_iac.gcp` modules each provide:

- `AutoScalingCluster` for runner compute and autoscaling
- `Network` for the cloud-specific network resources
- `Secret` for credentials stored in the provider's secret manager
- an IAM component for workload permissions: `IAMRole` on AWS and `ServiceAccount` on GCP

## Usage

This AWS example creates a network and a runner cluster using the official image:

```python
import pulumi

from tilebox_iac import aws

config = pulumi.Config()
aws_region = pulumi.Config("aws").require("region")

network = aws.Network("workflow-runners", aws_region=aws_region)

cluster = aws.AutoScalingCluster(
    "workflow-runners",
    instance_type="m7i.large",
    cpu_target=0.2,
    cluster_enabled=True,
    min_replicas_config=1,
    max_replicas_config=10,
    subnet_ids=[network.private_subnet_id],
    environment_variables={
        "TILEBOX_API_KEY": config.require_secret("tileboxApiKey"),
    },
)
```

Configure the API key before deploying:

```bash
pulumi config set --secret tileboxApiKey
pulumi up
```

## Runner configuration

Clusters pull `ghcr.io/tilebox/runner:latest` anonymously by default. This repository consumes the official image;
it does not build or publish runner images. The image owns the runner command and lifecycle.

Each cluster passes the configured `environment_variables` to the container:

- `TILEBOX_API_KEY` is required and may be a plain Pulumi input or a provider-specific `Secret`.
- `TILEBOX_CLUSTER` is optional. When omitted, the runner uses the account's default cluster.
- Additional runner environment variables use the same mapping.

AWS and GCP root disks default to 40 GiB. Set `root_volume_size_gb` to change the size. Boot volumes are deleted with
their instances.

### Custom images

Set `runner_image` to run a prebuilt custom image instead of the official image. Image building and publishing remain
outside this library.

- AWS authenticates to private ECR registries. Grant the instance role ECR pull permissions through `iam_config`.
- GCP authenticates to GCR and Artifact Registry. Grant the service account image-reader permissions through `roles`.
- Images in public registries are pulled anonymously.

## Instance health

Both providers restart the runner container through systemd and support replacing instances when the container remains
stopped. The health checks report whether the container is running; they do not test Tilebox API connectivity or task
execution.

AWS checks the container once per minute after startup. After ten consecutive failures, the instance marks itself
unhealthy so the Auto Scaling Group can replace it.

GCP exposes a health endpoint on port 8080 to Google Cloud health-check probes. Automatic MIG healing is disabled by
default to make upgrades safe. Roll out GCP self-healing in two deployments:

1. Deploy with `auto_healing_enabled=False`, wait for every instance to use the new template, and verify the health
   check reports all instances healthy.
2. Set `auto_healing_enabled=True` and deploy again to attach the auto-healing policy.

For Shared VPC deployments, pass both `health_check_network` and `health_check_network_project` so the firewall rule is
created in the host project.

## Development

```bash
uv sync
pre-commit install
```

Run the repository checks before submitting changes:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright .
uv lock --check
```
