output "keyvault_name" {
  description = "The name of the keyvault created by the Terraform"
  value       = module.security.keyvault_name
}
