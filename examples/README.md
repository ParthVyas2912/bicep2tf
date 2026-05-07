# Example: Azure Functions (Flex Consumption) with optional VNet

This example shows the same workload expressed in both formats:

- [`functions-flex-bicep/`](./functions-flex-bicep/) — original Bicep input
  (subscription-scope, AVM modules, optional VNet integration, RBAC).
- [`functions-flex-terraform/`](./functions-flex-terraform/) — output
  produced by `bicep2tf`, validated with `hashicorp/azurerm ~> 4.0`.

## Reproduce

```bash
bicep2tf functions-flex-bicep/main.bicep -o functions-flex-terraform
cd functions-flex-terraform
terraform init && terraform validate
```

## What's in the Terraform output

- `azurerm_resource_group.main` — created at subscription scope.
- `modules/identity/` — user-assigned managed identity for the function app.
- `modules/monitoring/` — Log Analytics workspace + workspace-based App Insights.
- `modules/storage/` — Storage account + deployment / app containers.
- `modules/networking/` — VNet + `app` and `private-endpoints` subnets
  (created only when `vnet_enabled = true`).
- `modules/storage_private_endpoint/` — per-subresource private endpoints
  for the storage account, created only when `vnet_enabled = true`.
- `modules/rbac/` — Storage Blob Data Owner + Monitoring Metrics Publisher
  role assignments, with optional user-principal grant for local debug.
- `modules/api/` — `azurerm_service_plan` (FC1 / Linux) and
  `azurerm_function_app_flex_consumption`.

## Notes

The original `terraform-output/` folder at the repository root is the
*same* artefact and is what CI continuously revalidates against
`terraform validate`.
