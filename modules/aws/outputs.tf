output "autoscaling_group_name" {
  description = "Name of the runner Auto Scaling Group."
  value       = module.runner.autoscaling_group_name
}

output "vpc_id" {
  description = "ID of the module-managed VPC."
  value       = aws_vpc.runner.id
}

output "subnet_ids" {
  description = "IDs of the module-managed runner subnets."
  value       = [for subnet in aws_subnet.runner : subnet.id]
}

output "runner_iam_role_arn" {
  description = "ARN of the runner IAM role."
  value       = module.runner.iam_role_arn
}

output "tilebox_api_key_secret_arn" {
  description = "ARN of the module-managed Tilebox API-key secret."
  value       = aws_secretsmanager_secret.tilebox_api_key.arn
}
