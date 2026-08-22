# Google Cloud quickstart

This example calls the high-level GCP module. It enables the required APIs in an existing project and creates a VPC,
regional subnetwork, Cloud Router/NAT, Secret Manager secret, and autoscaling runner fleet.

This stack can run production Tilebox workloads. It does not create a GCP project, organization IAM, Shared VPC, Google
Cloud log aggregation, budgets, policy controls, or customer-specific security settings. API services remain enabled
after destroy. Use [`gcp/runner`](../../../modules/gcp/runner) with existing infrastructure.

With Google Cloud credentials configured and billing enabled on the project, run:

```bash
cd examples/gcp/quickstart
export TF_VAR_project_id='replace-with-your-project-id'
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

The region defaults to `europe-west1`. Copy `terraform.tfvars.example` only to set the project and optionally override
the region. To select a non-default Tilebox cluster or customize runner capacity, call the high-level module directly
and set its optional inputs.

The API key is stored in Terraform/OpenTofu state. To keep the API key out of state, use the low-level module with an
existing secret.
