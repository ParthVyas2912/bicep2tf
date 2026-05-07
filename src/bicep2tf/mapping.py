"""Mapping rule loader. Rules live under mappings/*.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MappingRule:
    arm_type: str
    tf_type: str | None = None  # None means unmapped / TODO
    attribute_map: dict[str, str] = field(default_factory=dict)
    nested_blocks: dict[str, dict[str, str]] = field(default_factory=dict)
    inline_into_parent: bool = False
    notes: str | None = None
    # Required attributes the source ARM template never sets but TF demands.
    # Values are HCL expressions (typically `var.<name>` or a literal); the
    # converter auto-creates matching variables on the module.
    required_defaults: dict[str, str] = field(default_factory=dict)
    # Required nested blocks. Each value is a dict of HCL expressions that
    # become nested-block attributes. Useful for e.g. site_config { ... }.
    required_blocks: dict[str, dict[str, str]] = field(default_factory=dict)
    # Attributes the converter would otherwise emit but that aren't supported
    # on the TF resource (e.g. `kind` on azurerm_service_plan).
    drop_attributes: list[str] = field(default_factory=list)
    # Rename attributes after they've been auto-derived from top-level/ARM.
    rename_attributes: dict[str, str] = field(default_factory=dict)
    # Attribute names whose value should be wrapped from `x` to `[x]` if the
    # value isn't already a list literal. Useful for ARM scalars that map to
    # TF list attributes (e.g. `address_prefix` → `address_prefixes`).
    wrap_list_attributes: list[str] = field(default_factory=list)


def load_mappings(mapping_dir: Path | None = None) -> dict[str, MappingRule]:
    """Load all *.yaml files under mappings/ and return an ARM-type → rule dict."""
    if mapping_dir is None:
        mapping_dir = Path(__file__).resolve().parent.parent.parent / "mappings"
    rules: dict[str, MappingRule] = {}
    if not mapping_dir.exists():
        return rules
    for yml in sorted(mapping_dir.glob("*.yaml")):
        # AVM module bridge file uses a different schema; skip here.
        if yml.name == "avm.yaml":
            continue
        data: list[dict[str, Any]] = yaml.safe_load(yml.read_text(encoding="utf-8")) or []
        for entry in data:
            arm_type = entry.get("arm_type")
            if not arm_type:
                continue
            rules[arm_type.lower()] = MappingRule(
                arm_type=arm_type,
                tf_type=entry.get("tf_type"),
                attribute_map=entry.get("attribute_map") or {},
                nested_blocks=entry.get("nested_blocks") or {},
                inline_into_parent=bool(entry.get("inline_into_parent", False)),
                notes=entry.get("notes"),
                required_defaults=entry.get("required_defaults") or {},
                required_blocks=entry.get("required_blocks") or {},
                drop_attributes=entry.get("drop_attributes") or [],
                rename_attributes=entry.get("rename_attributes") or {},
                wrap_list_attributes=entry.get("wrap_list_attributes") or [],
            )
    return rules


def lookup(rules: dict[str, MappingRule], arm_type: str) -> MappingRule | None:
    return rules.get(arm_type.lower())
