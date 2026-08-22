# AWS quickstart

This example calls the high-level AWS module. It creates a public VPC, two public subnets, an outbound-only security
group, a Secrets Manager secret, and an autoscaling runner fleet.

This stack can run production Tilebox workloads. Runner instances receive public IPv4 addresses. The module does not
create private subnets, NAT gateways, VPC endpoints, organization controls, AWS log aggregation, or customer-specific
security policies. Use [`aws/runner`](../../../modules/aws/runner) with existing infrastructure.

With AWS credentials configured, run:

```bash
cd examples/aws/quickstart
export TF_VAR_tilebox_api_key='replace-with-your-api-key'
tofu init
tofu apply
```

The region defaults to `us-west-2`, the default region for geospatial datasets in the AWS Open Data Sponsorship
Program. Set `TF_VAR_region` to override it. To select a non-default Tilebox cluster or customize runner capacity, call
the high-level module directly and set its optional inputs.

The API key is stored in Terraform/OpenTofu state. To keep the API key out of state, use the low-level module with an
existing secret.
