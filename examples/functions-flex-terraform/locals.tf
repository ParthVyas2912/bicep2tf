locals {
  abbrs = jsondecode(file("${path.module}/../infra - bicep/abbreviations.json"))

  resource_token = lower(substr(sha1(join("-", [var.environment_name, var.location])), 0, 13))

  base_tags = merge({
    "azd-env-name" = var.environment_name
  }, var.tags)

  resource_group_name = coalesce(
    var.resource_group_name,
    "${local.abbrs.resourcesResourceGroups}${var.environment_name}"
  )

  function_app_name = coalesce(
    var.api_service_name,
    "${local.abbrs.webSitesFunctions}qsp-${local.resource_token}"
  )

  storage_account_name = lower(replace(coalesce(
    var.storage_account_name,
    "${local.abbrs.storageStorageAccounts}${local.resource_token}"
  ), "-", ""))

  identity_name = coalesce(
    var.api_user_assigned_identity_name,
    "${local.abbrs.managedIdentityUserAssignedIdentities}api-${local.resource_token}"
  )

  app_insights_name = coalesce(
    var.application_insights_name,
    "${local.abbrs.insightsComponents}${local.resource_token}"
  )

  app_service_plan_name = coalesce(
    var.app_service_plan_name,
    "qsp-${local.abbrs.webServerFarms}${local.resource_token}"
  )

  log_analytics_name = coalesce(
    var.log_analytics_name,
    "${local.abbrs.operationalInsightsWorkspaces}${local.resource_token}"
  )

  vnet_name = coalesce(
    var.vnet_name,
    "${local.abbrs.networkVirtualNetworks}${local.resource_token}"
  )

  deployment_storage_container_name = "app-package-${substr(local.function_app_name, 0, min(32, length(local.function_app_name)))}-${substr(lower(sha1("${local.function_app_name}-${local.resource_token}")), 0, 7)}"

  storage_endpoint_config = {
    enable_blob                   = true
    enable_queue                  = true
    enable_table                  = false
    enable_files                  = false
    allow_user_identity_principal = true
  }
}
