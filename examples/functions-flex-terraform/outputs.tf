output "AZURE_LOCATION" {
  value = var.location
}

output "AZURE_TENANT_ID" {
  value = data.azurerm_client_config.current.tenant_id
}

output "AZURE_RESOURCE_GROUP" {
  value = azurerm_resource_group.main.name
}

output "SERVICE_API_NAME" {
  value = module.api.function_app_name
}

output "AZURE_FUNCTION_NAME" {
  value = module.api.function_app_name
}

output "APPLICATIONINSIGHTS_CONNECTION_STRING" {
  value     = module.monitoring.application_insights_connection_string
  sensitive = true
}

data "azurerm_client_config" "current" {}
