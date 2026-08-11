output "cluster_id" {
  value = module.runner_cluster.cluster_id
}

output "node_pool_id" {
  value = module.runner_cluster.node_pool_id
}

output "kubeconfig" {
  value     = module.runner_cluster.kubeconfig
  sensitive = true
}
