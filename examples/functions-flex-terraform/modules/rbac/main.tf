variable "storage_account_id" { type = string }
variable "application_insights_id" { type = string }
variable "managed_identity_principal_id" { type = string }
variable "user_identity_principal_id" {
  type    = string
  default = ""
}
variable "enable_blob" {
  type    = bool
  default = true
}
variable "allow_user_identity_principal" {
  type    = bool
  default = true
}

# Storage Blob Data Owner
locals {
  storage_blob_data_owner      = "Storage Blob Data Owner"
  monitoring_metrics_publisher = "Monitoring Metrics Publisher"
}

resource "azurerm_role_assignment" "storage_mi" {
  count                = var.enable_blob ? 1 : 0
  scope                = var.storage_account_id
  role_definition_name = local.storage_blob_data_owner
  principal_id         = var.managed_identity_principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "storage_user" {
  count                = (var.enable_blob && var.allow_user_identity_principal && length(var.user_identity_principal_id) > 0) ? 1 : 0
  scope                = var.storage_account_id
  role_definition_name = local.storage_blob_data_owner
  principal_id         = var.user_identity_principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "appinsights_mi" {
  scope                = var.application_insights_id
  role_definition_name = local.monitoring_metrics_publisher
  principal_id         = var.managed_identity_principal_id
  principal_type       = "ServicePrincipal"
}
