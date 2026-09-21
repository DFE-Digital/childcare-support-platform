terraform {
  required_providers {
    azurerm = {
      source  = "azurerm"
      version = "5.4.0"
    }
  }
}

provider "azurerm" {
  features {}
}
