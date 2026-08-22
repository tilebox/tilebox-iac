# Tilebox runner cluster for Google Cloud

This high-level Google Cloud module enables the required APIs and creates a VPC, subnetwork, Cloud Router/NAT, Secret
Manager secret, and autoscaling runner fleet in an existing project.

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/gcp?ref=v0.1.0"
  project_id      = "my-project"
  tilebox_api_key = var.tilebox_api_key
}
```

Configure Google Cloud credentials through the inherited provider or Application Default Credentials. The project must
exist and have billing enabled. The module does not create projects or organization-level resources.

The API key is stored in Secret Manager and in Terraform/OpenTofu state. Use [`modules/gcp/runner`](runner) with
existing infrastructure and a secret identifier to keep the API key out of state.
