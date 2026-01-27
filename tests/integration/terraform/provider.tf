provider "openstack" {
  auth_url    = var.auth_url
  region      = var.region
  tenant_name = var.project_name
  user_name   = var.username
  password    = var.password
}
