locals {
  namespace         = coalesce(var.namespace, var.name)
  runner_name       = "runner"
  runner_pool_label = "tilebox.com/runner-pool"

  workload_labels = {
    "app.kubernetes.io/name"     = "tilebox-runner"
    "app.kubernetes.io/instance" = var.name
  }

  resource_requests = merge(
    { cpu = var.runner_cpu_request },
    var.runner_memory_request == null ? {} : { memory = var.runner_memory_request },
  )
}

resource "kubernetes_namespace_v1" "runner" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = local.namespace
  }
}

resource "kubernetes_secret_v1" "environment" {
  metadata {
    name      = "runner-environment"
    namespace = local.namespace
  }

  data = var.environment_variables
  type = "Opaque"

  depends_on = [kubernetes_namespace_v1.runner]
}

resource "kubernetes_service_account_v1" "runner" {
  metadata {
    name      = local.runner_name
    namespace = local.namespace
  }

  automount_service_account_token = false

  depends_on = [kubernetes_namespace_v1.runner]
}

resource "kubernetes_deployment_v1" "runner" {
  metadata {
    name      = local.runner_name
    namespace = local.namespace
    labels    = local.workload_labels
  }

  spec {
    replicas = var.min_replicas

    selector {
      match_labels = local.workload_labels
    }

    strategy {
      type = "RollingUpdate"

      rolling_update {
        max_surge       = "0"
        max_unavailable = "1"
      }
    }

    template {
      metadata {
        labels = local.workload_labels
        annotations = {
          "tilebox.com/environment-checksum" = sha256(jsonencode(var.environment_variables))
        }
      }

      spec {
        service_account_name             = kubernetes_service_account_v1.runner.metadata[0].name
        automount_service_account_token  = false
        termination_grace_period_seconds = 30

        dynamic "image_pull_secrets" {
          for_each = var.image_pull_secret_names
          content {
            name = image_pull_secrets.value
          }
        }

        node_selector = {
          (local.runner_pool_label) = var.name
        }

        toleration {
          key      = local.runner_pool_label
          operator = "Equal"
          value    = var.name
          effect   = "NoSchedule"
        }

        affinity {
          pod_anti_affinity {
            required_during_scheduling_ignored_during_execution {
              topology_key = "kubernetes.io/hostname"

              label_selector {
                match_labels = local.workload_labels
              }
            }
          }
        }

        container {
          name  = local.runner_name
          image = var.runner_image

          env_from {
            secret_ref {
              name = kubernetes_secret_v1.environment.metadata[0].name
            }
          }

          resources {
            requests = local.resource_requests
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_secret_v1.environment,
    kubernetes_service_account_v1.runner,
  ]

  lifecycle {
    ignore_changes = [spec[0].replicas]

    precondition {
      condition     = var.max_replicas >= var.min_replicas
      error_message = "max_replicas must be greater than or equal to min_replicas."
    }
  }
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "runner" {
  metadata {
    name      = local.runner_name
    namespace = local.namespace
  }

  spec {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.runner.metadata[0].name
    }

    metric {
      type = "Resource"

      resource {
        name = "cpu"

        target {
          type                = "Utilization"
          average_utilization = floor((var.cpu_target * 100) + 0.5)
        }
      }
    }

    behavior {
      scale_down {
        stabilization_window_seconds = 300

        policy {
          type           = "Percent"
          value          = 100
          period_seconds = 15
        }
      }
    }
  }
}
