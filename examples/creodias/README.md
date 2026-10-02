# CREODIAS runners

Use two local Pulumi stacks: `cluster` creates CloudFerro infrastructure; `runner` connects to its Kubernetes API.
Install Pulumi CLI 3.264.0 or newer. The library uses CloudFerro provider 0.1.3 through Pulumi's provider bridge;
no Terraform or OpenTofu CLI is needed.

Copy each directory into a separate project and follow the [common setup](../README.md). In the cluster project, set
your CloudFerro region, API token, and an available Kubernetes version:

```bash
pulumi config set region WAW4-1
pulumi config set --secret token
pulumi config set kubernetesVersion 1.34.9
pulumi up
pulumi stack output kubeconfig --show-secrets > ../kubeconfig
chmod 600 ../kubeconfig
```

The example uses one control-plane node; `creodias.Cluster` defaults to three. Check version and flavor availability
in your region. `shared_network_ids` accepts existing OpenStack networks. CloudFerro provider 0.1.3 does not expose
Spot workers.

In the runner project:

```bash
pulumi config set kubeconfigPath ../kubeconfig
pulumi config set --secret tileboxApiKey
pulumi up
kubectl --kubeconfig ../kubeconfig get --raw /apis/metrics.k8s.io/v1beta1/nodes
```

CPU autoscaling needs the Metrics API. The HPA adds pods; if all workers are occupied, CloudFerro adds nodes for the
pending pods. The shared name `runners` selects the pool labelled `tilebox.com/runner-pool=runners`, with at most one
runner per node. CPU targets are fractions of `runner_cpu_request`. No CPU or memory limits are imposed.

Destroy the runner stack before destroying or replacing the cluster so Pulumi can still reach its Kubernetes API.
For another Kubernetes cluster, use the runner project alone and label its worker nodes with the same pool label.
