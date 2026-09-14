terraform {
  required_providers {
    azurerm = {
      source  = "azurerm"
      version = "5.4.0"
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
}

provider "azurerm" {
  features {}
}

provider "github" {
  owner = "DFE-Digital"
  # Not including the `token` parameter here as it should be set by GITHUB_TOKEN in the environment
}
