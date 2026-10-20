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

output "runtime_group_name" {
  description = "The name of the runtime resource group"
  value       = azurerm_resource_group.runtime.name
}

output "function_app_name" {
  description = "The name of the azure function app"
  value       = azurerm_function_app_flex_consumption.consumption-plan.name
}