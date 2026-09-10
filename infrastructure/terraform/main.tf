terraform {
  required_providers {
    azurerm = {
      source  = "azurerm"
      version = "5.4.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "azurerm" {
    use_oidc = true
  }
}

module "core" {
  source = "./core"

  subscription_prefix       = var.subscription_prefix
  environment_prefix        = var.environment_prefix
  region                    = var.region
  remote_virtual_network_id = var.remote_virtual_network_id
}

module "edge" {
  source = "./edge"

  subscription_prefix       = var.subscription_prefix
  environment_prefix        = var.environment_prefix
  region                    = var.region
  frontend_subnet_id        = module.core.frontend_subnet_id
  apim_identity_id          = module.security.apim_identity_id
  frontdoor_identity_id     = module.security.frontdoor_identity_id
  storage_account_id        = module.storage.storage_account_id
  storage_account_name      = module.storage.storage_account_name
  storage_primary_web_host  = module.storage.primary_web_host
  storage_primary_blob_host = module.storage.primary_blob_host

  function_app_default_hostname = module.runtime.function_app_default_hostname
}

module "runtime" {
  source = "./runtime"

  subscription_prefix   = var.subscription_prefix
  environment_prefix    = var.environment_prefix
  region                = var.region
  api_management_api_id = module.edge.api_management_api_id
  azf_identity_id       = module.security.azf_identity_id
  unique_suffix         = random_id.unique_suffix.hex
}

module "security" {
  source = "./security"

  subscription_prefix = var.subscription_prefix
  environment_prefix  = var.environment_prefix
  region              = var.region
}

module "storage" {
  source = "./storage"

  subscription_prefix = var.subscription_prefix
  environment_prefix  = var.environment_prefix
  region              = var.region
  unique_suffix       = random_id.unique_suffix.hex
}
