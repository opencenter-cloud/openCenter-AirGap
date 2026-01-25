# Terraform version constraint
terraform {
  required_version = ">= 1.6.6"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "= 2.4.0"
    }

    null = {
      source  = "hashicorp/null"
      version = "= 3.2.1"
    }

    tls = {
      source  = "hashicorp/tls"
      version = "= 4.0.5"
    }

    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "= 1.54.1"
    }
  }
}
