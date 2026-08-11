variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "name" {
  type    = string
  default = "tilebox-runners-example"
}

variable "instance_type" {
  type    = string
  default = "m7i.large"
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
