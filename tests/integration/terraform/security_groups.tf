# Security groups for air-gap topology

# Bastion - internet access allowed
resource "openstack_networking_secgroup_v2" "bastion_sg" {
  name        = "airgap-bastion-sg"
  description = "Bastion security group - internet access allowed"
}

resource "openstack_networking_secgroup_rule_v2" "bastion_ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.bastion_sg.id
}

resource "openstack_networking_secgroup_rule_v2" "bastion_egress" {
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.bastion_sg.id
}

# Air-gapped nodes - no internet access
resource "openstack_networking_secgroup_v2" "airgap_sg" {
  name        = "airgap-nodes-sg"
  description = "Air-gapped nodes - no internet access"
}

resource "openstack_networking_secgroup_rule_v2" "airgap_internal" {
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = var.internal_cidr
  security_group_id = openstack_networking_secgroup_v2.airgap_sg.id
}

resource "openstack_networking_secgroup_rule_v2" "airgap_egress_internal" {
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = var.internal_cidr
  security_group_id = openstack_networking_secgroup_v2.airgap_sg.id
}
