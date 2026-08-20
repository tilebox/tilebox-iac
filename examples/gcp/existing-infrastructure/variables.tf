variable "project_id" {
  description = "Existing workload project."
  type        = string
}

variable "region" {
  description = "Region containing the existing subnetwork."
  type        = string
}

variable "name" {
  type    = string
  default = "tilebox-runners"
}

variable "network_self_link" {
  description = "Self-link of the existing VPC."
  type        = string
}

variable "subnetwork_self_link" {
  description = "Self-link of the existing regional subnetwork."
  type        = string
}

variable "health_check_network_project_id" {
  description = "Shared VPC host project, or null when the workload project owns the VPC."
  type        = string
  default     = null
}

variable "health_check_network_self_link" {
  description = "Shared VPC host-network self-link, or null to use network_self_link."
  type        = string
  default     = null
}

variable "machine_type" {
  type    = string
  default = "n2-standard-2"
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 10
}

variable "cpu_target" {
  type    = number
  default = 0.2
}

variable "service_account_email" {
  description = "Optional existing runner service account."
  type        = string
  default     = null
}

variable "tilebox_api_key_secret_project_id" {
  description = "Project containing the existing Tilebox API-key secret."
  type        = string
}

variable "tilebox_api_key_secret_id" {
  description = "Bare Secret Manager secret ID containing the Tilebox API key."
  type        = string
}

variable "tilebox_api_key_rollout_marker" {
  description = "Secret version or other marker to replace runner VMs after rotating the Tilebox API key."
  type        = string
  default     = ""
}

variable "environment_variables" {
  description = "Additional non-secret runner environment variables, such as TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}
