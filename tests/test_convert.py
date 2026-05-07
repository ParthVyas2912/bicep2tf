"""Unit tests for the convert layer (no bicep CLI required)."""

from __future__ import annotations

from pathlib import Path

from bicep2tf.config import Config
from bicep2tf.convert import convert


def _arm(**extra):
    base = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "variables": {},
        "resources": [],
        "outputs": {},
    }
    base.update(extra)
    return base


def test_emits_child_module_for_nested_deployment():
    arm = _arm(
        resources=[
            {
                "type": "Microsoft.Resources/deployments",
                "apiVersion": "2025-04-01",
                "name": "storage",
                "properties": {
                    "template": _arm(
                        parameters={"name": {"type": "string"}},
                        resources=[
                            {
                                "type": "Microsoft.Storage/storageAccounts",
                                "apiVersion": "2024-01-01",
                                "name": "[parameters('name')]",
                                "location": "eastus",
                                "sku": {"name": "Standard_LRS"},
                                "kind": "StorageV2",
                            }
                        ],
                        outputs={
                            "id": {
                                "type": "string",
                                "value": "[resourceId('Microsoft.Storage/storageAccounts', parameters('name'))]",
                            }
                        },
                    ),
                    "parameters": {"name": {"value": "mystorage"}},
                },
            }
        ]
    )
    ir = convert(arm, source=Path("test.bicep"), config=Config())
    assert "storage" in ir.modules
    child = ir.modules["storage"]
    assert any(r.tf_type == "azurerm_storage_account" for r in child.resources)
    assert ir.root.submodule_calls
    call = ir.root.submodule_calls[0]
    assert call.name == "storage"
    assert call.source == "./modules/storage"
    assert call.inputs == {"name": '"mystorage"', "resource_group_name": "var.resource_group_name"}


def test_reference_resolves_to_module_output():
    arm = _arm(
        resources=[
            {
                "type": "Microsoft.Resources/deployments",
                "apiVersion": "2025-04-01",
                "name": "appinsights",
                "properties": {
                    "template": _arm(outputs={"name": {"type": "string", "value": "ai"}}),
                    "parameters": {},
                },
            }
        ],
        outputs={
            "appInsightsName": {
                "type": "string",
                "value": "[reference(resourceId('Microsoft.Resources/deployments', 'appinsights'), '2025-04-01').outputs.name.value]",
            }
        },
    )
    ir = convert(arm, source=Path("test.bicep"), config=Config())
    assert ir.root.outputs[0].value == "module.appinsights.name"


def test_handles_arm_v2_dict_resources():
    """ARM languageVersion 2.0 templates use a dict for resources."""
    arm = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "languageVersion": "2.0",
        "parameters": {},
        "resources": {
            "rg": {
                "type": "Microsoft.Resources/resourceGroups",
                "apiVersion": "2024-03-01",
                "name": "test-rg",
                "location": "eastus",
            }
        },
    }
    ir = convert(arm, source=Path("test.bicep"), config=Config())
    assert any(r.tf_type == "azurerm_resource_group" for r in ir.root.resources)
