provider "google" {
  project = var.project_id
  region  = var.region
}

module "runner" {
  source = "../../../modules/gcp-runner"

  name                 = var.name
  project_id           = var.project_id
  region               = var.region
  network_self_link    = var.network_self_link
  subnetwork_self_link = var.subnetwork_self_link
  machine_type         = var.machine_type
  min_replicas         = var.min_replicas
  max_replicas         = var.max_replicas
  cpu_target           = var.cpu_target

  health_check_network_project_id = var.health_check_network_project_id
  health_check_network_self_link  = var.health_check_network_self_link
  service_account_email           = var.service_account_email

  environment_variables = var.environment_variables
  secret_environment_variables = {
    TILEBOX_API_KEY = {
      project_id     = var.tilebox_api_key_secret_project_id
      secret_id      = var.tilebox_api_key_secret_id
      rollout_marker = var.tilebox_api_key_rollout_marker
    }
  }
}
