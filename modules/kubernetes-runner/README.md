# Tilebox Kubernetes runner module

This module deploys Tilebox runners into an existing Kubernetes cluster through an inherited `hashicorp/kubernetes`
provider. It is paired with the CREODIAS module but contains no CloudFerro-specific API resources.

The module creates a namespace by default, an opaque environment Secret, a no-token ServiceAccount, a Deployment, and
an autoscaling/v2 HPA. The full environment mapping, including `TILEBOX_API_KEY`, is stored in Kubernetes and
Terraform/OpenTofu state. Anyone who can read the state can read the API key.

The workload targets worker nodes labeled `tilebox.com/runner-pool = name`, tolerates the matching `NoSchedule` taint,
and uses required hostname anti-affinity. This guarantees at most one matching runner pod per worker. Extra HPA
replicas remain Pending until the managed cluster autoscaler adds workers.

## Capacity configuration

- Set `runner_cpu_request` close to, but below, allocatable CPU on the selected worker flavor.
- HPA CPU utilization is measured relative to that request.
- Keep `min_replicas` and `max_replicas` equal to the CREODIAS node-pool bounds.
- The five-minute HPA scale-down delay prevents workers from being added and removed after short CPU changes.
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
