# Low-level Tilebox runner module for AWS

This module deploys an autoscaling fleet of Spot EC2 instances that run the prebuilt Tilebox runner image. It uses
existing subnets and optional security groups; it does not create or manage a VPC, routing, NAT, secrets, organization
policies, or shared networking.

## What it creates

- an Amazon Linux 2023 launch template with a 60 GiB encrypted gp3 root volume by default;
- a Spot Auto Scaling Group with capacity rebalance and CPU target tracking;
- either a minimal workload IAM role and instance profile or mandatory policies on an existing role;
- systemd/cloud-init integration that pulls and restarts the runner container;
- a one-minute container-state check that marks an instance unhealthy after ten consecutive failures.

The health check only proves that Docker reports the runner container as running. It does not test Tilebox API
connectivity or task execution.

## Identity modes

By default, the module creates an EC2-assumable role and instance profile. To use an existing identity, set both
`iam_role_name` and `instance_profile_name`. The module attaches only its mandatory ASG-health and configured
Secrets Manager read policies. The caller remains responsible for the role trust policy and any S3 or private ECR
permissions.

## Secrets and state

`TILEBOX_API_KEY` is required in exactly one of `environment_variables` or `secret_environment_variables`.
Secret references are preferred: the VM fetches the latest SecretString on every systemd service start. Rotating a
secret changes its version but not its ARN, so Terraform cannot otherwise detect that the running VMs need replacement.
Set `rollout_marker` to the current secret version ID; changing it creates a new launch-template version and refreshes
the fleet. The high-level AWS module sets this automatically for its managed API key. For secrets encrypted with
customer-managed KMS keys, pass the key ARNs through `secret_kms_key_arns` and ensure their key policies permit the
runner role. The module grants scoped `kms:Decrypt` through Secrets Manager only.

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

Start with [`modules/aws`](..) or [`examples/aws/quickstart`](../../../examples/aws/quickstart) for the minimal
batteries-included stack, or
[`examples/aws/existing-infrastructure`](../../../examples/aws/existing-infrastructure) to integrate the module into
customer-owned networking and secrets.
