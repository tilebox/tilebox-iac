provider "cloudferro" {
  region      = var.host == null ? var.region : null
  host        = var.host
  server_cert = var.server_cert
}

module "runner_cluster" {
  source = "../../../modules/creodias"

  name                 = var.name
  kubernetes_version   = var.kubernetes_version
  control_plane_flavor = var.control_plane_flavor
  control_plane_size   = var.control_plane_size
  worker_flavor        = var.worker_flavor
  min_replicas         = var.min_replicas
  max_replicas         = var.max_replicas
  shared_network_ids   = var.shared_network_ids
}
