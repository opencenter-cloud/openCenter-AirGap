# Outputs for test orchestration

output "bastion_public_ip" {
  description = "Bastion floating IP"
  value       = openstack_networking_floatingip_v2.bastion_fip.address
}

output "bastion_private_ip" {
  description = "Bastion internal IP"
  value       = openstack_compute_instance_v2.bastion.access_ip_v4
}

output "controller_ips" {
  description = "Controller node IPs"
  value       = openstack_compute_instance_v2.controllers[*].access_ip_v4
}

output "worker_ips" {
  description = "Worker node IPs"
  value       = openstack_compute_instance_v2.workers[*].access_ip_v4
}
