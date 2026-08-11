# Tilebox runner infrastructure module for CREODIAS

This module creates a CloudFerro Managed Kubernetes control plane and a dedicated autoscaled worker node pool through
`CloudFerro/cloudferro` 0.1.3. It does not configure the CloudFerro provider, create OpenStack networking, or deploy
Kubernetes workloads.

Use it with [`modules/kubernetes-runner`](../kubernetes-runner) in two separate root configurations and states:

1. Apply the CREODIAS cluster state.
2. Export its sensitive kubeconfig to a protected local path.
3. Configure the Kubernetes provider in the runner root and apply the runner state.

A reusable child module cannot safely configure the Kubernetes provider from a kubeconfig produced by a resource
inside that same module. The split also keeps provider credentials and lifecycle ownership explicit.

## Lifecycle order

- Apply: cluster state, then runner state.
- Destroy: runner state, then cluster state.
- Before replacing the cluster, remove or reconcile the runner state against the old API server.

Terraform/OpenTofu cannot create a dependency across these two states. Destroying the cluster first leaves Kubernetes
resources stranded in runner state.

The kubeconfig is stored in the cluster state even though it is marked sensitive. Treat the backend as a credential
store. Prefer a protected `kubeconfig_path` in the runner root over `terraform_remote_state`, which would copy the
credential into a second state without solving destroy ordering.

## Scaling behavior

The node pool is labeled and tainted with `tilebox.com/runner-pool = name`. The companion runner module places at most
one runner pod on each worker. Kubernetes HPA creates additional replicas when CPU exceeds its target; required pod
anti-affinity leaves extra replicas Pending, and CloudFerro's managed Cluster Autoscaler adds workers. HPA scale-down
eventually leaves empty nodes for removal.

This depends on Kubernetes resource metrics and the managed Cluster Autoscaler. Verify both in a live cluster. Provider
0.1.3 does not expose spot workers or configurable worker boot-volume sizes, and CREODIAS scale-to-zero is not
documented, so `min_replicas` must be at least one.

`shared_network_ids` accepts existing OpenStack networks only. Configure the required network RBAC before applying;
otherwise a pool can remain in `Awaiting Network`. The module does not take ownership of OpenStack networking.
