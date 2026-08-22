# Tilebox runner cluster for AWS

This high-level AWS module creates a VPC, two public subnets, internet routing, an outbound-only security group, a
Secrets Manager secret, and an autoscaling runner fleet.

```hcl
module "tilebox" {
  source          = "git::https://github.com/tilebox/tilebox-iac.git//modules/aws?ref=v0.1.0"
  tilebox_api_key = var.tilebox_api_key
}
```

Configure the AWS provider in the root or through standard AWS environment variables. Runner instances receive public
IPv4 addresses but no inbound security-group rules. The module creates only the listed resources. It does not configure
other account networking, security, or organization settings.

The API key is stored in Secrets Manager and in Terraform/OpenTofu state. Use [`modules/aws/runner`](runner) with
existing infrastructure and a secret identifier to keep the API key out of state.
