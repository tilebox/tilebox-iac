# AWS quickstart

This primary onboarding path invokes the high-level AWS module, which creates a small public VPC, two public subnets,
an outbound-only security group, a Secrets Manager secret, and the autoscaling runner fleet.

It is a minimal stack rather than a production landing zone. Runner instances receive public IPv4 addresses; the
module does not provide private subnets, NAT gateways, VPC endpoints, organization controls, centralized logging, or
customer-specific security policy. Use the low-level [`aws-runner`](../../../modules/aws-runner) module to integrate
with existing infrastructure.

With AWS credentials configured, the complete quickstart is:

```bash
cd examples/aws/quickstart
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

The region defaults to `eu-west-1`. Copy `terraform.tfvars.example` only to override it. To select a non-default
Tilebox cluster or customize runner capacity, call the high-level module directly and set its optional inputs.

The API key is stored in Terraform/OpenTofu state. Protect the state appropriately; use the low-level module with an
externally managed secret when stricter secret management is required.
