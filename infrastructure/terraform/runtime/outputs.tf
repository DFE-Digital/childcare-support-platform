output "application_insights_instrumentation_key" {
  description = "Instrumentation key of the Application Insights resource (azurerm_application_insights.runtime-insights), used by the API Management logger."
  value       = azurerm_application_insights.runtime-insights.instrumentation_key
  sensitive   = true
}

output "function_app_default_hostname" {
  description = "Real, Azure-assigned default hostname of the runtime module's function app, used by APIM's backend."
  value       = azurerm_function_app_flex_consumption.consumption-plan.default_hostname
  sensitive   = true
}

output "function_app_id" {
  description = "ID of the function app (azurerm_function_app_flex_consumption.consumption-plan), used by its private endpoint."
  value       = azurerm_function_app_flex_consumption.consumption-plan.id
}
