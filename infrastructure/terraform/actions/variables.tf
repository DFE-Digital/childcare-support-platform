variable "subscription_prefix" {
  description = "Short subscription code forming the first segment of the resource naming prefix (e.g. \"s288\")."
  type        = string
}

variable "environment_prefix" {
  description = "Short environment code forming the second segment of the resource naming prefix (e.g. \"d01\")."
  type        = string
}

variable "environment_tag" {
  description = "Environment name for the required tag"
  type        = string
}

variable "region" {
  description = "Azure region for resources that follow the primary deployment region (e.g. \"uksouth\")."
  type        = string
}

variable "runners_subnet_id" {
  description = "ID of the core module's runners subnet, used by the virtual machines private endpoint"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key to associate with the admin account for the actions runner VM"
  type        = string
}
