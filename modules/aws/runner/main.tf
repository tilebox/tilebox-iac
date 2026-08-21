# Nested low-level compute module. Callers provide existing subnets and secret identifiers.
data "aws_partition" "current" {}

data "aws_caller_identity" "current" {}

data "aws_ami" "runner" {
  count = var.ami_id == null ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  create_identity = var.iam_role_name == null && var.instance_profile_name == null
  valid_identity  = local.create_identity || (var.iam_role_name != null && var.instance_profile_name != null)

  iam_role_name         = local.create_identity ? aws_iam_role.runner[0].name : coalesce(var.iam_role_name, "invalid")
  instance_profile_name = local.create_identity ? aws_iam_instance_profile.runner[0].name : coalesce(var.instance_profile_name, "invalid")

  effective_min_replicas = var.enabled ? var.min_replicas : 0
  effective_max_replicas = var.enabled ? var.max_replicas : 0

  registry_hostname = split("/", var.runner_image)[0]
  registry_parts    = split(".", local.registry_hostname)
  ecr_region = (
    length(local.registry_parts) > 3 &&
    local.registry_parts[1] == "dkr" &&
    local.registry_parts[2] == "ecr"
  ) ? local.registry_parts[3] : ""

  environment_file = base64encode(join("", [
    for name in sort(keys(var.environment_variables)) : "${name}=${var.environment_variables[name]}\n"
  ]))

  secret_arns = setunion(
    var.additional_secret_arns,
    toset([for secret in values(var.secret_environment_variables) : secret.secret_arn]),
  )

  region  = split(":", aws_launch_template.runner.arn)[3]
  asg_arn = "arn:${data.aws_partition.current.partition}:autoscaling:${local.region}:${data.aws_caller_identity.current.account_id}:autoScalingGroup:*:autoScalingGroupName/${var.name}"

  resource_tags = merge(var.tags, {
    Name = "${var.name}-instance"
  })

  cloud_init = templatefile("${path.module}/cloud-init.tftpl", {
    container_image              = var.runner_image
    ecr_region                   = local.ecr_region
    environment_file             = local.environment_file
    registry_hostname            = local.registry_hostname
    secret_environment_variables = var.secret_environment_variables
  })
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "runner" {
  count = local.create_identity ? 1 : 0

  name               = var.name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

data "aws_iam_role" "runner" {
  count = !local.create_identity && local.valid_identity ? 1 : 0
  name  = var.iam_role_name
}

resource "aws_iam_instance_profile" "runner" {
  count = local.create_identity ? 1 : 0

  name = var.name
  role = aws_iam_role.runner[0].name
  tags = var.tags
}

data "aws_iam_policy_document" "instance_health" {
  statement {
    sid       = "ReplacePersistentlyUnhealthyRunner"
    effect    = "Allow"
    actions   = ["autoscaling:SetInstanceHealth"]
    resources = [local.asg_arn]
  }
}

resource "aws_iam_role_policy" "instance_health" {
  name   = "${var.name}-set-instance-health"
  role   = local.iam_role_name
  policy = data.aws_iam_policy_document.instance_health.json
}

data "aws_iam_policy_document" "secrets" {
  count = length(local.secret_arns) > 0 ? 1 : 0

  statement {
    sid    = "ReadRunnerSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
    ]
    resources = sort(tolist(local.secret_arns))
  }

  dynamic "statement" {
    for_each = length(var.secret_kms_key_arns) > 0 ? [1] : []

    content {
      sid       = "DecryptRunnerSecrets"
      effect    = "Allow"
      actions   = ["kms:Decrypt"]
      resources = sort(tolist(var.secret_kms_key_arns))

      condition {
        test     = "StringEquals"
        variable = "kms:ViaService"
        values = [
          "secretsmanager.${local.region}.${data.aws_partition.current.dns_suffix}",
        ]
      }
    }
  }
}

resource "aws_iam_role_policy" "secrets" {
  count = length(local.secret_arns) > 0 ? 1 : 0

  name   = "${var.name}-read-secrets"
  role   = local.iam_role_name
  policy = data.aws_iam_policy_document.secrets[0].json
}

resource "aws_launch_template" "runner" {
  name_prefix            = "${var.name}-"
  image_id               = coalesce(var.ami_id, try(data.aws_ami.runner[0].id, null))
  instance_type          = var.instance_type
  user_data              = base64encode(local.cloud_init)
  update_default_version = true
  vpc_security_group_ids = var.security_group_ids

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      delete_on_termination = true
      volume_size           = var.root_volume_size_gb
      volume_type           = "gp3"
    }
  }

  iam_instance_profile {
    name = local.instance_profile_name
  }

  instance_market_options {
    market_type = "spot"

    spot_options {
      spot_instance_type = "one-time"
    }
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"
    tags          = local.resource_tags
  }

  tags = var.tags

  lifecycle {
    precondition {
      condition     = local.valid_identity
      error_message = "iam_role_name and instance_profile_name must either both be null or both be set."
    }

    precondition {
      condition     = !var.enabled || var.min_replicas >= 1
      error_message = "min_replicas must be at least 1 while enabled because instance CPU cannot scale a zero-sized fleet."
    }

    precondition {
      condition     = var.max_replicas >= var.min_replicas
      error_message = "max_replicas must be greater than or equal to min_replicas."
    }

    precondition {
      condition = (
        contains(keys(var.environment_variables), "TILEBOX_API_KEY") !=
        contains(keys(var.secret_environment_variables), "TILEBOX_API_KEY")
      )
      error_message = "TILEBOX_API_KEY must be present in exactly one of environment_variables or secret_environment_variables."
    }

    precondition {
      condition     = length(setintersection(toset(keys(var.environment_variables)), toset(keys(var.secret_environment_variables)))) == 0
      error_message = "environment_variables and secret_environment_variables must not contain the same key."
    }
  }
}

resource "aws_autoscaling_group" "runner" {
  name                = var.name
  min_size            = local.effective_min_replicas
  max_size            = local.effective_max_replicas
  desired_capacity    = local.effective_min_replicas
  vpc_zone_identifier = var.subnet_ids

  health_check_type         = "EC2"
  health_check_grace_period = 300
  default_instance_warmup   = 60
  capacity_rebalance        = true
  termination_policies      = ["OldestInstance", "Default"]

  launch_template {
    id      = aws_launch_template.runner.id
    version = tostring(aws_launch_template.runner.latest_version)
  }

  instance_refresh {
    strategy = "Rolling"

    preferences {
      min_healthy_percentage = 0
      instance_warmup        = 60
    }
  }

  dynamic "tag" {
    for_each = local.resource_tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  depends_on = [
    aws_iam_role_policy.instance_health,
    aws_iam_role_policy.secrets,
  ]

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

resource "aws_autoscaling_policy" "cpu" {
  count = var.enabled ? 1 : 0

  name                      = "${var.name}-cpu"
  autoscaling_group_name    = aws_autoscaling_group.runner.name
  policy_type               = "TargetTrackingScaling"
  estimated_instance_warmup = 60

  target_tracking_configuration {
    target_value = var.cpu_target * 100

    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
  }
}
