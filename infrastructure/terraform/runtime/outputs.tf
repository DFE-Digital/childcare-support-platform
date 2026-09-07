output "application_insights_instrumentation_key" {
  description = "Instrumentation key of the Application Insights resource (azurerm_application_insights.res-19), used by the API Management logger."
  value       = azurerm_application_insights.res-19.instrumentation_key
  sensitive   = true
}
