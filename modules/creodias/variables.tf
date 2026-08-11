variable "name" {
  description = "Managed Kubernetes cluster and runner node-pool name. Also used as the dedicated pool-label value."
  type        = string

  validation {
    condition     = can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.name))
    error_message = "name must start with a lowercase letter and be a lowercase DNS label of at most 63 characters."
  }
}

variable "kubernetes_version" {
  description = "Exact Kubernetes version offered by the selected CloudFerro Managed Kubernetes region."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.kubernetes_version))
    error_message = "kubernetes_version must be an exact three-part version such as 1.32.6."
  }
}

variable "control_plane_flavor" {
  description = "Control-plane flavor offered by the selected Managed Kubernetes endpoint."
  type        = string

  validation {
    condition     = length(trimspace(var.control_plane_flavor)) > 0
    error_message = "control_plane_flavor must not be empty."
  }
}

variable "control_plane_size" {
  description = "Number of managed control-plane nodes. Use 3 or 5 for production high availability."
  type        = number
  default     = 3

  validation {
    condition     = contains([1, 3, 5], var.control_plane_size)
    error_message = "control_plane_size must be 1, 3, or 5."
  }
}

variable "worker_flavor" {
  description = "Worker flavor offered by the selected Managed Kubernetes endpoint."
  type        = string

  validation {
    condition     = length(trimspace(var.worker_flavor)) > 0
    error_message = "worker_flavor must not be empty."
  }
}

variable "min_replicas" {
  description = "Minimum runner workers. CREODIAS Managed Kubernetes scale-to-zero is not documented."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 1 && floor(var.min_replicas) == var.min_replicas
    error_message = "min_replicas must be an integer of at least 1."
  }
}

variable "max_replicas" {
  description = "Maximum runner workers."
  type        = number

  validation {
    condition     = var.max_replicas >= 1 && floor(var.max_replicas) == var.max_replicas
    error_message = "max_replicas must be an integer of at least 1."
  }
}

variable "shared_network_ids" {
  description = "Existing OpenStack network IDs shared with the worker pool. The caller must configure network RBAC first."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for id in var.shared_network_ids : length(trimspace(id)) > 0])
    error_message = "shared_network_ids must contain only non-empty network IDs."
  }
}
