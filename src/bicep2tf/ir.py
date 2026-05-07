"""Intermediate representation produced from ARM and consumed by the renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Parameter:
    name: str
    type: str = "string"
    default: Any = None
    allowed_values: list[Any] | None = None
    description: str | None = None
    secure: bool = False
    optional: bool = False  # default is explicitly `null` (no value required)


@dataclass
class Output:
    name: str
    type: str
    value: str  # already-translated HCL expression
    description: str | None = None
    sensitive: bool = False


@dataclass
class Resource:
    """A Terraform resource or data source."""

    arm_type: str
    tf_type: str
    symbolic_name: str
    attributes: dict[str, str] = field(default_factory=dict)  # values are HCL expressions
    nested_blocks: list[NestedBlock] = field(default_factory=list)
    is_data_source: bool = False
    count_expr: str | None = None
    for_each_expr: str | None = None
    depends_on: list[str] = field(default_factory=list)
    todo: str | None = None  # if set, render as a TODO comment


@dataclass
class NestedBlock:
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    nested_blocks: list[NestedBlock] = field(default_factory=list)


@dataclass
class Module:
    """A Terraform module (one per Bicep module + the root)."""

    name: str  # symbolic, e.g. "storage"
    is_root: bool = False
    parameters: list[Parameter] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    outputs: list[Output] = field(default_factory=list)
    locals_: dict[str, str] = field(default_factory=dict)
    submodule_calls: list[ModuleCall] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extra_required_providers: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class ModuleCall:
    """An instance of a child Terraform module from the root module."""

    name: str  # the local name in main.tf (e.g. "storage")
    source: str  # e.g. "./modules/storage"
    inputs: dict[str, str] = field(default_factory=dict)
    count_expr: str | None = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class IR:
    root: Module
    modules: dict[str, Module] = field(default_factory=dict)
    unmapped_types: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
