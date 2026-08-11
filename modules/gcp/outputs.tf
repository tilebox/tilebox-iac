output "service_account_email" {
  description = "Email of the module-created or caller-supplied runner service account."
  value       = local.service_account_email
}

output "service_account_id" {
  description = "ID of the module-created service account, or null when using an existing identity."
  value       = local.create_service_account ? google_service_account.runner[0].id : null
}

output "instance_template_id" {
  description = "ID of the runner instance template."
  value       = google_compute_instance_template.runner.id
}

output "instance_group_manager_id" {
  description = "ID of the regional managed instance group."
  value       = google_compute_region_instance_group_manager.runner.id
}

output "instance_group" {
  description = "Self-link of the managed instance group controlled by the regional manager."
  value       = google_compute_region_instance_group_manager.runner.instance_group
}

output "autoscaler_id" {
  description = "ID of the regional CPU autoscaler."
  value       = google_compute_region_autoscaler.runner.id
}

output "health_check_id" {
  description = "ID of the regional container-state health check."
  value       = google_compute_region_health_check.runner.id
}
