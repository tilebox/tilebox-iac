# CREODIAS two-stage example

CREODIAS uses separate cluster and runner roots because the Kubernetes provider must be configured from a cluster that
already exists.

## Apply

1. Configure the CloudFerro Managed Kubernetes token without writing it to configuration:

   ```bash
   export CLOUDFERRO_TOKEN='replace-with-your-token'
   ```

2. Initialize and apply the cluster root:

   ```bash
   cd cluster
   cp terraform.tfvars.example terraform.tfvars
   tofu init
   tofu apply
   umask 077
   tofu output -raw kubeconfig > ../creodias-kubeconfig.yaml
   ```

3. Supply the Tilebox API key through the environment and apply the runner root:

   ```bash
   cd ../runner
   cp terraform.tfvars.example terraform.tfvars
   export TF_VAR_tilebox_api_key='replace-with-your-api-key'
   tofu init
   tofu apply
   ```

The kubeconfig and both state files contain credentials. Store them only in protected locations/backends and remove
the exported file when it is no longer needed.

## Destroy

Always destroy the runner root before the cluster root:

```bash
cd runner && tofu destroy
cd ../cluster && tofu destroy
```

Terraform/OpenTofu cannot enforce ordering across states. Destroying the cluster first prevents the Kubernetes provider
from removing workload resources and leaves them stranded in runner state.
