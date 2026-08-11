variable "name" {
  type    = string
  default = "tilebox-runners"
}

variable "region" {
  description = "CloudFerro Managed Kubernetes region. Ignored when host is set."
  type        = string
  default     = "WAW4-1"
}

variable "host" {
  description = "Optional private Managed Kubernetes host. Mutually exclusive with region."
  type        = string
  default     = null
}

variable "server_cert" {
  description = "Optional path to an additional PEM certificate bundle."
  type        = string
  default     = null
}

variable "kubernetes_version" {
  description = "Exact version available in the selected Managed Kubernetes endpoint."
  type        = string
}

variable "control_plane_flavor" {
  description = "Control-plane flavor available in the selected endpoint."
  type        = string
}

variable "control_plane_size" {
  type    = number
  default = 3
}

variable "worker_flavor" {
  description = "Worker flavor available in the selected endpoint."
  type        = string
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 10
}

variable "shared_network_ids" {
  description = "Optional existing OpenStack network IDs with Managed Kubernetes RBAC already configured."
  type        = list(string)
  default     = []
}
