data "azurerm_resource_group" "res-0" {
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-security"
}

data "azurerm_key_vault" "res-1" {
  name = "${var.subscription_prefix}${var.environment_prefix}kv-${local.location_prefix}-vault-01"
  resource_group_name = azurerm_resource_group.res-0.name
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
