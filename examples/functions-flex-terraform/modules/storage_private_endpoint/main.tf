variable "resource_name" { type = string }
variable "storage_account_id" { type = string }
variable "subnet_id" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "enable_blob" {
  type    = bool
  default = true
}
variable "enable_queue" {
  type    = bool
  default = false
}
variable "enable_table" {
  type    = bool
  default = false
}

locals {
  subresources = compact([
    var.enable_blob ? "blob" : "",
    var.enable_queue ? "queue" : "",
    var.enable_table ? "table" : "",
  ])
}

resource "azurerm_private_endpoint" "this" {
  for_each            = toset(local.subresources)
  name                = "pe-${var.resource_name}-${each.value}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "pe-${var.resource_name}-${each.value}"
    private_connection_resource_id = var.storage_account_id
    is_manual_connection           = false
    subresource_names              = [each.value]
  }
}

output "private_endpoint_ids" {
  value = { for k, pe in azurerm_private_endpoint.this : k => pe.id }
}
