# Tilebox runner infrastructure module for CREODIAS

This module creates a CloudFerro Managed Kubernetes control plane and a dedicated autoscaled worker node pool. It does not configure the CloudFerro provider, create OpenStack networking, or deploy
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

The module labels the worker pool for Tilebox runners but does not taint it. This allows managed components such as
metrics-server to run on a worker. The Kubernetes runner module uses the label to select this pool and runs no more than
one runner on each worker. When average CPU use rises above the configured target, Kubernetes starts more runners. If
every worker is occupied, a new runner waits while CloudFerro adds another worker. When CPU use falls, Kubernetes stops
extra runners and CloudFerro can remove empty workers.

CPU-based runner scaling requires the Kubernetes Metrics API. Worker scaling requires CloudFerro autoscaling, which
the module enables. Check both after creating the cluster. Provider 0.1.3 cannot create Spot workers.

`shared_network_ids` accepts existing OpenStack networks only. The module does not take ownership of OpenStack networking.
