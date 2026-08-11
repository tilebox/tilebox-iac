variable "name" {
  description = "Runner deployment identity and dedicated worker-pool label value."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.name))
    error_message = "name must be a lowercase Kubernetes DNS label of at most 63 characters."
  }
}

variable "namespace" {
  description = "Kubernetes namespace for the runner. Defaults to name."
  type        = string
  default     = null

  validation {
    condition     = var.namespace == null || can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.namespace))
    error_message = "namespace must be null or a lowercase Kubernetes DNS label of at most 63 characters."
  }
}

variable "create_namespace" {
  description = "Create the runner namespace. Set false when the caller manages it."
  type        = bool
  default     = true
}

variable "runner_image" {
  description = "Prebuilt runner container image."
  type        = string
  default     = "ghcr.io/tilebox/runner:latest"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._:/@-]*$", var.runner_image))
    error_message = "runner_image must be a container image reference without whitespace or shell metacharacters."
  }
}

variable "environment_variables" {
  description = "Runner environment variables stored in a Kubernetes Secret. TILEBOX_API_KEY is required and TILEBOX_CLUSTER is optional."
  type        = map(string)
  sensitive   = true

  validation {
    condition = (
      try(length(var.environment_variables["TILEBOX_API_KEY"]) > 0, false) &&
      alltrue([
        for name, value in var.environment_variables :
        can(regex("^[A-Za-z_][A-Za-z0-9_]*$", name)) &&
        length(regexall("[\r\n]", value)) == 0 &&
        length(split("\u0000", value)) == 1
      ])
    )
    error_message = "environment_variables must contain a non-empty TILEBOX_API_KEY; names must be shell-compatible and values must not contain CR, LF, or NUL."
  }
}

variable "image_pull_secret_names" {
  description = "Names of existing image-pull Secrets in the runner namespace."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for name in var.image_pull_secret_names :
      can(regex("^[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?$", name))
    ])
    error_message = "image_pull_secret_names must contain valid Kubernetes DNS subdomain names."
  }
}

variable "runner_cpu_request" {
  description = "CPU request for each runner, such as 3500m. HPA utilization is relative to this request."
  type        = string

  validation {
    condition     = length(var.runner_cpu_request) > 0 && length(regexall("[[:space:]]", var.runner_cpu_request)) == 0
    error_message = "runner_cpu_request must be a non-empty Kubernetes quantity without whitespace."
  }
}

variable "runner_memory_request" {
  description = "Optional memory request for each runner, such as 14Gi."
  type        = string
  default     = null

  validation {
    condition     = var.runner_memory_request == null || (length(var.runner_memory_request) > 0 && length(regexall("[[:space:]]", var.runner_memory_request)) == 0)
    error_message = "runner_memory_request must be null or a non-empty Kubernetes quantity without whitespace."
  }
}

variable "cpu_target" {
  description = "HPA average CPU-utilization target as a fraction of runner_cpu_request."
  type        = number

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target <= 1 && floor((var.cpu_target * 100) + 0.5) >= 1
    error_message = "cpu_target must round to at least 1 percent and be at most 1."
  }
}

variable "min_replicas" {
  description = "Minimum runner pods. CREODIAS Managed Kubernetes scale-to-zero is not documented."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 1 && floor(var.min_replicas) == var.min_replicas
    error_message = "min_replicas must be an integer of at least 1."
  }
}

variable "max_replicas" {
  description = "Maximum runner pods. Keep this equal to the CREODIAS node-pool maximum."
  type        = number

  validation {
    condition     = var.max_replicas >= 1 && floor(var.max_replicas) == var.max_replicas
    error_message = "max_replicas must be an integer of at least 1."
  }
}
