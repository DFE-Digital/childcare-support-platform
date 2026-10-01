output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = azurerm_key_vault.key-vault.name
}

output "security_rg_name" {
  description = "The name of the security resource group"
  value       = azurerm_resource_group.security.name
}