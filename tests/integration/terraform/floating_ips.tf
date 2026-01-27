# Floating IP for bastion

resource "openstack_networking_floatingip_v2" "bastion_fip" {
  pool = var.external_network
}

resource "openstack_compute_floatingip_associate_v2" "bastion_fip_assoc" {
  floating_ip = openstack_networking_floatingip_v2.bastion_fip.address
  instance_id = openstack_compute_instance_v2.bastion.id
}
