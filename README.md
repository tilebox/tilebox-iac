# Tilebox infrastructure components

This library provides reusable [Pulumi](https://www.pulumi.com/) components for running auto-scaling Tilebox runners on AWS, Azure, and GCP.

## Tilebox runner

A [Tilebox runner](https://docs.tilebox.com/workflows/concepts/runners) watches one cluster and executes Python workflow releases deployed to it. It downloads release artifacts, starts their Python runtimes with `uv`, and updates its task registrations when deployments change. Workflow releases can therefore be deployed or rolled back without rebuilding the runner image or restarting the runner fleet.

Tilebox publishes the runner image for Linux AMD64 and ARM64 at [`ghcr.io/tilebox/runner`](https://github.com/tilebox/runner/pkgs/container/runner). It includes `uv`, Python 3.12–3.14, Git, Git LFS, SSH support, and the matching Tilebox CLI release. Every cluster runs `ghcr.io/tilebox/runner:latest`; instances pull the current image when they start. The image starts the runner with:

```bash
tilebox runner start
```

The default runner requires no image configuration:

```python
from tilebox_iac import gcp

cluster = gcp.AutoScalingCluster(
    "tilebox-release-runners",
    environment_variables={
        "TILEBOX_API_KEY": tilebox_api_key_secret,
        "TILEBOX_CLUSTER": tilebox_cluster_slug,
    },
    # Cloud, network, machine, and scaling configuration omitted.
)
```

AWS, Azure, and GCP use the same official image and environment variable contract. This library consumes the Tilebox image but does not build or publish runner images.

## Deployment requirements

Each release runner deployment needs:

- A `TILEBOX_API_KEY`, injected through the cloud provider's secret manager rather than baked into the image.
- Optionally, a Tilebox cluster slug created with `tilebox cluster create`, passed as `TILEBOX_CLUSTER`. The [default cluster](https://docs.tilebox.com/workflows/concepts/clusters#default-cluster) is used when it is omitted.
- Optionally, a non-default Tilebox API endpoint passed as `TILEBOX_API_URL`.
- Outbound network access for the Tilebox API, workflow release artifacts, Python package indexes, and any data sources used by the workflows.
- Cloud credentials, network access, system libraries, disk space, and CPU or GPU hardware required by the deployed workflows.
- At least one workflow release deployed to the same cluster with `tilebox workflow deploy-release` before the runner can execute its tasks.

[Release runners](https://docs.tilebox.com/guides/workflows/deploy-to-your-compute) currently execute Python workflow projects. The runner image is shared across workflows; workflow code and Python dependencies belong in each immutable workflow release.

## Components

The `tilebox_iac.aws`, `tilebox_iac.azure`, and `tilebox_iac.gcp` modules provide cloud-specific auto-scaling clusters, networking, identities, and secret integrations.

## Dev setup

```bash
pre-commit install
uv sync
```
