# OpenStack Kubernetes Cluster Infrastructure
#
# This Terraform configuration provisions VMs for a Kubernetes cluster
# in an OpenStack environment.

# Variables
variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
  default     = "mycluster"
}

variable "control_plane_count" {
  description = "Number of control plane nodes"
  type        = number
  default     = 3
}

variable "worker_count" {
  description = "Number of worker nodes"
  type        = number
  default     = 2
}

variable "flavor" {
  description = "OpenStack flavor for VMs"
  type        = string
  default     = "m1.large"
}

variable "image" {
  description = "OpenStack image name (Ubuntu 24.04)"
  type        = string
  default     = "ubuntu-24.04"
}

variable "network" {
  description = "OpenStack network name"
  type        = string
}

variable "floating_ip_pool" {
  description = "Floating IP pool name (optional)"
  type        = string
  default     = ""
}

variable "key_pair" {
  description = "SSH key pair name"
  type        = string
}

# Data sources
data "openstack_images_image_v2" "ubuntu" {
  name        = var.image
  most_recent = true
}

data "openstack_networking_network_v2" "network" {
  name = var.network
}

# Security group
resource "openstack_networking_secgroup_v2" "k8s" {
  name        = "${var.cluster_name}-k8s-sg"
  description = "Security group for Kubernetes cluster ${var.cluster_name}"
}

# Allow SSH
resource "openstack_networking_secgroup_rule_v2" "ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.k8s.id
}

# Allow all traffic within cluster
resource "openstack_networking_secgroup_rule_v2" "cluster_internal" {
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_group_id   = openstack_networking_secgroup_v2.k8s.id
  security_group_id = openstack_networking_secgroup_v2.k8s.id
}

# Allow Kubernetes API
resource "openstack_networking_secgroup_rule_v2" "k8s_api" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 6443
  port_range_max    = 6443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.k8s.id
}

# Control plane nodes
resource "openstack_compute_instance_v2" "control_plane" {
  count           = var.control_plane_count
  name            = "${var.cluster_name}-control-${format("%02d", count.index + 1)}"
  flavor_name     = var.flavor
  image_id        = data.openstack_images_image_v2.ubuntu.id
  key_pair        = var.key_pair
  security_groups = [openstack_networking_secgroup_v2.k8s.name]

  network {
    uuid = data.openstack_networking_network_v2.network.id
  }

  metadata = {
    cluster = var.cluster_name
    role    = "control-plane"
  }
}

# Worker nodes
resource "openstack_compute_instance_v2" "worker" {
  count           = var.worker_count
  name            = "${var.cluster_name}-worker-${format("%02d", count.index + 1)}"
  flavor_name     = var.flavor
  image_id        = data.openstack_images_image_v2.ubuntu.id
  key_pair        = var.key_pair
  security_groups = [openstack_networking_secgroup_v2.k8s.name]

  network {
    uuid = data.openstack_networking_network_v2.network.id
  }

  metadata = {
    cluster = var.cluster_name
    role    = "worker"
  }
}

# Floating IPs for control plane (optional)
resource "openstack_networking_floatingip_v2" "control_plane" {
  count = var.floating_ip_pool != "" ? var.control_plane_count : 0
  pool  = var.floating_ip_pool
}

resource "openstack_compute_floatingip_associate_v2" "control_plane" {
  count       = var.floating_ip_pool != "" ? var.control_plane_count : 0
  floating_ip = openstack_networking_floatingip_v2.control_plane[count.index].address
  instance_id = openstack_compute_instance_v2.control_plane[count.index].id
}

# Outputs
output "control_plane_ips" {
  description = "IP addresses of control plane nodes"
  value       = openstack_compute_instance_v2.control_plane[*].access_ip_v4
}

output "worker_ips" {
  description = "IP addresses of worker nodes"
  value       = openstack_compute_instance_v2.worker[*].access_ip_v4
}

output "control_plane_floating_ips" {
  description = "Floating IP addresses of control plane nodes"
  value       = var.floating_ip_pool != "" ? openstack_networking_floatingip_v2.control_plane[*].address : []
}

output "security_group_id" {
  description = "Security group ID"
  value       = openstack_networking_secgroup_v2.k8s.id
}
