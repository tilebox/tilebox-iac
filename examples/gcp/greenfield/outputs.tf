output "instance_group" {
  value = module.runner.instance_group
}

output "network_self_link" {
  value = google_compute_network.example.self_link
}
