# Tilebox Kubernetes runner module

This module runs Tilebox runners on any existing Kubernetes cluster. Configure the `hashicorp/kubernetes` provider in
the root configuration. The module does not create the cluster.

By default, the module creates a Kubernetes namespace and starts Tilebox runners in it. It stores the runner settings,
including `TILEBOX_API_KEY`, in a Kubernetes Secret and in Terraform/OpenTofu state. Anyone who can read the state can
read the API key. The module does not give runner containers credentials for the Kubernetes API.

Runner nodes must have the label `tilebox.com/runner-pool=<name>`, where `<name>` is the module's `name` input. This
label tells Kubernetes where runners may run. You can reserve those nodes for runners by adding the taint
`tilebox.com/runner-pool=<name>:NoSchedule`. The module allows runners to use nodes with this taint; other workloads
must be configured separately to use them. Kubernetes runs no more than one Tilebox runner on each node so runners do
not compete for the same CPU and memory. When CPU use rises, Kubernetes can start more runners. New runners wait until
matching nodes are available. A cluster autoscaler can add those nodes.

The [CREODIAS example](../../examples/creodias) reuses this module. Its cluster configuration creates a worker pool for
the runners. Its runner configuration applies this module to that cluster.

## Capacity configuration

- Set `runner_cpu_request` below the CPU available to pods on each runner node. For example, use `3500m` when about four
  CPUs are available.
- Kubernetes compares each runner's CPU use with `runner_cpu_request` to decide when to start or stop runners.
- Each runner requires a separate node with the runner-pool label. When using a cluster autoscaler, do not set
  `max_replicas` higher than the maximum number of runner nodes.
- After CPU use falls, Kubernetes waits five minutes before reducing the runner pod count.
- During an update, Kubernetes stops one runner before starting its replacement and never starts an extra runner. With
  one replica, no runner is available during the replacement.

CPU autoscaling requires the Kubernetes Metrics API. Check it with:

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top nodes
```

Kubernetes restarts the runner container if it exits. The module does not check whether a runner can reach Tilebox or
process tasks. If `runner_image` points to a private image, set `image_pull_secret_names` to existing Kubernetes
credentials for that image.
