variable "kubeconfig_path" {
  description = "Protected path to the kubeconfig exported by the CREODIAS cluster state."
  type        = string
}

variable "name" {
  description = "Must match the name used by the CREODIAS cluster module."
  type        = string
  default     = "tilebox-runners"
}

variable "tilebox_api_key" {
  description = "Tilebox API key. Supply through TF_VAR_tilebox_api_key rather than a committed tfvars file."
  type        = string
  sensitive   = true
}

variable "runner_cpu_request" {
  type    = string
  default = "3500m"
}

variable "runner_memory_request" {
  type    = string
  default = "14Gi"
}

variable "cpu_target" {
  type    = number
  default = 0.2
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 10
}

variable "runner_image" {
  type    = string
  default = "ghcr.io/tilebox/runner:latest"
}

variable "image_pull_secret_names" {
  description = "Existing registry Secret names in the runner namespace."
  type        = list(string)
  default     = []
}

variable "environment_variables" {
  description = "Additional runner environment variables, such as TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}
