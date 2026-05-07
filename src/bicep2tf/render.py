"""Render IR to Terraform files on disk."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .config import Config
from .ir import IR, Module, NestedBlock, Output, Parameter, Resource


def render(ir: IR, output_dir: Path, config: Config) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    main_body = _render_module_body(ir.root)
    vars_body = _render_variables(ir.root.parameters)
    outs_body = _render_outputs(ir.root.outputs)
    locals_body = _render_locals(ir.root.locals_) if ir.root.locals_ else ""

    combined = main_body + vars_body + outs_body + locals_body
    main_body, vars_body = _inject_ambient_data_sources(main_body, vars_body, combined)

    _write(output_dir / "providers.tf", _render_providers(config))
    _write(output_dir / "variables.tf", vars_body)
    _write(output_dir / "main.tf", main_body)
    _write(output_dir / "outputs.tf", outs_body)
    if locals_body:
        _write(output_dir / "locals.tf", locals_body)

    for name, mod in ir.modules.items():
        sub_dir = output_dir / "modules" / name
        sub_dir.mkdir(parents=True, exist_ok=True)
        sub_main = _render_module_body(mod)
        sub_vars = _render_variables(mod.parameters) if mod.parameters else ""
        sub_outs = _render_outputs(mod.outputs) if mod.outputs else ""
        sub_locals = _render_locals(mod.locals_) if mod.locals_ else ""
        sub_combined = sub_main + sub_vars + sub_outs + sub_locals
        sub_main, sub_vars = _inject_ambient_data_sources(sub_main, sub_vars, sub_combined)
        _write(sub_dir / "main.tf", sub_main)
        if sub_vars:
            _write(sub_dir / "variables.tf", sub_vars)
        if sub_outs:
            _write(sub_dir / "outputs.tf", sub_outs)
        if sub_locals:
            _write(sub_dir / "locals.tf", sub_locals)
        if mod.extra_required_providers:
            _write(sub_dir / "versions.tf", _render_required_providers(mod.extra_required_providers))

    if shutil.which("terraform"):
        subprocess.run(["terraform", "fmt", "-recursive"], cwd=output_dir, check=False)


def _inject_ambient_data_sources(main_body: str, vars_body: str, combined: str) -> tuple[str, str]:
    if "data.azurerm_client_config.current" in combined and 'data "azurerm_client_config" "current"' not in combined:
        main_body = 'data "azurerm_client_config" "current" {}\n\n' + main_body
    if "data.azurerm_resource_group.main" in combined and 'data "azurerm_resource_group" "main"' not in combined:
        main_body = ('data "azurerm_resource_group" "main" {\n  name = var.resource_group_name\n}\n\n') + main_body
        if 'variable "resource_group_name"' not in vars_body:
            vars_body = 'variable "resource_group_name" {\n  type = string\n}\n\n' + vars_body
    if (
        "data.azurerm_storage_account.storage_account" in combined
        and 'data "azurerm_storage_account" "storage_account"' not in combined
    ):
        storage_name_ref = "var.storage_account_name" if 'variable "storage_account_name"' in vars_body else "var.name"
        main_body = (
            'data "azurerm_storage_account" "storage_account" {\n'
            f"  name                = {storage_name_ref}\n"
            "  resource_group_name = var.resource_group_name\n"
            "}\n\n"
        ) + main_body
        if storage_name_ref == "var.storage_account_name" and 'variable "storage_account_name"' not in vars_body:
            vars_body = 'variable "storage_account_name" {\n  type = string\n}\n\n' + vars_body
        if 'variable "resource_group_name"' not in vars_body:
            vars_body = 'variable "resource_group_name" {\n  type = string\n}\n\n' + vars_body
    return main_body, vars_body


def _write(path: Path, contents: str) -> None:
    path.write_text(contents.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------


def _render_providers(config: Config) -> str:
    return f"""terraform {{
  required_version = ">= 1.6.0"
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "{config.provider_version}"
    }}
    azapi = {{
      source  = "Azure/azapi"
      version = "~> 2.0"
    }}
    random = {{
      source  = "hashicorp/random"
      version = "~> 3.6"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}

provider "azapi" {{}}
"""


def _render_required_providers(providers: dict[str, dict[str, str]]) -> str:
    body = "\n".join(
        f'    {n} = {{ source = "{c["source"]}", version = "{c["version"]}" }}' for n, c in providers.items()
    )
    return f"terraform {{\n  required_providers {{\n{body}\n  }}\n}}\n"


def _render_variables(params: list[Parameter]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for p in sorted(params, key=lambda x: x.name):
        # Sanitize: HCL variable names must be valid identifiers. Strip only
        # leading underscores so that reserved-name suffixes like `version_`
        # (used to avoid module-block collisions) survive intact.
        name = re.sub(r"[^A-Za-z0-9_]", "_", p.name).lstrip("_") or "v"
        if name in seen:
            continue
        seen.add(name)
        lines = [f'variable "{name}" {{']
        lines.append(f"  type = {p.type}")
        if p.default is not None:
            lines.append(f"  default = {_lit(p.default)}")
        elif p.optional:
            # Explicitly nullable; omit `default` and Terraform treats it as required
            # unless we set null. Set to null so callers can omit it.
            lines.append("  default = null")
        elif p.default is None and p.type != "any":
            pass  # required
        if p.description:
            lines.append(f"  description = {_str(p.description)}")
        if p.secure:
            lines.append("  sensitive = true")
        if p.allowed_values:
            allowed = ", ".join(_lit(v) for v in p.allowed_values)
            human = ", ".join(str(v) for v in p.allowed_values)
            lines.append("  validation {")
            if p.optional or p.default is None:
                lines.append(f"    condition = var.{name} == null || contains([{allowed}], var.{name})")
            else:
                lines.append(f"    condition = contains([{allowed}], var.{name})")
            lines.append(f"    error_message = {_str('Must be one of: ' + human)}")
            lines.append("  }")
        lines.append("}")
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def _render_outputs(outputs: list[Output]) -> str:
    out: list[str] = []
    for o in outputs:
        lines = [f'output "{o.name}" {{', f"  value = {o.value}"]
        if o.description:
            lines.append(f"  description = {_str(o.description)}")
        if o.sensitive:
            lines.append("  sensitive = true")
        lines.append("}")
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def _render_locals(locals_map: dict[str, str]) -> str:
    body = "\n".join(f"  {k} = {v}" for k, v in sorted(locals_map.items()))
    return f"locals {{\n{body}\n}}\n"


def _render_module_body(mod: Module) -> str:
    chunks: list[str] = []
    for r in mod.resources:
        chunks.append(_render_resource(r))
    for c in mod.submodule_calls:
        chunks.append(_render_module_call(c))
    return "\n\n".join(chunks) + "\n"


def _render_resource(r: Resource) -> str:
    if r.todo:
        return f"# TODO: {r.todo}\n# Type: {r.arm_type}\n# Manual intervention needed — see conversion_report.json"
    kind = "data" if r.is_data_source else "resource"
    head = f'{kind} "{r.tf_type}" "{r.symbolic_name}" {{'
    body_lines: list[str] = []
    if r.count_expr:
        body_lines.append(f"  count = {r.count_expr}")
    if r.for_each_expr:
        body_lines.append(f"  for_each = {r.for_each_expr}")
    for k, v in r.attributes.items():
        body_lines.append(f"  {k} = {v}")
    for nb in r.nested_blocks:
        body_lines.append(_render_nested_block(nb, indent=2))
    if r.depends_on:
        body_lines.append(f"  depends_on = [{', '.join(r.depends_on)}]")
    return head + "\n" + "\n".join(body_lines) + "\n}"


def _render_nested_block(nb: NestedBlock, indent: int) -> str:
    pad = " " * indent
    lines = [f"{pad}{nb.name} {{"]
    for k, v in nb.attributes.items():
        lines.append(f"{pad}  {k} = {v}")
    for sub in nb.nested_blocks:
        lines.append(_render_nested_block(sub, indent + 2))
    lines.append(f"{pad}}}")
    return "\n".join(lines)


def _render_module_call(c: ModuleCall) -> str:  # noqa: F821
    lines = [f'module "{c.name}" {{', f'  source = "{c.source}"']
    if c.count_expr:
        lines.append(f"  count = {c.count_expr}")
    for k, v in c.inputs.items():
        lines.append(f"  {k} = {v}")
    if c.depends_on:
        lines.append(f"  depends_on = [{', '.join(c.depends_on)}]")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------


def _lit(value: object) -> str:
    # Raw HCL marker (set by the converter for translated ARM-expression
    # defaults that resolve to literal expressions).
    if value.__class__.__name__ == "_RawHcl":
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_lit(v) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{k} = {_lit(v)}" for k, v in value.items())
        return "{ " + items + " }"
    return _str(str(value))


def _str(s: str) -> str:
    if "\n" in s:
        # Use heredoc; pick a marker unlikely to clash.
        marker = "EOT"
        while marker in s:
            marker += "_"
        body = s.rstrip("\n")
        return f"<<-{marker}\n{body}\n{marker}"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
