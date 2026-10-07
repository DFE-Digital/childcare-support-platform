output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = azurerm_key_vault.key-vault.name
}

output "security_rg_name" {
  description = "The name of the security resource group"
  value       = azurerm_resource_group.security.name
}

output "storage_group_name" {
  description = "The name of the storage resource group"
  value       = azurerm_resource_group.storage.name
}

output "storage_account_name" {
  description = "The name of the storage account"
  value       = azurerm_storage_account.site-data.name
}

output "storage_container_name" {
  description = "The name of the storage container with source data in"
  value       = azurerm_storage_container.source-data-container.name
}