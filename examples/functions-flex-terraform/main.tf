resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.base_tags
}

module "identity" {
  source              = "./modules/identity"
  name                = local.identity_name
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.base_tags
}

module "monitoring" {
  source                    = "./modules/monitoring"
  log_analytics_name        = local.log_analytics_name
  application_insights_name = local.app_insights_name
  location                  = var.location
  resource_group_name       = azurerm_resource_group.main.name
  tags                      = local.base_tags
}

module "storage" {
  source              = "./modules/storage"
  name                = local.storage_account_name
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.base_tags
  vnet_enabled        = var.vnet_enabled
  containers          = [local.deployment_storage_container_name, "qsp"]
}

module "networking" {
  source              = "./modules/networking"
  count               = var.vnet_enabled ? 1 : 0
  vnet_name           = local.vnet_name
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.base_tags
}

module "storage_private_endpoint" {
  source              = "./modules/storage_private_endpoint"
  count               = var.vnet_enabled ? 1 : 0
  resource_name       = module.storage.name
  storage_account_id  = module.storage.id
  subnet_id           = module.networking[0].pe_subnet_id
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.base_tags
  enable_blob         = local.storage_endpoint_config.enable_blob
  enable_queue        = local.storage_endpoint_config.enable_queue
  enable_table        = local.storage_endpoint_config.enable_table
}

module "rbac" {
  source                        = "./modules/rbac"
  storage_account_id            = module.storage.id
  application_insights_id       = module.monitoring.application_insights_id
  managed_identity_principal_id = module.identity.principal_id
  user_identity_principal_id    = var.principal_id
  enable_blob                   = local.storage_endpoint_config.enable_blob
  allow_user_identity_principal = local.storage_endpoint_config.allow_user_identity_principal
}

module "api" {
  source              = "./modules/api"
  name                = local.function_app_name
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.base_tags
  service_name        = "qsp-api"

  app_service_plan_name        = local.app_service_plan_name
  existing_app_service_plan_id = var.existing_app_service_plan_id

  storage_account_name              = module.storage.name
  storage_primary_blob_endpoint     = module.storage.primary_blob_endpoint
  deployment_storage_container_name = local.deployment_storage_container_name

  identity_id                   = module.identity.id
  identity_client_id            = module.identity.client_id
  application_insights_conn_str = module.monitoring.application_insights_connection_string

  virtual_network_subnet_id = var.vnet_enabled ? module.networking[0].app_subnet_id : null

  enable_blob  = local.storage_endpoint_config.enable_blob
  enable_queue = local.storage_endpoint_config.enable_queue
  enable_table = local.storage_endpoint_config.enable_table

  runtime_name    = "python"
  runtime_version = "3.12"
}
