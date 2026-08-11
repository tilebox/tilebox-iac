output "autoscaling_group_name" {
  description = "Name of the quickstart runner Auto Scaling Group."
  value       = module.runner.autoscaling_group_name
}

output "vpc_id" {
  description = "ID of the module-managed VPC."
  value       = module.runner.vpc_id
}
