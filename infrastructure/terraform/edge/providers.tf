terraform {
    required_providers {
      azurerm = {
        source = "azurerm"
        version = "5.4.0"
      }
    random = {
      source = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
    features {}
}