# Tilebox runner infrastructure module for CREODIAS

This module creates a CloudFerro Managed Kubernetes control plane and a dedicated autoscaled worker node pool through
`CloudFerro/cloudferro` 0.1.3. It does not configure the CloudFerro provider, create OpenStack networking, or deploy
Kubernetes workloads.

Use it with [`modules/kubernetes-runner`](../kubernetes-runner) in two separate root configurations and states:

1. Apply the CREODIAS cluster state.
2. Write its sensitive kubeconfig to a local file with restricted permissions.
3. Configure the Kubernetes provider in the runner root and apply the runner state.

A child module cannot configure the Kubernetes provider from a kubeconfig created during the same plan. Use separate
states so the cluster exists before the Kubernetes provider connects to it.

## Lifecycle order

- Apply: cluster state, then runner state.
- Destroy: runner state, then cluster state.
- Before replacing the cluster, destroy the runner resources while the old Kubernetes API server is available.

Terraform/OpenTofu cannot create a dependency across these two states. If the cluster is destroyed first, the runner
state still records Kubernetes resources that Terraform can no longer delete.

The kubeconfig is stored in the cluster state even though it is marked sensitive. Anyone who can read the state can
read the kubeconfig. Pass the path of a local file with restricted permissions to `kubeconfig_path` in the runner root.
Do not use `terraform_remote_state`; it copies the credential into a second state without enforcing destroy order.

## Scaling behavior

The node pool is labeled and tainted with `tilebox.com/runner-pool = name`. The Kubernetes runner module places at most
one runner pod on each worker. Kubernetes HPA creates additional replicas when CPU exceeds its target; required pod
anti-affinity leaves extra replicas Pending, and CloudFerro's managed Cluster Autoscaler adds workers. HPA scale-down
eventually leaves empty nodes for removal.

This depends on Kubernetes resource metrics and the managed Cluster Autoscaler. Verify both in a live cluster. Provider
0.1.3 does not expose spot workers or configurable worker boot-volume sizes, and CREODIAS scale-to-zero is not
documented, so `min_replicas` must be at least one.

`shared_network_ids` accepts existing OpenStack networks only. Configure the required network RBAC before applying;
otherwise a pool can remain in `Awaiting Network`. The module does not take ownership of OpenStack networking.
