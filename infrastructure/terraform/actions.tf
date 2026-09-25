data "github_actions_registration_token" "runner-token" {
  repository = "childcare-support-platform"
}

data "cloudinit_config" "vm-init" {
  gzip          = true
  base64_encode = true

  part {
    content_type = "text/cloud-config"
    content = templatefile("${path.module}/scripts/cloud-init.yaml", {
      GITHUB_TOKEN = data.github_actions_registration_token.runner-token.token
      GITHUB_URL   = "https://github.com/DFE-Digital/childcare-support-platform"
      RUNNER_NAME  = "${var.subscription_prefix}${var.environment_prefix}vm-${local.location_prefix}-actions-runner-01"
    })
  }
}

resource "azurerm_resource_group" "runner-group" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-actions-runners"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_network_interface" "actions-nic" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}nic-${local.location_prefix}-actions-runner-card-01"
  resource_group_name = azurerm_resource_group.runner-group.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.actions-runner.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "actions-runner" {
  location              = var.region
  name                  = "${var.subscription_prefix}${var.environment_prefix}vm-${local.location_prefix}-actions-runner-01"
  resource_group_name   = azurerm_resource_group.runner-group.name
  size                  = "Standard_D2s_v5"
  admin_username        = "adminuser"
  network_interface_ids = [azurerm_network_interface.actions-nic.id]

  identity {
    type = "SystemAssigned"
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  admin_ssh_key {
    username   = "adminuser"
    public_key = var.ssh_public_key
  }

  source_image_reference {
    offer     = "ubuntu-24_04-lts"
    publisher = "canonical"
    sku       = "server"
    version   = "latest"
  }

  custom_data = data.cloudinit_config.vm-init.rendered
}
