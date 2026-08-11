provider "aws" {
  region = var.region
}

module "runner" {
  source = "../../../modules/aws"

  tilebox_api_key = var.tilebox_api_key
}
