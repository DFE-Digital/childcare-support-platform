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

    cloudinit = {
      source  = "hashicorp/cloudinit"
      version = "2.4.1"
    }

    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  backend "azurerm" {
    use_oidc         = true
    use_azuread_auth = true
  }
}

provider "github" {
  owner = "DFE-Digital"
  # Not including the `token` parameter here as it should be set by GITHUB_TOKEN in the environment
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

resource "azurerm_resource_provider_registration" "cdn-reg" {
  name = "Microsoft.Cdn"
}

resource "azurerm_resource_provider_registration" "compute-reg" {
  name = "Microsoft.Compute"
}

resource "azurerm_resource_provider_registration" "kv-reg" {
  name = "Microsoft.KeyVault"
}

# Microsoft.Web registration: stop managing it without unregistering it in Azure
removed {
  from = azurerm_resource_provider_registration.web-reg

  lifecycle {
    destroy = false
  }
}
