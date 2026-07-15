# AGENTS.md

## Project Overview

Tilebox IaC - reusable Pulumi components for auto-scaling Tilebox runner clusters on AWS, Azure, and GCP.

Clusters use the public `ghcr.io/tilebox/runner:latest` image. This repository consumes that image but does not build or publish runner images. Custom images are outside this library's scope.

## Commands

- **Install dependencies**: `uv sync`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type check**: `pyright`
- **Pulumi preview**: `pulumi preview`
- **Pulumi deploy**: `pulumi up`

## Architecture

This is a Pulumi Python library providing reusable infrastructure components, organized into cloud-specific submodules:

### Package Structure

```
tilebox_iac/
├── __init__.py          # Exports aws, azure, and gcp submodules
├── release_runner.py    # Official GHCR runner image default
├── aws/                 # Amazon Web Services components
│   ├── __init__.py
│   ├── auto_scaling_cluster.py
│   ├── cloud-init.yaml
│   ├── iam_role.py
│   ├── network.py
│   └── secrets.py
├── azure/               # Microsoft Azure components
│   ├── __init__.py
│   ├── auto_scaling_cluster.py
│   ├── cloud-init.yaml
│   ├── identity.py
│   ├── network.py
│   └── secrets.py
└── gcp/                 # Google Cloud Platform components
    ├── __init__.py
    ├── auto_scaling_cluster.py
    ├── cloud-init.yaml
    ├── network.py
    ├── secrets.py
    └── service_account.py
```

### GCP Components (`tilebox_iac.gcp`)

- `AutoScalingCluster` - Managed Instance Group with Spot VMs and CPU-based autoscaling
- `Network` - VPC with Private Google Access and optional NAT Gateway
- `ServiceAccount` - GCP IAM service accounts with role bindings
- `Secret` - GCP Secret Manager wrapper

### AWS Components (`tilebox_iac.aws`)

- `AutoScalingCluster` - Auto Scaling Group with Spot instances and a Launch Template
- `Network` - VPC with private subnets, optional NAT Gateway, and S3 VPC Gateway Endpoint
- `IAMRole` - IAM roles with instance profiles, bucket policies, secrets access
- `Secret` - AWS Secrets Manager wrapper

### Azure Components (`tilebox_iac.azure`)

- `AutoScalingCluster` - Virtual Machine Scale Set with CPU-based autoscaling and optional Spot instances
- `Network` - VNet with a private subnet and optional NAT Gateway
- `ManagedIdentity` - Azure managed identity with role assignments
- `Secret` - Azure Key Vault secret wrapper

## Usage

```python
from tilebox_iac import gcp

runner_environment = {
    "TILEBOX_API_KEY": tilebox_api_key_secret,
}

cluster = gcp.AutoScalingCluster(
    "my-cluster",
    environment_variables=runner_environment,
    ...,
)
```

AWS, Azure, and GCP use the same runner image and environment variable contract. `TILEBOX_API_KEY` is required; `TILEBOX_CLUSTER` is optional and defaults to the account's default cluster. In the upstream Tilebox repository, keep `ghcr.io/tilebox/runner:latest` as the built-in image and do not add image configuration, image builders, publishing, or private registry authentication. Forks may customize the image behavior for their own deployments.

## Code Style

- Use `ComponentResource` pattern for Pulumi components
- Use `TypedDict` for configuration dictionaries
- Use Jinja2 for cloud-init templates
- Follow ruff ALL rules (see pyproject.toml for ignored rules)
- Use type hints everywhere
- Import order: stdlib, blank line, external, blank line, internal (enforced by ruff isort)
- Format with ruff format

## Key Patterns

### ComponentResource Structure
```python
class MyComponent(ComponentResource):
    def __init__(self, name: str, ..., opts: ResourceOptions | None = None) -> None:
        super().__init__("tilebox:cloud:ComponentName", name, opts=opts)
        # Create resources with ResourceOptions(parent=self)
        self.register_outputs({...})
```

### TypedDict for Configs
```python
class MyConfigDict(TypedDict):
    required_field: str
    optional_field: NotRequired[str]
```

### Cloud-init Templates
- GCP: `gcp/cloud-init.yaml` - Uses GCP metadata server for secrets
- AWS: `aws/cloud-init.yaml` - Uses AWS CLI/IMDS for secrets
- Azure: `azure/cloud-init.yaml` - Uses a managed identity to fetch Key Vault secrets
- All templates anonymously pull the official GHCR runner image
- AWS self-reports persistent runner failures; GCP and Azure use provider health probes

## Dependencies

- `pulumi` - Core Pulumi SDK
- `pulumi-gcp` - GCP provider
- `pulumi-aws` - AWS provider
- `pulumi-azure-native` - Azure provider
- `jinja2` - Cloud-init templating
