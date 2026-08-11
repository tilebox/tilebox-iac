# Tilebox runner module for AWS

This module deploys an autoscaling fleet of Spot EC2 instances that run the prebuilt Tilebox runner image. It uses
existing subnets and optional security groups; it does not create or manage a VPC, routing, NAT, secrets, or a customer
landing zone.

## What it creates

- an Amazon Linux 2023 launch template with a 40 GiB gp3 root volume by default;
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
Secret references are preferred: the VM fetches the latest SecretString on every systemd service start. Set
`rollout_marker` to a secret version ID when a rotation should create a new launch-template version and refresh the
fleet.

Plain environment values are embedded in EC2 user data and Terraform/OpenTofu state. Marking an input sensitive only
redacts CLI output; it does not remove data from state. Protect state accordingly.

## Operational notes

- Existing subnets need outbound access to package repositories, the image registry, Tilebox, AWS APIs, and Secrets
  Manager when configured.
- The default AMI lookup is x86_64. Pass `ami_id` for ARM instance types.
- CPU autoscaling cannot scale from zero, so `min_replicas` must be at least one while `enabled = true`.
- Setting `enabled = false` keeps the infrastructure while setting min/max/desired capacity to zero.
- Private ECR images use provider-native `aws ecr get-login-password`; the selected role still needs ECR pull
  permissions.
- Launch-template changes trigger a rolling instance refresh. The parity default allows zero healthy instances during
  a refresh, so a single-runner fleet may be briefly unavailable.

See [`examples/aws/existing-infrastructure`](../../examples/aws/existing-infrastructure) for the primary usage path.
