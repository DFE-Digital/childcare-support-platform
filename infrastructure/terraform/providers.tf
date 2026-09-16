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
    use_oidc         = true
    use_azuread_auth = true
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_provider_registration" "cdn-reg" {
  name = "Microsoft.Cdn"
}

resource "azurerm_resource_provider_registration" "compute-reg" {
  name = "Microsoft.Compute"
}

resource "azurerm_resource_provider_registration" "web-reg" {
  name = "Microsoft.Web"
}

resource "azurerm_resource_provider_registration" "kv-reg" {
  name = "Microsoft.KeyVault"
}
