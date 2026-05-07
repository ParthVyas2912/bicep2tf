variable "vnet_name" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "address_space" {
  type    = list(string)
  default = ["10.0.0.0/16"]
}
variable "pe_subnet_name" {
  type    = string
  default = "private-endpoints-subnet"
}
variable "app_subnet_name" {
  type    = string
  default = "app"
}

resource "azurerm_virtual_network" "this" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space
  tags                = var.tags
}

resource "azurerm_subnet" "pe" {
  name                              = var.pe_subnet_name
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = ["10.0.1.0/24"]
  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_subnet" "app" {
  name                              = var.app_subnet_name
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = ["10.0.2.0/24"]
  private_endpoint_network_policies = "Disabled"

  delegation {
    name = "appservice-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

output "vnet_id" { value = azurerm_virtual_network.this.id }
output "vnet_name" { value = azurerm_virtual_network.this.name }
output "pe_subnet_id" { value = azurerm_subnet.pe.id }
output "pe_subnet_name" { value = azurerm_subnet.pe.name }
output "app_subnet_id" { value = azurerm_subnet.app.id }
output "app_subnet_name" { value = azurerm_subnet.app.name }
