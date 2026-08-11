variable "region" {
  description = "AWS region containing the existing subnets."
  type        = string
}

variable "name" {
  description = "Runner cluster name."
  type        = string
  default     = "tilebox-runners"
}

variable "instance_type" {
  description = "EC2 instance type for runner instances."
  type        = string
  default     = "m7i.large"
}

variable "subnet_ids" {
  description = "Existing subnet IDs with outbound connectivity."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Existing runner security groups, or null to use the VPC default."
  type        = list(string)
  default     = null
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

variable "iam_role_name" {
  description = "Optional existing EC2-assumable role; set with instance_profile_name."
  type        = string
  default     = null
}

variable "instance_profile_name" {
  description = "Optional existing instance profile; set with iam_role_name."
  type        = string
  default     = null
}

variable "tilebox_api_key_secret_arn" {
  description = "ARN of an existing Secrets Manager secret containing the Tilebox API key as SecretString."
  type        = string
}

variable "tilebox_api_key_rollout_marker" {
  description = "Optional secret version ID or other marker that triggers a fleet refresh after rotation."
  type        = string
  default     = ""
}

variable "secret_kms_key_arns" {
  description = "Customer-managed KMS key ARNs needed to decrypt the configured secret, if any."
  type        = set(string)
  default     = []
}

variable "environment_variables" {
  description = "Additional non-secret runner environment variables, such as TILEBOX_CLUSTER."
  type        = map(string)
  default     = {}
  sensitive   = true
}
