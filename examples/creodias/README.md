# CREODIAS two-stage example

CREODIAS uses separate cluster and runner roots because the Kubernetes provider must be configured from a cluster that
already exists.

## Apply

1. Configure the CloudFerro Managed Kubernetes token without writing it to configuration:

   ```bash
   export CLOUDFERRO_TOKEN='replace-with-your-token'
   ```

   When using the provider's explicit `host` input, also unset `CLOUDFERRO_REGION`; an environment-provided region and
   an explicit host are mutually exclusive.

2. Initialize and apply the cluster root:

   ```bash
   cd cluster
   cp terraform.tfvars.example terraform.tfvars
   tofu init
   tofu apply
   export CREODIAS_KUBECONFIG="$HOME/.kube/tilebox-creodias.yaml"
   install -d -m 0700 "$(dirname "$CREODIAS_KUBECONFIG")"
   umask 077
   tofu output -raw kubeconfig > "$CREODIAS_KUBECONFIG"
   ```

3. Supply the Tilebox API key through the environment and apply the runner root:

   ```bash
   cd ../runner
   cp terraform.tfvars.example terraform.tfvars
   export TF_VAR_kubeconfig_path="$CREODIAS_KUBECONFIG"
   export TF_VAR_tilebox_api_key='replace-with-your-api-key'
   tofu init
   tofu apply
   ```

The kubeconfig and both state files contain credentials. The commands above keep the kubeconfig outside the repository.
Store the kubeconfig and state where access is restricted, and delete the kubeconfig file when it is no longer needed.

## Destroy

Always destroy the runner root before the cluster root:

```bash
cd runner && tofu destroy
cd ../cluster && tofu destroy
```

Terraform/OpenTofu cannot enforce ordering across states. Destroying the cluster first prevents the Kubernetes provider
from removing workload resources. The runner state would still record resources in a cluster that no longer exists.
