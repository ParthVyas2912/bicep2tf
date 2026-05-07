variable "name" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "service_name" {
  type    = string
  default = "qsp-api"
}

variable "app_service_plan_name" { type = string }
variable "existing_app_service_plan_id" {
  type    = string
  default = ""
}

variable "storage_account_name" { type = string }
variable "storage_primary_blob_endpoint" { type = string }
variable "deployment_storage_container_name" { type = string }

variable "identity_id" { type = string }
variable "identity_client_id" { type = string }

variable "application_insights_conn_str" {
  type      = string
  sensitive = true
}

variable "virtual_network_subnet_id" {
  type    = string
  default = null
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

variable "runtime_name" {
  type    = string
  default = "python"
}
variable "runtime_version" {
  type    = string
  default = "3.12"
}
variable "instance_memory_mb" {
  type    = number
  default = 2048
}
variable "maximum_instance_count" {
  type    = number
  default = 100
}

resource "azurerm_service_plan" "this" {
  count               = var.existing_app_service_plan_id == "" ? 1 : 0
  name                = var.app_service_plan_name
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = var.tags
}

locals {
  service_plan_id = var.existing_app_service_plan_id != "" ? var.existing_app_service_plan_id : azurerm_service_plan.this[0].id

  app_settings = merge(
    {
      AzureWebJobsStorage__credential           = "managedidentity"
      AzureWebJobsStorage__clientId             = var.identity_client_id
      AzureWebJobsStorage__accountName          = var.storage_account_name
      APPLICATIONINSIGHTS_AUTHENTICATION_STRING = "ClientId=${var.identity_client_id};Authorization=AAD"
      APPLICATIONINSIGHTS_CONNECTION_STRING     = var.application_insights_conn_str
    },
    var.enable_blob ? { AzureWebJobsStorage__blobServiceUri = var.storage_primary_blob_endpoint } : {},
    var.enable_queue ? { AzureWebJobsStorage__queueServiceUri = replace(var.storage_primary_blob_endpoint, ".blob.", ".queue.") } : {},
    var.enable_table ? { AzureWebJobsStorage__tableServiceUri = replace(var.storage_primary_blob_endpoint, ".blob.", ".table.") } : {},
  )
}

resource "azurerm_function_app_flex_consumption" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_plan_id     = local.service_plan_id

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${var.storage_primary_blob_endpoint}${var.deployment_storage_container_name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = var.identity_id

  runtime_name    = var.runtime_name
  runtime_version = var.runtime_version

  instance_memory_in_mb     = var.instance_memory_mb
  maximum_instance_count    = var.maximum_instance_count
  virtual_network_subnet_id = var.virtual_network_subnet_id
  https_only                = true

  app_settings = local.app_settings

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }

  site_config {
    minimum_tls_version = "1.2"
    cors {
      allowed_origins     = ["https://portal.azure.com", "https://ms.portal.azure.com"]
      support_credentials = false
    }
  }

  tags = merge(var.tags, { "azd-service-name" = var.service_name })
}

output "function_app_id" { value = azurerm_function_app_flex_consumption.this.id }
output "function_app_name" { value = azurerm_function_app_flex_consumption.this.name }
output "function_app_default_hostname" { value = azurerm_function_app_flex_consumption.this.default_hostname }
