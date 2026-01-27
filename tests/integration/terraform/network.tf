# Network resources for air-gap test topology

resource "openstack_networking_network_v2" "airgap_network" {
  name           = "airgap-test-network"
  admin_state_up = true
}

resource "openstack_networking_subnet_v2" "airgap_subnet" {
  name            = "airgap-test-subnet"
  network_id      = openstack_networking_network_v2.airgap_network.id
  cidr            = var.internal_cidr
  ip_version      = 4
  dns_nameservers = var.dns_servers
}

resource "openstack_networking_router_v2" "airgap_router" {
  name                = "airgap-test-router"
  external_network_id = data.openstack_networking_network_v2.external.id
}

resource "openstack_networking_router_interface_v2" "airgap_router_interface" {
  router_id = openstack_networking_router_v2.airgap_router.id
  subnet_id = openstack_networking_subnet_v2.airgap_subnet.id
}
