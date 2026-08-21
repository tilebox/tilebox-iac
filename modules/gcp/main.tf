locals {
  required_services = toset([
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "monitoring.googleapis.com",
    "secretmanager.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "runner" {
  project                 = var.project_id
  name                    = var.name
  auto_create_subnetworks = false

  depends_on = [google_project_service.required["compute.googleapis.com"]]
}

resource "google_compute_subnetwork" "runner" {
  project                  = var.project_id
  region                   = var.region
  name                     = var.name
  network                  = google_compute_network.runner.id
  ip_cidr_range            = "10.42.0.0/24"
  private_ip_google_access = true
}

resource "google_compute_router" "runner" {
  project = var.project_id
  region  = var.region
  name    = var.name
  network = google_compute_network.runner.id
}

resource "google_compute_router_nat" "runner" {
  project                            = var.project_id
  region                             = var.region
  name                               = var.name
  router                             = google_compute_router.runner.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.runner.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

resource "google_secret_manager_secret" "tilebox_api_key" {
  project   = var.project_id
  secret_id = "${var.name}-tilebox-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "tilebox_api_key" {
  secret      = google_secret_manager_secret.tilebox_api_key.id
  secret_data = var.tilebox_api_key
}

module "runner" {
  source = "./runner"

  name                  = var.name
  project_id            = var.project_id
  region                = var.region
  network_self_link     = google_compute_network.runner.self_link
  subnetwork_self_link  = google_compute_subnetwork.runner.self_link
  machine_type          = var.machine_type
  enabled               = var.enabled
  min_replicas          = var.min_replicas
  max_replicas          = var.max_replicas
  cpu_target            = var.cpu_target
  runner_image          = var.runner_image
  root_volume_size_gb   = var.root_volume_size_gb
  labels                = var.labels
  environment_variables = var.environment_variables

  secret_environment_variables = {
    TILEBOX_API_KEY = {
      project_id     = var.project_id
      secret_id      = google_secret_manager_secret.tilebox_api_key.secret_id
      rollout_marker = google_secret_manager_secret_version.tilebox_api_key.id
    }
  }

  depends_on = [
    google_compute_router_nat.runner,
    google_project_service.required,
  ]
}
