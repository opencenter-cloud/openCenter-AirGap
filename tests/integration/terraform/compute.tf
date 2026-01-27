# Compute instances for air-gap test topology

# Bastion instance
resource "openstack_compute_instance_v2" "bastion" {
  name            = "airgap-bastion"
  flavor_name     = var.bastion_flavor
  image_name      = var.image
  key_pair        = var.ssh_key_name
  security_groups = [openstack_networking_secgroup_v2.bastion_sg.name]

  network {
    uuid = openstack_networking_network_v2.airgap_network.id
  }
}

# Controller instances
resource "openstack_compute_instance_v2" "controllers" {
  count           = var.controller_count
  name            = "airgap-controller-${count.index + 1}"
  flavor_name     = var.controller_flavor
  image_name      = var.image
  key_pair        = var.ssh_key_name
  security_groups = [openstack_networking_secgroup_v2.airgap_sg.name]

  network {
    uuid = openstack_networking_network_v2.airgap_network.id
  }
}

# Worker instances
resource "openstack_compute_instance_v2" "workers" {
  count           = var.worker_count
  name            = "airgap-worker-${count.index + 1}"
  flavor_name     = var.worker_flavor
  image_name      = var.image
  key_pair        = var.ssh_key_name
  security_groups = [openstack_networking_secgroup_v2.airgap_sg.name]

  network {
    uuid = openstack_networking_network_v2.airgap_network.id
  }
}
