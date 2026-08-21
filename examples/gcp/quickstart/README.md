# Google Cloud quickstart

This primary onboarding path invokes the high-level GCP module, which enables the required APIs in an existing project
and creates a small VPC, regional subnetwork, Cloud Router/NAT, Secret Manager secret, and autoscaling runner fleet.

It is a minimal stack rather than a production landing zone. It does not create a GCP project, organization IAM,
Shared VPC, centralized logging, budgets, policy controls, or customer-specific security configuration. API services
remain enabled after destroy. Use the low-level [`gcp/runner`](../../../modules/gcp/runner) module to integrate with
existing infrastructure.

With Google Cloud credentials configured and billing enabled on the project, the complete quickstart is:

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

The API key is stored in Terraform/OpenTofu state. Protect the state appropriately; use the low-level module with an
externally managed secret when stricter secret management is required.
