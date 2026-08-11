# Outputs from the low-level AWS runner fleet.
output "autoscaling_group_name" {
  description = "Name of the runner Auto Scaling Group."
  value       = aws_autoscaling_group.runner.name
}

output "autoscaling_group_arn" {
  description = "ARN of the runner Auto Scaling Group."
  value       = aws_autoscaling_group.runner.arn
}

output "launch_template_id" {
  description = "ID of the runner launch template."
  value       = aws_launch_template.runner.id
}

output "iam_role_name" {
  description = "Name of the module-created or caller-supplied runner IAM role."
  value       = local.iam_role_name
}

output "iam_role_arn" {
  description = "ARN of the module-created or caller-supplied runner IAM role."
  value = local.create_identity ? aws_iam_role.runner[0].arn : try(
    data.aws_iam_role.runner[0].arn,
    null,
  )
}

output "instance_profile_name" {
  description = "Name of the module-created or caller-supplied EC2 instance profile."
  value       = local.instance_profile_name
}
