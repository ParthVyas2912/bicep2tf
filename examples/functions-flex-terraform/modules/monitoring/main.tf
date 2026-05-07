variable "log_analytics_name" { type = string }
variable "application_insights_name" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = var.log_analytics_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                          = var.application_insights_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  workspace_id                  = azurerm_log_analytics_workspace.this.id
  application_type              = "web"
  local_authentication_disabled = true
  tags                          = var.tags
}

output "log_analytics_id" { value = azurerm_log_analytics_workspace.this.id }
output "application_insights_id" { value = azurerm_application_insights.this.id }
output "application_insights_name" { value = azurerm_application_insights.this.name }
output "application_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}
