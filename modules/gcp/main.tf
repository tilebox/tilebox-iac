locals {
  create_service_account = var.service_account_email == null
  service_account_id     = coalesce(var.service_account_id, var.name)
  service_account_email = local.create_service_account ? (
    google_service_account.runner[0].email
  ) : var.service_account_email

  effective_min_replicas = var.enabled ? var.min_replicas : 0
  effective_max_replicas = var.enabled ? var.max_replicas : 0

  health_check_network            = coalesce(var.health_check_network_self_link, var.network_self_link)
  health_check_network_project_id = coalesce(var.health_check_network_project_id, var.project_id)

  registry_hostname = split("/", var.runner_image)[0]
  gcp_registry_hostname = (
    local.registry_hostname == "gcr.io" ||
    endswith(local.registry_hostname, ".gcr.io") ||
    endswith(local.registry_hostname, ".pkg.dev")
  ) ? local.registry_hostname : ""

  environment_file = base64encode(join("", [
    for name in sort(keys(var.environment_variables)) : "${name}=${var.environment_variables[name]}\n"
  ]))

  secret_resource_names = {
    for name, secret in var.secret_environment_variables :
    name => "projects/${secret.project_id}/secrets/${secret.secret_id}"
  }

  resource_labels = merge(var.labels, {
    "tilebox-component" = "runner"
  })

  cloud_init = templatefile("${path.module}/cloud-init.tftpl", {
    container_image              = var.runner_image
    environment_file             = local.environment_file
    gcp_registry_hostname        = local.gcp_registry_hostname
    secret_environment_variables = local.secret_resource_names
  })
}

resource "google_service_account" "runner" {
  count = local.create_service_account ? 1 : 0

  project      = var.project_id
  account_id   = local.service_account_id
  display_name = "Tilebox ${var.name} Runner"

  lifecycle {
    precondition {
      condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", local.service_account_id))
      error_message = "A module-created service account needs a 6-30 character service_account_id; set service_account_id when name is not valid."
    }

    precondition {
      condition     = var.service_account_email == null || var.service_account_id == null
      error_message = "service_account_id must be null when service_account_email selects an existing identity."
    }
  }
}

resource "google_project_iam_member" "monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${local.service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "runner" {
  for_each = var.secret_environment_variables

  project   = each.value.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.service_account_email}"
}

resource "google_compute_region_health_check" "runner" {
  project = var.project_id
  region  = var.region
  name    = "${var.name}-health-check"

  check_interval_sec  = 30
  timeout_sec         = 5
  healthy_threshold   = 1
  unhealthy_threshold = 3

  http_health_check {
    port         = 8080
    request_path = "/health"
  }
}

resource "google_compute_firewall" "health_check" {
  project   = local.health_check_network_project_id
  name      = "${var.name}-health-check"
  network   = local.health_check_network
  direction = "INGRESS"

  source_ranges           = ["130.211.0.0/22", "35.191.0.0/16"]
  target_service_accounts = [local.service_account_email]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

resource "google_compute_instance_template" "runner" {
  project      = var.project_id
  name_prefix  = "${var.name}-"
  machine_type = var.machine_type

  metadata = {
    "enable-oslogin"            = "TRUE"
    "google-monitoring-enabled" = "true"
    "user-data"                 = local.cloud_init
  }

  labels = local.resource_labels

  disk {
    source_image = "projects/cos-cloud/global/images/family/cos-stable"
    auto_delete  = true
    boot         = true
    disk_size_gb = var.root_volume_size_gb
  }

  network_interface {
    network    = var.network_self_link
    subnetwork = var.subnetwork_self_link
  }

  service_account {
    email  = local.service_account_email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  scheduling {
    provisioning_model          = "SPOT"
    preemptible                 = true
    automatic_restart           = false
    on_host_maintenance         = "TERMINATE"
    instance_termination_action = "STOP"
  }

  depends_on = [
    google_project_iam_member.monitoring,
    google_secret_manager_secret_iam_member.runner,
  ]

  lifecycle {
    create_before_destroy = true

    precondition {
      condition     = var.service_account_email == null || var.service_account_id == null
      error_message = "service_account_id must be null when service_account_email selects an existing identity."
    }

    precondition {
      condition     = !local.create_service_account || can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", local.service_account_id))
      error_message = "A module-created service account needs a 6-30 character service_account_id; set service_account_id when name is not valid."
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

resource "google_compute_region_instance_group_manager" "runner" {
  project            = var.project_id
  region             = var.region
  name               = "${var.name}-mig"
  base_instance_name = var.name

  version {
    name              = "primary"
    instance_template = google_compute_instance_template.runner.self_link
  }

  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 10
    max_unavailable_fixed = 0
  }

  dynamic "auto_healing_policies" {
    for_each = var.auto_healing_enabled ? [1] : []
    content {
      health_check      = google_compute_region_health_check.runner.id
      initial_delay_sec = 300
    }
  }

  depends_on = [google_compute_firewall.health_check]
}

resource "google_compute_region_autoscaler" "runner" {
  project = var.project_id
  region  = var.region
  name    = "${var.name}-autoscaler"
  target  = google_compute_region_instance_group_manager.runner.id

  autoscaling_policy {
    min_replicas    = local.effective_min_replicas
    max_replicas    = local.effective_max_replicas
    cooldown_period = 60
    mode            = var.enabled ? "ON" : "OFF"

    cpu_utilization {
      target = var.cpu_target
    }
  }
}
