# IaC for a auto-scaling cluster utilizing GCP Spot instances

This [Pulumi](https://www.pulumi.com/) project provisions the following resources:

- A `LocalBuildTrigger` ressource that runs a local command to build a Docker image on code changes and pushes it to a Google Artifact Registry repository
- A `Secret` resource to manage GCP secrets
- A `AutoScalingGCPCluster` resource to manage the auto-scaling cluster

## Dev setup

```bash
pre-commit install
uv sync
```
