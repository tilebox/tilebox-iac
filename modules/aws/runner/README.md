# Low-level Tilebox runner module for AWS

This module deploys an autoscaling fleet of Spot EC2 instances that run the prebuilt Tilebox runner image. It uses
existing subnets and optional security groups; it does not create or manage a VPC, routing, NAT, secrets, organization
policies, or shared networking.

## What it creates

- an Amazon Linux 2023 launch template with a 60 GiB encrypted gp3 root volume by default;
- a Spot Auto Scaling Group with capacity rebalance and CPU target tracking;
- an IAM role and instance profile, or the required policies on an existing role;
- cloud-init and systemd configuration that pulls and restarts the runner container;
- a one-minute container-state check that marks an instance unhealthy after ten consecutive failures.

The health check only proves that Docker reports the runner container as running. It does not test Tilebox API
connectivity or task execution.

## Identity modes

By default, the module creates an EC2-assumable role and instance profile. To use an existing identity, set both
`iam_role_name` and `instance_profile_name`. The module attaches policies to report instance health and read the
configured secrets. The existing role must trust EC2 and have any required S3 or private ECR permissions.

## Secrets and state

`TILEBOX_API_KEY` is required in exactly one of `environment_variables` or `secret_environment_variables`.
Use `secret_environment_variables` to keep secret values out of state. The VM fetches the latest SecretString on every
systemd service start. Rotating a secret changes its version but not its ARN, so Terraform cannot detect that the VMs
need replacement. Set `rollout_marker` to the current secret version ID. Changing it creates a launch-template version
and refreshes the fleet. The high-level AWS module sets this value for its managed API key. For secrets encrypted with
customer-managed KMS keys, pass the key ARNs through `secret_kms_key_arns` and allow the runner role in each key policy.
The module grants `kms:Decrypt` only through Secrets Manager.

Plain environment values are embedded in EC2 user data and Terraform/OpenTofu state. Marking an input sensitive only
redacts CLI output; it does not remove data from state. Protect state accordingly.

## Operational notes

- Existing subnets need outbound access to package repositories, the image registry, Tilebox, AWS APIs, and Secrets
  Manager when configured.
- Root volumes are encrypted with the account's default EBS KMS key.
- The default AMI lookup is x86_64. Pass `ami_id` for ARM instance types.
- CPU autoscaling cannot scale from zero, so `min_replicas` must be at least one while `enabled = true`.
- Setting `enabled = false` keeps the infrastructure while setting min/max/desired capacity to zero.
- If `runner_image` points to a private Amazon ECR repository, startup authenticates Docker by running
  `aws ecr get-login-password`. The EC2 IAM role must have permission to authenticate to ECR and pull the image.
- Launch-template changes trigger a rolling instance refresh. `min_healthy_percentage = 0` allows AWS to terminate the
  existing runner before its replacement is healthy, so a one-runner fleet can be temporarily unavailable.

Use [`modules/aws`](..) or [`examples/aws/quickstart`](../../../examples/aws/quickstart) to create networking and an
API-key secret. Use [`examples/aws/existing-infrastructure`](../../../examples/aws/existing-infrastructure) with
existing networking and secrets.
