variable "subscription_prefix" {
  description = "Short subscription code forming the first segment of the resource naming prefix (e.g. \"s288\")."
  type        = string
}

variable "environment_prefix" {
  description = "Short environment code forming the second segment of the resource naming prefix (e.g. \"d01\")."
  type        = string
}

variable "frontend_subnet_id" {
  description = "ID of the core module's frontend subnet, used by the storage private endpoint."
  type        = string
}

variable "apim_identity_id" {
  description = "ID of the security module's API Management user-assigned identity."
  type        = string
}

variable "frontdoor_identity_id" {
  description = "ID of the security module's Front Door user-assigned identity."
  type        = string
}

variable "storage_account_id" {
  description = "ID of the storage module's primary storage account, used by Front Door's private link origin and private endpoint."
  type        = string
}

variable "storage_account_name" {
  description = "Name of the storage module's primary storage account, used in the Front Door private link request message."
  type        = string
}

variable "storage_primary_web_host" {
  description = "Static website hostname of the storage module's primary storage account, used by Front Door's default origin."
  type        = string
}

variable "storage_primary_blob_host" {
  description = "Blob endpoint hostname of the storage module's primary storage account, used by Front Door's runtime-data origin."
  type        = string
}

variable "region" {
  description = "Azure region for resources that follow the primary deployment region (e.g. \"uksouth\"). The ukwest API Management instance is not parameterised by this variable."
  type        = string
}

variable "application_insights_instrumentation_key" {
  description = "Instrumentation key of the runtime module's Application Insights resource, used by the API Management logger."
  type        = string
  sensitive   = true
}
