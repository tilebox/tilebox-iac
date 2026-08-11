provider "aws" {
  region = var.region
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  tags = {
    "tilebox-example" = var.name
  }
}

resource "aws_vpc" "example" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.tags, {
    Name = "${var.name}-example"
  })
}

resource "aws_internet_gateway" "example" {
  vpc_id = aws_vpc.example.id

  tags = merge(local.tags, {
    Name = "${var.name}-example"
  })
}

resource "aws_subnet" "runner" {
  for_each = toset(local.availability_zones)

  vpc_id                  = aws_vpc.example.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(aws_vpc.example.cidr_block, 8, index(local.availability_zones, each.value))
  map_public_ip_on_launch = true

  tags = merge(local.tags, {
    Name = "${var.name}-${each.value}"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.example.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.example.id
  }

  tags = merge(local.tags, {
    Name = "${var.name}-public"
  })
}

resource "aws_route_table_association" "runner" {
  for_each = aws_subnet.runner

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "runner" {
  name_prefix = "${var.name}-"
  description = "Outbound access for the Tilebox runner greenfield example"
  vpc_id      = aws_vpc.example.id
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "runner_ipv4" {
  security_group_id = aws_security_group.runner.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_secretsmanager_secret" "tilebox_api_key" {
  name                    = "${var.name}-tilebox-api-key"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "tilebox_api_key" {
  secret_id     = aws_secretsmanager_secret.tilebox_api_key.id
  secret_string = var.tilebox_api_key
}

module "runner" {
  source = "../../../modules/aws"

  name               = var.name
  instance_type      = var.instance_type
  subnet_ids         = [for subnet in aws_subnet.runner : subnet.id]
  security_group_ids = [aws_security_group.runner.id]
  min_replicas       = var.min_replicas
  max_replicas       = var.max_replicas
  cpu_target         = var.cpu_target
  tags               = local.tags

  environment_variables = var.environment_variables
  secret_environment_variables = {
    TILEBOX_API_KEY = {
      secret_arn     = aws_secretsmanager_secret.tilebox_api_key.arn
      rollout_marker = aws_secretsmanager_secret_version.tilebox_api_key.version_id
    }
  }
}
