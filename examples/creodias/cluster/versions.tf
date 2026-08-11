terraform {
  required_version = ">= 1.5.0"

  required_providers {
    cloudferro = {
      source  = "registry.terraform.io/CloudFerro/cloudferro"
      version = "= 0.1.3"
    }
  }
}
