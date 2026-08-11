# Tilebox runner cluster for AWS

This is the default, high-level AWS module. It creates the minimal VPC, two public subnets, internet routing,
outbound-only security group, Secrets Manager secret, and autoscaling runner fleet needed to start running Tilebox
workflows.

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/aws?ref=v0.1.0"
  tilebox_api_key = var.tilebox_api_key
}
```

Configure the AWS provider in the root or through standard AWS environment variables. Runner instances receive public
IPv4 addresses but no inbound security-group rules. This is an opinionated starter stack, not a general AWS landing
zone.

The API key is stored in Secrets Manager and in Terraform/OpenTofu state. Protect the state appropriately. Users with
stricter networking, state, or secret-management requirements should use [`modules/aws-runner`](../aws-runner) with
their existing infrastructure and secret identifiers.
