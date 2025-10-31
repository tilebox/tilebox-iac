# IaC for a auto-scaling cluster utilizing GCP Spot instances

This library provides the following [Pulumi](https://www.pulumi.com/) resources:

- A `LocalBuildTrigger` ressource that runs a local command to build a Docker image on code changes and pushes it to a Google Artifact Registry repository
- A `Secret` resource to manage GCP secrets
- A `AutoScalingGCPCluster` resource to manage the auto-scaling cluster
- A `GCPNetwork` resource to manage networking within the Cluster, optionally enabling Private Google Access (PGA) and a router for outbound internet access

## Dev setup

```bash
pre-commit install
uv sync
```
