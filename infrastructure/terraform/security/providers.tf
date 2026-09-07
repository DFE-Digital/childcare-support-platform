terraform {
    required_providers {
      azurerm = {
        source = "azurerm"
        version = "4.80.0"
      }
    }
}

provider "azurerm" {
    features {}
}