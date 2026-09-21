output "azf_identity_id" {
  description = "ID of the function app user-assigned identity (azurerm_user_assigned_identity.azf-identity)."
  value       = azurerm_user_assigned_identity.azf-identity.id
}

output "frontdoor_identity_id" {
  description = "ID of the Front Door user-assigned identity (azurerm_user_assigned_identity.frontdoor-identity)."
  value       = azurerm_user_assigned_identity.frontdoor-identity.id
}

output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = azurerm_key_vault.key-vault.name
}

output "security_rg_name" {
  description = "The name of the security resource group"
  value       = azurerm_resource_group.security.name
}