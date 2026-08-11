variable "project_id" {
  description = "Existing GCP project for this disposable example. The example does not create a project."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "name" {
  type    = string
  default = "tilebox-runners-example"
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
  default = 3
}

variable "cpu_target" {
  type    = number
  default = 0.2
}

variable "tilebox_api_key" {
  description = "Tilebox API key. Supply through TF_VAR_tilebox_api_key rather than a committed tfvars file."
  type        = string
  sensitive   = true
}

variable "environment_variables" {
  description = "Additional non-secret runner environment variables, such as TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}
