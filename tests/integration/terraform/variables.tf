# Test topology variables

variable "auth_url" {
  description = "OpenStack auth URL"
  type        = string
}

variable "region" {
  description = "OpenStack region"
  type        = string
}

variable "project_name" {
  description = "OpenStack project/tenant name"
  type        = string
}

variable "username" {
  description = "OpenStack username"
  type        = string
}

variable "password" {
  description = "OpenStack password"
  type        = string
  sensitive   = true
}

variable "ssh_key_name" {
  description = "SSH key pair name"
  type        = string
}

variable "image" {
  description = "Ubuntu 24.04 image name"
  type        = string
  default     = "ubuntu-24.04"
}

variable "external_network" {
  description = "External network name for floating IPs"
  type        = string
}

variable "internal_cidr" {
  description = "Internal network CIDR"
  type        = string
  default     = "192.168.100.0/24"
}

variable "dns_servers" {
  description = "DNS servers"
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

variable "bastion_flavor" {
  description = "Bastion flavor"
  type        = string
  default     = "m1.medium"
}

variable "controller_flavor" {
  description = "Controller flavor"
  type        = string
  default     = "m1.large"
}

variable "controller_count" {
  description = "Number of controller nodes"
  type        = number
  default     = 3
}

variable "worker_flavor" {
  description = "Worker flavor"
  type        = string
  default     = "m1.large"
}

variable "worker_count" {
  description = "Number of worker nodes"
  type        = number
  default     = 2
}
