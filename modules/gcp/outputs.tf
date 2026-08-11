output "instance_group" {
  description = "Self-link of the runner managed instance group."
  value       = module.runner.instance_group
}

output "network_self_link" {
  description = "Self-link of the module-managed VPC."
  value       = google_compute_network.runner.self_link
}

output "subnetwork_self_link" {
  description = "Self-link of the module-managed runner subnetwork."
  value       = google_compute_subnetwork.runner.self_link
}

output "runner_service_account_email" {
  description = "Email of the runner service account."
  value       = module.runner.service_account_email
}

output "tilebox_api_key_secret_id" {
  description = "ID of the module-managed Tilebox API-key secret."
  value       = google_secret_manager_secret.tilebox_api_key.id
}
