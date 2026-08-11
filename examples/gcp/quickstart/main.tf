provider "google" {
  project = var.project_id
  region  = var.region
}

module "runner" {
  source = "../../../modules/gcp"

  project_id      = var.project_id
  region          = var.region
  tilebox_api_key = var.tilebox_api_key
}
