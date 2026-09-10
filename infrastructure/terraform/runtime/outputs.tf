output "application_insights_instrumentation_key" {
  description = "Instrumentation key of the Application Insights resource (azurerm_application_insights.res-19), used by the API Management logger."
  value       = azurerm_application_insights.res-19.instrumentation_key
  sensitive   = true
}

output "function_app_default_hostname" {
  description = "Real, Azure-assigned default hostname of the runtime module's function app, used by APIM's backend."
  value       = azurerm_function_app_flex_consumption.res-11.default_hostname
  sensitive   = true
}

output "function_app_id" {
  description = "ID of the function app (azurerm_function_app_flex_consumption.res-11), used by its private endpoint."
  value       = azurerm_function_app_flex_consumption.res-11.id
}
