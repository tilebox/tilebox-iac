output "namespace" {
  description = "Namespace containing the Tilebox runner workload."
  value       = local.namespace
}

output "deployment_name" {
  description = "Tilebox runner Deployment name."
  value       = kubernetes_deployment_v1.runner.metadata[0].name
}

output "horizontal_pod_autoscaler_name" {
  description = "Runner HPA name."
  value       = kubernetes_horizontal_pod_autoscaler_v2.runner.metadata[0].name
}
