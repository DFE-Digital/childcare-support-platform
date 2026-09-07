output "frontend_subnet_id" {
  description = "ID of the frontend subnet (<prefix>-uks-snet-frontend)."
  value       = azurerm_subnet.res-7.id
}
