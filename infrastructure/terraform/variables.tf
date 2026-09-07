variable "subscription_prefix" {
  description = "Short subscription code forming the first segment of the resource naming prefix (e.g. \"s288\")."
  type        = string
}

variable "environment_prefix" {
  description = "Short environment code forming the second segment of the resource naming prefix (e.g. \"d01\")."
  type        = string
}

variable "region" {
  description = "Azure region for resources that follow the primary deployment region (e.g. \"uksouth\"). Resources pinned to a different region (such as the ukwest API Management instance) are not parameterised by this variable."
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the (externally managed) Log Analytics workspace used by Application Insights. Not created by this configuration, so it must be supplied."
  type        = string
}
