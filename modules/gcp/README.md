# Tilebox runner cluster for Google Cloud

This is the default, high-level Google Cloud module. It enables the required APIs and creates the minimal VPC,
subnetwork, Cloud Router/NAT, Secret Manager secret, and autoscaling runner fleet needed to start running Tilebox
workflows inside an existing project.

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/gcp?ref=v0.1.0"
  project_id      = "my-project"
  tilebox_api_key = var.tilebox_api_key
}
```

Configure Google Cloud credentials through the inherited provider or Application Default Credentials. The project must
exist and have billing enabled; the module intentionally does not create projects or organization-level infrastructure.

The API key is stored in Secret Manager and in Terraform/OpenTofu state. Protect the state appropriately. Users with
stricter networking, state, or secret-management requirements should use [`modules/gcp/runner`](runner) with
their existing infrastructure and secret identifiers.
