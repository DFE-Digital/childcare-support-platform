variable "subscription_prefix" {
  description = "Short subscription code forming the first segment of the resource naming prefix (e.g. \"s288\")."
  type        = string
}

variable "environment_prefix" {
  description = "Short environment code forming the second segment of the resource naming prefix (e.g. \"d01\")."
  type        = string
}

variable "region" {
  description = "Azure region for resources that follow the primary deployment region (e.g. \"uksouth\")."
  type        = string
}

variable "remote_virtual_network_id" {
  description = "ID of a remote (hub) virtual network to peer with. When null, no peering is created."
  type        = string
  default     = null
}
