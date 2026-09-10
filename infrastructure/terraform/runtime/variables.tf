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

variable "azf_identity_id" {
  description = "ID of the security module's function app user-assigned identity."
  type        = string
}

variable "unique_suffix" {
  description = "Random 4-hex-digit suffix used to keep globally-unique resource names (e.g. the storage account) unique across deployments."
  type        = string
}
