provider "kubernetes" {
  config_path = var.kubeconfig_path
}

module "runner" {
  source = "../../../modules/kubernetes-runner"

  name                    = var.name
  runner_cpu_request      = var.runner_cpu_request
  runner_memory_request   = var.runner_memory_request
  cpu_target              = var.cpu_target
  min_replicas            = var.min_replicas
  max_replicas            = var.max_replicas
  runner_image            = var.runner_image
  image_pull_secret_names = var.image_pull_secret_names

  environment_variables = merge(var.environment_variables, {
    TILEBOX_API_KEY = var.tilebox_api_key
  })
}
