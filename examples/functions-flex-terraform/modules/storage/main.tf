variable "name" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "vnet_enabled" {
  type    = bool
  default = false
}
variable "containers" {
  type    = list(string)
  default = []
}

resource "azurerm_storage_account" "this" {
  name                            = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  public_network_access_enabled   = !var.vnet_enabled
  dns_endpoint_type               = "Standard"
  tags                            = var.tags

  network_rules {
    default_action = var.vnet_enabled ? "Deny" : "Allow"
    bypass         = var.vnet_enabled ? ["None"] : ["AzureServices"]
  }
}

resource "azurerm_storage_container" "this" {
  for_each              = toset(var.containers)
  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

output "id" { value = azurerm_storage_account.this.id }
output "name" { value = azurerm_storage_account.this.name }
output "primary_blob_endpoint" { value = azurerm_storage_account.this.primary_blob_endpoint }
