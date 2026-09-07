terraform {
    required_providers {
      azurerm = {
        source = "azurerm"
        version = "4.80.0"
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