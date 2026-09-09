output "apim_identity_id" {
  description = "ID of the API Management user-assigned identity (azurerm_user_assigned_identity.res-2)."
  value       = azurerm_user_assigned_identity.res-2.id
}

output "azf_identity_id" {
  description = "ID of the function app user-assigned identity (azurerm_user_assigned_identity.res-3)."
  value       = azurerm_user_assigned_identity.res-3.id
}

output "frontdoor_identity_id" {
  description = "ID of the Front Door user-assigned identity (azurerm_user_assigned_identity.res-4)."
  value       = azurerm_user_assigned_identity.res-4.id
}
