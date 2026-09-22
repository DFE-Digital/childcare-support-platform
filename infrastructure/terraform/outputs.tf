output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = module.security.keyvault_name
}

output "security_rg_name" {
  description = "The name of the security resource group"
  value       = module.security.security_rg_name
}