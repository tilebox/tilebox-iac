output "autoscaling_group_name" {
  value = module.runner.autoscaling_group_name
}

output "vpc_id" {
  value = aws_vpc.example.id
}
