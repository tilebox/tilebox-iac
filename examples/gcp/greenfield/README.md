# Google Cloud greenfield example

This optional example enables the required APIs in an existing project, creates a small VPC, regional subnetwork,
Cloud Router/NAT, and Secret Manager secret, then invokes the same GCP runner module used by the
existing-infrastructure example.

It is intended for evaluation, not as a production landing zone. It does not create a GCP project, organization IAM,
Shared VPC, centralized logging, budgets, policy controls, or customer-specific security configuration. API services
remain enabled after destroy.

Supply the API key without committing it:

```bash
cp terraform.tfvars.example terraform.tfvars
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

The secret payload is stored in Terraform/OpenTofu state because the example creates a secret version. Protect the
state backend.
