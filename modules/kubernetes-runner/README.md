# Tilebox Kubernetes runner module

This module deploys Tilebox runners to any existing Kubernetes cluster with the `hashicorp/kubernetes` provider. It
does not create or configure the cluster.

The module creates a namespace by default, an opaque environment Secret, a no-token ServiceAccount, a Deployment, and
an autoscaling/v2 HPA. The full environment mapping, including `TILEBOX_API_KEY`, is stored in Kubernetes and
Terraform/OpenTofu state. Anyone who can read the state can read the API key.

Runner nodes must have the label `tilebox.com/runner-pool=<name>`, where `<name>` is the module's `name` input. The
module also allows runner pods on nodes with the taint `tilebox.com/runner-pool=<name>:NoSchedule`. Pods without this
permission cannot be scheduled on those nodes. The module requires Kubernetes to place each runner on a separate node
so runners do not compete for the same CPU and memory. Extra HPA replicas remain Pending until matching nodes are
added. A cluster autoscaler can add those nodes.

The [CREODIAS example](../../examples/creodias) reuses this module. Its cluster root creates a worker pool with the
required label and taint, then its runner root applies this module to that cluster.

## Capacity configuration

- Set `runner_cpu_request` below the CPU available to pods on each runner node. For example, use `3500m` when about four
  CPUs are available.
- HPA CPU utilization is measured relative to that request.
- Each replica requires a separate node with the runner-pool label. When using a cluster autoscaler, do not set
  `max_replicas` higher than the maximum number of runner nodes.
- After CPU usage falls, HPA waits five minutes before reducing the runner pod count.
- The Deployment uses zero surge and one unavailable pod during updates so a rollout does not request capacity beyond
  the one-pod-per-worker limit. With one replica, no runner is available between the old pod stopping and its
  replacement starting.

Verify the cluster exposes CPU resource metrics before relying on HPA:

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top nodes
```

Kubernetes restarts exited containers; this module does not add an application-liveness or Tilebox-connectivity probe.
Set `image_pull_secret_names` to the names of existing private-registry credentials in the target namespace.
