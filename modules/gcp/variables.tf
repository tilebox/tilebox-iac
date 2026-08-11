variable "name" {
  description = "Name prefix for runner resources."
  type        = string

  validation {
    condition     = can(regex("^[a-z](?:[a-z0-9-]{0,48}[a-z0-9])?$", var.name))
    error_message = "name must be a lowercase GCP-compatible prefix of at most 50 characters so generated resource names stay within GCP's 63-character limit."
  }
}

variable "project_id" {
  description = "Existing GCP project in which to create runner compute and workload IAM grants."
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must not be empty."
  }
}

variable "region" {
  description = "Region for the managed instance group, autoscaler, and health check."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region must not be empty."
  }
}

variable "network_self_link" {
  description = "Self-link of the existing VPC network used by runner instances."
  type        = string

  validation {
    condition     = length(trimspace(var.network_self_link)) > 0
    error_message = "network_self_link must not be empty."
  }
}

variable "subnetwork_self_link" {
  description = "Self-link of the existing regional subnetwork used by runner instances."
  type        = string

  validation {
    condition     = length(trimspace(var.subnetwork_self_link)) > 0
    error_message = "subnetwork_self_link must not be empty."
  }
}

variable "health_check_network_self_link" {
  description = "Optional network self-link for the health-check firewall. Defaults to network_self_link."
  type        = string
  default     = null

  validation {
    condition     = var.health_check_network_self_link == null || length(trimspace(var.health_check_network_self_link)) > 0
    error_message = "health_check_network_self_link must be null or non-empty."
  }
}

variable "health_check_network_project_id" {
  description = "Optional project that owns the health-check network. Set this to the host project for Shared VPC."
  type        = string
  default     = null

  validation {
    condition     = var.health_check_network_project_id == null || length(trimspace(var.health_check_network_project_id)) > 0
    error_message = "health_check_network_project_id must be null or non-empty."
  }
}

variable "machine_type" {
  description = "Compute Engine machine type for each runner."
  type        = string

  validation {
    condition     = length(trimspace(var.machine_type)) > 0
    error_message = "machine_type must not be empty."
  }
}

variable "enabled" {
  description = "Whether runners are enabled. Disabled clusters keep their compute infrastructure, remove the autoscaler, and resize the managed instance group to zero."
  type        = bool
  default     = true
}

variable "min_replicas" {
  description = "Minimum number of runners while enabled. CPU autoscaling cannot wake a zero-sized fleet."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 0 && floor(var.min_replicas) == var.min_replicas
    error_message = "min_replicas must be a non-negative integer."
  }
}

variable "max_replicas" {
  description = "Maximum number of runners while enabled."
  type        = number

  validation {
    condition     = var.max_replicas >= 0 && floor(var.max_replicas) == var.max_replicas
    error_message = "max_replicas must be a non-negative integer."
  }
}

variable "cpu_target" {
  description = "Average managed-instance-group CPU target as a fraction from greater than 0 through 1."
  type        = number

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target <= 1
    error_message = "cpu_target must be greater than 0 and at most 1."
  }
}

variable "runner_image" {
  description = "Prebuilt runner image. Private GCR or Artifact Registry images require pull permissions on the runner service account."
  type        = string
  default     = "ghcr.io/tilebox/runner:latest"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._:/@-]*$", var.runner_image))
    error_message = "runner_image must be a container image reference without whitespace or shell metacharacters."
  }
}

variable "root_volume_size_gb" {
  description = "Boot disk size in GiB. The disk is deleted with the instance."
  type        = number
  default     = 40

  validation {
    condition     = var.root_volume_size_gb >= 10 && floor(var.root_volume_size_gb) == var.root_volume_size_gb
    error_message = "root_volume_size_gb must be an integer of at least 10 GiB."
  }
}

variable "environment_variables" {
  description = "Plain runner environment variables. Values are stored in Terraform/OpenTofu state and instance metadata; use secret_environment_variables for credentials."
  type        = map(string)
  default     = {}
  sensitive   = true

  validation {
    condition = alltrue([
      for name, value in var.environment_variables :
      can(regex("^[A-Za-z_][A-Za-z0-9_]*$", name)) &&
      length(regexall("[\r\n]", value)) == 0 &&
      length(split("\u0000", value)) == 1
    ])
    error_message = "Environment variable names must be shell-compatible and values must not contain CR, LF, or NUL."
  }
}

variable "secret_environment_variables" {
  description = "Runner environment variables fetched from existing Secret Manager secrets on every service start."
  type = map(object({
    project_id = string
    secret_id  = string
  }))
  default = {}

  validation {
    condition = alltrue([
      for name, secret in var.secret_environment_variables :
      can(regex("^[A-Za-z_][A-Za-z0-9_]*$", name)) &&
      length(trimspace(secret.project_id)) > 0 &&
      can(regex("^[A-Za-z0-9_-]+$", secret.secret_id))
    ])
    error_message = "Secret environment names must be shell-compatible and every secret must have a project_id and bare secret_id."
  }
}

variable "service_account_email" {
  description = "Existing runner service-account email. Leave null to let the module create a minimal workload identity."
  type        = string
  default     = null

  validation {
    condition     = var.service_account_email == null || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.gserviceaccount\\.com$", var.service_account_email))
    error_message = "service_account_email must be null or a Google service-account email."
  }
}

variable "service_account_id" {
  description = "Account ID for a module-created service account. Defaults to name and must be omitted with service_account_email."
  type        = string
  default     = null

  validation {
    condition     = var.service_account_id == null || can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.service_account_id))
    error_message = "service_account_id must contain 6-30 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "labels" {
  description = "Additional labels for module-owned GCP resources."
  type        = map(string)
  default     = {}
}
