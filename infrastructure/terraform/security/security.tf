terraform {
  required_providers {
    azurerm = {
      source  = "azurerm"
      version = "4.80.0"
    }
  }
}
provider "azurerm" {
  features {}
}
resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-security"
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}
resource "azurerm_key_vault" "res-1" {
  access_policy                   = []
  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = false
  location                        = var.region
  name                            = "${var.subscription_prefix}${var.environment_prefix}kv-${local.location_prefix}-vault-01"
  public_network_access_enabled   = false
  purge_protection_enabled        = true
  rbac_authorization_enabled      = true
  resource_group_name             = azurerm_resource_group.res-0.name
  sku_name                        = "standard"
  soft_delete_retention_days      = 90
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  tenant_id = "fad277c9-c60a-4da1-b5f3-b3b8b34a82f9"
  network_acls {
    bypass                     = "None"
    default_action             = "Deny"
    ip_rules                   = []
    virtual_network_subnet_ids = []
  }
}
resource "azurerm_user_assigned_identity" "res-2" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}mi-${local.location_prefix}-apim-identity-01"
  resource_group_name = azurerm_resource_group.res-0.name
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}
resource "azurerm_user_assigned_identity" "res-3" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}mi-${local.location_prefix}-azf-identity-01"
  resource_group_name = azurerm_resource_group.res-0.name
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}
resource "azurerm_user_assigned_identity" "res-4" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}mi-${local.location_prefix}-frontdoor-identity-01"
  resource_group_name = azurerm_resource_group.res-0.name
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}
