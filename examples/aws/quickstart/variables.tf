variable "region" {
  description = "AWS region for the runner cluster."
  type        = string
  default     = "us-west-2"
}

variable "tilebox_api_key" {
  description = "Tilebox API key. Supply through TF_VAR_tilebox_api_key rather than a committed tfvars file."
  type        = string
  sensitive   = true
}
