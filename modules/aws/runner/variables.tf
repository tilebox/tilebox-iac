# Inputs for the nested runner module that deploys into caller-owned AWS infrastructure.
variable "name" {
  description = "Name used for the Auto Scaling Group and module-owned IAM resources."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", var.name))
    error_message = "name must contain 1-64 letters, numbers, underscores, or hyphens and start with a letter or number."
  }
}

variable "instance_type" {
  description = "EC2 instance type for each runner. The default AMI is x86_64; ARM instances require an explicit compatible ami_id."
  type        = string

  validation {
    condition     = length(trimspace(var.instance_type)) > 0
    error_message = "instance_type must not be empty."
  }
}

variable "subnet_ids" {
  description = "Existing subnet IDs for runner instances. The subnets must provide outbound access to AWS APIs, the image registry, and Tilebox."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for id in var.subnet_ids : length(trimspace(id)) > 0])
    error_message = "subnet_ids must contain at least one non-empty subnet ID."
  }
}

variable "security_group_ids" {
  description = "Existing security group IDs for runner instances. When null, EC2 uses the VPC's default security group."
  type        = list(string)
  default     = null

  validation {
    condition     = var.security_group_ids == null || alltrue([for id in var.security_group_ids : length(trimspace(id)) > 0])
    error_message = "security_group_ids must be null or contain only non-empty security group IDs."
  }
}

variable "ami_id" {
  description = "Optional AMI ID. Defaults to the latest Amazon Linux 2023 x86_64 HVM image owned by Amazon."
  type        = string
  default     = null

  validation {
    condition     = var.ami_id == null || can(regex("^ami-[0-9a-fA-F]+$", var.ami_id))
    error_message = "ami_id must be null or a valid AMI ID."
  }
}

variable "enabled" {
  description = "Whether runners are enabled. Disabled clusters keep their infrastructure but set all ASG capacities to zero and omit CPU scaling."
  type        = bool
  default     = true
}

variable "min_replicas" {
  description = "Minimum number of runners while enabled. CPU autoscaling cannot wake a zero-sized fleet."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 0 && floor(var.min_replicas) == var.min_replicas
    error_message = "min_replicas must be a non-negative integer."
  }
}

variable "max_replicas" {
  description = "Maximum number of runners while enabled."
  type        = number

  validation {
    condition     = var.max_replicas >= 0 && floor(var.max_replicas) == var.max_replicas
    error_message = "max_replicas must be a non-negative integer."
  }
}

variable "cpu_target" {
  description = "Average ASG CPU target as a fraction from greater than 0 through 1."
  type        = number

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target <= 1
    error_message = "cpu_target must be greater than 0 and at most 1."
  }
}

variable "runner_image" {
  description = "Prebuilt runner image. Private ECR images require pull permissions on the selected IAM role."
  type        = string
  default     = "ghcr.io/tilebox/runner:latest"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._:/@-]*$", var.runner_image))
    error_message = "runner_image must be a container image reference without whitespace or shell metacharacters."
  }
}

variable "root_volume_size_gb" {
  description = "Root gp3 EBS volume size in GiB. The volume is deleted with the instance."
  type        = number
  default     = 60

  validation {
    condition     = var.root_volume_size_gb >= 8 && floor(var.root_volume_size_gb) == var.root_volume_size_gb
    error_message = "root_volume_size_gb must be an integer of at least 8 GiB."
  }
}

variable "environment_variables" {
  description = "Plain runner environment variables. Values are stored in Terraform/OpenTofu state and EC2 user data; use secret_environment_variables for credentials."
  type        = map(string)
  default     = {}
  sensitive   = true

  validation {
    condition = alltrue([
      for name, value in var.environment_variables :
      can(regex("^[A-Za-z_][A-Za-z0-9_]*$", name)) &&
      length(regexall("[\r\n]", value)) == 0 &&
      length(split("\u0000", value)) == 1
    ])
    error_message = "Environment variable names must be shell-compatible and values must not contain CR, LF, or NUL."
  }
}

variable "secret_environment_variables" {
  description = "Runner environment variables fetched from existing AWS Secrets Manager secrets on every service start. rollout_marker can be a version ID used only to trigger an instance refresh after rotation."
  type = map(object({
    secret_arn     = string
    rollout_marker = optional(string, "")
  }))
  default = {}

  validation {
    condition = alltrue([
      for name, secret in var.secret_environment_variables :
      can(regex("^[A-Za-z_][A-Za-z0-9_]*$", name)) &&
      can(regex("^arn:[^[:space:]'\"]+$", secret.secret_arn)) &&
      length(regexall("[\r\n]", secret.rollout_marker)) == 0
    ])
    error_message = "Secret environment names must be shell-compatible, secret_arn must be an ARN without whitespace or quotes, and rollout_marker must be a single line."
  }
}

variable "iam_role_name" {
  description = "Name of an existing EC2-assumable IAM role. Set together with instance_profile_name, or leave both null for a module-owned identity."
  type        = string
  default     = null
}

variable "instance_profile_name" {
  description = "Name of the existing instance profile containing iam_role_name. Set together with iam_role_name."
  type        = string
  default     = null
}

variable "additional_secret_arns" {
  description = "Additional existing Secrets Manager ARNs that the runner role may read."
  type        = set(string)
  default     = []

  validation {
    condition     = alltrue([for arn in var.additional_secret_arns : can(regex("^arn:[^[:space:]]+$", arn))])
    error_message = "additional_secret_arns must contain valid non-empty ARNs without whitespace."
  }
}

variable "secret_kms_key_arns" {
  description = "Customer-managed KMS key ARNs needed to decrypt configured Secrets Manager secrets. The key policies must also permit the runner role."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for arn in var.secret_kms_key_arns :
      can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/[^[:space:]]+$", arn))
    ])
    error_message = "secret_kms_key_arns must contain KMS key ARNs without whitespace."
  }
}

variable "tags" {
  description = "Additional tags for module-owned AWS resources. The module's Name tag takes precedence."
  type        = map(string)
  default     = {}
}
