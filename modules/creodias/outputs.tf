output "cluster_id" {
  description = "CloudFerro Managed Kubernetes cluster UUID."
  value       = cloudferro_kubernetes_cluster_v1.runner.id
}

output "node_pool_id" {
  description = "Autoscaled runner node-pool UUID."
  value       = cloudferro_kubernetes_node_pool_v1.runner.id
}

output "router_ip" {
  description = "Router IP returned by CloudFerro."
  value       = cloudferro_kubernetes_cluster_v1.runner.router_ip
}

output "openstack_project_id" {
  description = "OpenStack project ID backing the managed cluster."
  value       = cloudferro_kubernetes_cluster_v1.runner.metadata.openstack_project_id
}

output "kubeconfig" {
  description = "Sensitive kubeconfig for the managed cluster."
  value       = cloudferro_kubernetes_cluster_v1.runner.kubeconfig
  sensitive   = true
}
