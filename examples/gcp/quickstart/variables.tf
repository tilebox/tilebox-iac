variable "project_id" {
  description = "Existing GCP project for the runner cluster. The module does not create a project."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "tilebox_api_key" {
  description = "Tilebox API key. Supply through TF_VAR_tilebox_api_key rather than a committed tfvars file."
  type        = string
  sensitive   = true
}
