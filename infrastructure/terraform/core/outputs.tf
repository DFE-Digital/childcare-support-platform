output "frontend_subnet_id" {
  description = "ID of the frontend subnet (<prefix>-uks-snet-frontend)."
  value       = azurerm_subnet.frontend.id
}

output "runners_subnet_id" {
  description = "ID of the runners subnet (<prefix>-uks-snet-githubActionsRunner)."
  value       = azurerm_subnet.actions-runner.id
}