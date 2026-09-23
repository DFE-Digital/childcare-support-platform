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
  description = "Azure region for resources that follow the primary deployment region (e.g. \"uksouth\"). Resources pinned to a different region (such as the ukwest API Management instance) are not parameterised by this variable."
  type        = string
}

variable "remote_virtual_network_id" {
  description = "ID of a remote (hub) virtual network to peer the core vnet with. When null, no peering is created."
  type        = string
  default     = null
}

variable "ssh_public_key" {
  description = "SSH public key to associate with the admin account for the actions runner VM"
  type        = string
}

variable "support_alert_email" {
  description = "The email account used by the monitoring config for alerting"
  type        = string
  sensitive   = true
}
