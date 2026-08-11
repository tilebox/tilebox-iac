variable "project_id" {
  description = "Existing Google Cloud project in which to create the cluster infrastructure."
  type        = string
}

variable "region" {
  description = "Google Cloud region for the cluster."
  type        = string
  default     = "europe-west1"
}

variable "name" {
  description = "Name for the Tilebox runner cluster and its infrastructure."
  type        = string
  default     = "tilebox-runners"
}

variable "tilebox_api_key" {
  description = "Tilebox API key stored in a module-managed Secret Manager secret."
  type        = string
  sensitive   = true
}

variable "machine_type" {
  description = "Compute Engine machine type for each runner."
  type        = string
  default     = "n2-standard-2"
}

variable "enabled" {
  description = "Whether runner capacity is enabled."
  type        = bool
  default     = true
}

variable "min_replicas" {
  description = "Minimum number of runners while enabled."
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum number of runners while enabled."
  type        = number
  default     = 3
}

variable "cpu_target" {
  description = "Average fleet CPU target as a fraction."
  type        = number
  default     = 0.2
}

variable "runner_image" {
  description = "Prebuilt runner container image."
  type        = string
  default     = "ghcr.io/tilebox/runner:latest"
}

variable "root_volume_size_gb" {
  description = "Runner boot disk size in GiB."
  type        = number
  default     = 40
}

variable "environment_variables" {
  description = "Additional runner settings such as the optional TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "labels" {
  description = "Additional labels for module-owned Google Cloud resources."
  type        = map(string)
  default     = {}
}
