# Resource type coverage

Status legend: ✅ supported · 🟡 partial · ❌ unmapped (emits TODO).

Tracked against `hashicorp/azurerm ~> 4.0`.

| ARM type | Terraform type | Status | Notes |
|---|---|---|---|
| `Microsoft.Resources/resourceGroups` | `azurerm_resource_group` | ✅ | |
| `Microsoft.ManagedIdentity/userAssignedIdentities` | `azurerm_user_assigned_identity` | ✅ | |
| `Microsoft.Authorization/roleAssignments` | `azurerm_role_assignment` | ✅ | `scope`, `role_definition_name`, `principal_type` derived. |
| `Microsoft.Web/serverfarms` | `azurerm_service_plan` | ✅ | FlexConsumption (`FC1`) supported. |
| `Microsoft.Web/sites` (function app, Linux, Flex) | `azurerm_function_app_flex_consumption` | ✅ | |
| `Microsoft.Web/sites` (web app, Linux) | `azurerm_linux_web_app` | ✅ | |
| `Microsoft.Web/sites/config` (`appsettings`, `web`, `logs`, `authsettingsV2`) | inlined into parent | 🟡 | Merged into `app_settings` / `site_config` / `auth_settings_v2`. |
| `Microsoft.Web/sites/slots` | `azurerm_linux_web_app_slot` | 🟡 | |
| `Microsoft.Web/sites/extensions` (`MSDeploy`) | n/a | ❌ | Use deployment pipelines. |
| `Microsoft.Storage/storageAccounts` | `azurerm_storage_account` | ✅ | |
| `Microsoft.Storage/storageAccounts/blobServices` | inlined | ✅ | Mapped to `blob_properties`. |
| `Microsoft.Storage/storageAccounts/blobServices/containers` | `azurerm_storage_container` | ✅ | |
| `Microsoft.Storage/storageAccounts/managementPolicies` | `azurerm_storage_management_policy` | ✅ | |
| `Microsoft.Storage/storageAccounts/fileServices/shares` | `azurerm_storage_share` | ✅ | |
| `Microsoft.KeyVault/vaults` | `azurerm_key_vault` | ✅ | |
| `Microsoft.KeyVault/vaults/accessPolicies` | `azurerm_key_vault_access_policy` | ✅ | |
| `Microsoft.KeyVault/vaults/secrets` | `azurerm_key_vault_secret` | 🟡 | Values must come from variables marked `sensitive`. |
| `Microsoft.Insights/components` | `azurerm_application_insights` | ✅ | Workspace-based. |
| `Microsoft.OperationalInsights/workspaces` | `azurerm_log_analytics_workspace` | ✅ | |
| `Microsoft.OperationsManagement/solutions` | `azurerm_log_analytics_solution` | 🟡 | |
| `Microsoft.SecurityInsights/*` | `azurerm_sentinel_*` | 🟡 | Subset supported. |
| `Microsoft.Network/virtualNetworks` | `azurerm_virtual_network` | ✅ | |
| `Microsoft.Network/virtualNetworks/subnets` | `azurerm_subnet` | ✅ | Delegations supported. |
| `Microsoft.Network/virtualNetworks/virtualNetworkPeerings` | `azurerm_virtual_network_peering` | ✅ | |
| `Microsoft.Network/privateEndpoints` | `azurerm_private_endpoint` | ✅ | |
| `Microsoft.Network/privateDnsZones` | `azurerm_private_dns_zone` | ✅ | |
| `Microsoft.Network/networkSecurityGroups` | `azurerm_network_security_group` | ✅ | |
| `Microsoft.Network/publicIPAddresses` | `azurerm_public_ip` | ✅ | |
| `Microsoft.ContainerRegistry/registries` | `azurerm_container_registry` | ✅ | |
| `Microsoft.ContainerService/managedClusters` | `azurerm_kubernetes_cluster` | 🟡 | Common attributes only. |
| `Microsoft.App/managedEnvironments` | `azurerm_container_app_environment` | ✅ | |
| `Microsoft.App/containerApps` | `azurerm_container_app` | ✅ | |
| `Microsoft.DocumentDB/databaseAccounts` | `azurerm_cosmosdb_account` | ✅ | |
| `Microsoft.Sql/servers` | `azurerm_mssql_server` | ✅ | |
| `Microsoft.DBforPostgreSQL/flexibleServers` | `azurerm_postgresql_flexible_server` | ✅ | |
| `Microsoft.ServiceBus/namespaces` | `azurerm_servicebus_namespace` | ✅ | |
| `Microsoft.EventHub/namespaces` | `azurerm_eventhub_namespace` | ✅ | |
| `Microsoft.CognitiveServices/accounts` | `azurerm_cognitive_account` | 🟡 | OpenAI subkind partial. |

> Generated. Re-run `python tools/regen_coverage.py` to update.
