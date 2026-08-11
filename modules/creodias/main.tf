locals {
  runner_pool_label = "tilebox.com/runner-pool"
}

resource "cloudferro_kubernetes_cluster_v1" "runner" {
  name    = var.name
  version = var.kubernetes_version

  control_plane = {
    flavor = var.control_plane_flavor
    size   = var.control_plane_size
  }
}

resource "cloudferro_kubernetes_node_pool_v1" "runner" {
  name       = var.name
  cluster_id = cloudferro_kubernetes_cluster_v1.runner.id
  flavor     = var.worker_flavor

  autoscale = true
  size_min  = var.min_replicas
  size_max  = var.max_replicas

  labels = [
    {
      key   = local.runner_pool_label
      value = var.name
    },
  ]

  taints = [
    {
      key    = local.runner_pool_label
      value  = var.name
      effect = "NoSchedule"
    },
  ]

  shared_networks = var.shared_network_ids

  lifecycle {
    precondition {
      condition     = var.max_replicas >= var.min_replicas
      error_message = "max_replicas must be greater than or equal to min_replicas."
    }
  }
}
