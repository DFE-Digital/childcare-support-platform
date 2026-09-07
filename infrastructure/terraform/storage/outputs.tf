output "storage_account_id" {
  description = "ID of the primary storage account (azurerm_storage_account.res-1), used by Front Door's private link origin and private endpoint."
  value       = azurerm_storage_account.res-1.id
}

output "storage_account_name" {
  description = "Name of the primary storage account (azurerm_storage_account.res-1)."
  value       = azurerm_storage_account.res-1.name
}

output "primary_web_host" {
  description = "Static website hostname of the primary storage account, used by Front Door's default origin."
  value       = azurerm_storage_account.res-1.primary_web_host
}

output "primary_blob_host" {
  description = "Blob endpoint hostname of the primary storage account, used by Front Door's runtime-data origin."
  value       = azurerm_storage_account.res-1.primary_blob_host
}
