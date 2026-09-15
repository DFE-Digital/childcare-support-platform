output "azf_identity_id" {
  description = "ID of the function app user-assigned identity (azurerm_user_assigned_identity.res-3)."
  value       = azurerm_user_assigned_identity.res-3.id
}

output "frontdoor_identity_id" {
  description = "ID of the Front Door user-assigned identity (azurerm_user_assigned_identity.res-4)."
  value       = azurerm_user_assigned_identity.res-4.id
}

output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = azurerm_key_vault.res-1.name
}

output "security_rg_name" {
  description = "The name of the security resource group"
  value       = azurerm_resource_group.res-0.name
}