output "instance_group" {
  description = "Self-link of the quickstart runner managed instance group."
  value       = module.runner.instance_group
}

output "network_self_link" {
  description = "Self-link of the module-managed VPC."
  value       = module.runner.network_self_link
}
