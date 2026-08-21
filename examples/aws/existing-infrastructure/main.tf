provider "aws" {
  region = var.region
}

module "runner" {
  source = "../../../modules/aws/runner"

  name               = var.name
  instance_type      = var.instance_type
  subnet_ids         = var.subnet_ids
  security_group_ids = var.security_group_ids
  min_replicas       = var.min_replicas
  max_replicas       = var.max_replicas
  cpu_target         = var.cpu_target

  iam_role_name         = var.iam_role_name
  instance_profile_name = var.instance_profile_name
  secret_kms_key_arns   = var.secret_kms_key_arns

  environment_variables = var.environment_variables
  secret_environment_variables = {
    TILEBOX_API_KEY = {
      secret_arn     = var.tilebox_api_key_secret_arn
      rollout_marker = var.tilebox_api_key_rollout_marker
    }
  }
}
