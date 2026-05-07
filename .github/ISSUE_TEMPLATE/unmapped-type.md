---
name: Unmapped ARM type
about: Request a mapping for a Microsoft.* type that currently emits a TODO
labels: [unmapped-type, good first issue]
---

**ARM type**

`Microsoft.<provider>/<type>[/<child>...]`

**Suggested Terraform target**

`azurerm_<resource>` (or AzAPI fallback)

**Bicep snippet**

```bicep
```

**Expected Terraform**

```hcl
```

**References**

- Bicep schema: https://learn.microsoft.com/azure/templates/...
- AzureRM provider docs: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/...
