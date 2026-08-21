variable "name" {
  description = "Name for the Tilebox runner cluster and its infrastructure."
  type        = string
  default     = "tilebox-runners"
}

variable "tilebox_api_key" {
  description = "Tilebox API key stored in a module-managed Secrets Manager secret."
  type        = string
  sensitive   = true
}

variable "instance_type" {
  description = "EC2 instance type for each runner."
  type        = string
  default     = "m7i.large"
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
  default     = 10
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
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 60
}

variable "environment_variables" {
  description = "Additional runner settings such as the optional TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "secret_recovery_window_days" {
  description = "Secrets Manager recovery window. Use zero only for disposable environments."
  type        = number
  default     = 7

  validation {
    condition = (
      var.secret_recovery_window_days == 0 ||
      (var.secret_recovery_window_days >= 7 && var.secret_recovery_window_days <= 30)
    )
    error_message = "secret_recovery_window_days must be 0 or between 7 and 30."
  }
}

variable "tags" {
  description = "Additional tags for module-owned AWS resources."
  type        = map(string)
  default     = {}
}
