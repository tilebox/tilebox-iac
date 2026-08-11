# AWS greenfield example

This optional example creates a small public VPC, two public subnets, outbound-only security group, and Secrets Manager
secret before invoking the same AWS runner module used by the existing-infrastructure example.

It is intended for evaluation, not as a production landing zone. Runner instances receive public IPv4 addresses; the
example does not provide private subnets, NAT gateways, VPC endpoints, organization controls, centralized logging, or
customer-specific security policy.

Supply the API key without committing it:

```bash
cp terraform.tfvars.example terraform.tfvars
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

The secret payload is stored in Terraform/OpenTofu state because the example creates a secret version. Protect the
state backend. The secret uses immediate deletion on destroy, which is suitable only for a disposable example.
