"""ARM template → IR conversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from . import expressions as _expr
from .config import Config
from .expressions import is_arm_expression, translate
from .ir import IR, Module, ModuleCall, NestedBlock, Output, Parameter, Resource
from .mapping import MappingRule, load_mappings, lookup

_AVM_BRIDGE: dict[str, dict[str, str]] | None = None


def _avm_bridge() -> dict[str, dict[str, str]]:
    global _AVM_BRIDGE
    if _AVM_BRIDGE is not None:
        return _AVM_BRIDGE
    _AVM_BRIDGE = {}
    path = Path(__file__).resolve().parent.parent.parent / "mappings" / "avm.yaml"
    if path.exists():
        for entry in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if isinstance(entry, dict) and entry.get("bicep_ref"):
                _AVM_BRIDGE[entry["bicep_ref"]] = entry
    return _AVM_BRIDGE


# Terraform reserves these argument names on module {} blocks. Rename ARM
# parameters that collide so we can still pass them as inputs.
_TF_RESERVED_MODULE_ARGS = {
    "source",
    "version",
    "count",
    "for_each",
    "providers",
    "depends_on",
    "lifecycle",
}


def _safe_input_name(name: str) -> str:
    snake = _snake(name)
    if snake in _TF_RESERVED_MODULE_ARGS:
        return f"{snake}_"
    return snake


# TF resource types that don't take resource_group_name (subscription-scoped
# or RG-itself, or scoped on a parent resource id). Anything not on this list
# gets the auto-derivation treatment.
_NO_RG_TYPES = {
    "azurerm_resource_group",
    "azurerm_role_definition",
    "azurerm_role_assignment",
    "azurerm_subscription",
    "azurerm_management_group",
    "azurerm_policy_definition",
    "azurerm_policy_set_definition",
    "azurerm_subscription_policy_assignment",
    "azurerm_management_group_policy_assignment",
    "azurerm_user_assigned_identity",  # has its own RG arg, see below
    # Storage data-plane children scope themselves on the parent storage account.
    "azurerm_storage_management_policy",
    "azurerm_storage_share",
    "azurerm_storage_container",
    "azurerm_storage_blob",
    "azurerm_storage_queue",
    "azurerm_storage_table",
    "azurerm_storage_data_lake_gen2_filesystem",
    # Diagnostic / monitoring scoped on a target resource.
    "azurerm_monitor_diagnostic_setting",
    # Federated credentials scope on the parent identity.
    "azurerm_federated_identity_credential",
    # Private endpoint DNS zone group scopes on the PE.
    "azurerm_private_endpoint_application_security_group_association",
}

# TF resource types that auto-set `location` from `var.location`.
# Some resources are global / parent-scoped and don't take a location.
_NO_LOCATION_TYPES = {
    "azurerm_role_assignment",
    "azurerm_role_definition",
    "azurerm_user_assigned_identity_federated_credential",
    "azurerm_federated_identity_credential",
    "azurerm_storage_management_policy",
    "azurerm_storage_share",
    "azurerm_storage_container",
    "azurerm_storage_blob",
    "azurerm_storage_queue",
    "azurerm_storage_table",
    "azurerm_storage_data_lake_gen2_filesystem",
    "azurerm_monitor_diagnostic_setting",
    "azurerm_resource_group_template_deployment",
    "azurerm_management_lock",
    "azurerm_subscription",
    "azurerm_management_group",
    "azurerm_policy_definition",
    "azurerm_policy_set_definition",
    "azurerm_subscription_policy_assignment",
    "azurerm_private_dns_zone",
    "azurerm_dns_zone",
    "azurerm_private_dns_a_record",
    "azurerm_private_dns_zone_virtual_network_link",
    "azurerm_application_insights_workbook",
    # Slots inherit location from parent app.
    "azurerm_linux_web_app_slot",
    "azurerm_windows_web_app_slot",
    "azurerm_linux_function_app_slot",
    "azurerm_windows_function_app_slot",
    # VNet peerings are scoped on a parent VNet.
    "azurerm_virtual_network_peering",
}


_TYPE_MAP = {
    "string": "string",
    "securestring": "string",
    "int": "number",
    "bool": "bool",
    "object": "any",
    "secureobject": "any",
    "array": "list(any)",
}


class _RawHcl(str):
    """Marker subclass: render as raw HCL, not as a quoted string literal."""

    pass


def convert(arm: dict, source: Path, config: Config) -> IR:
    rules = load_mappings()
    root = Module(name="root", is_root=True)
    ir = IR(root=root)
    # Symbol table: ARM deployment name (literal) → TF module address.
    # Consulted by the expression translator for reference('depName').outputs.X
    _expr.set_context({"modules": {}})
    _convert_template(arm, root, rules, ir, config)
    _expr.set_context(None)
    return ir


def _convert_template(arm: dict, module: Module, rules: dict[str, MappingRule], ir: IR, config: Config) -> None:
    # Parameters
    for name, schema in (arm.get("parameters") or {}).items():
        module.parameters.append(_parameter(name, schema))

    # Variables → locals. ARM uses a special `copy` array for iteration
    # variables — expand each entry into a discrete local with a for-expression.
    for name, value in (arm.get("variables") or {}).items():
        if name == "copy" and isinstance(value, list):
            for entry in value:
                if not isinstance(entry, dict):
                    continue
                vname = entry.get("name")
                if not vname:
                    continue
                count_expr = translate(entry.get("count"))
                input_expr = translate(entry.get("input"))
                # ARM copyIndex() became `count.index`; rebind to the for-loop var.
                input_expr = input_expr.replace("count.index", "i")
                module.locals_[_snake(vname)] = f"[for i in range({count_expr}) : {input_expr}]"
            continue
        module.locals_[_snake(name)] = translate(value)

    # Resources — ARM 1.x uses a list, the languageVersion 2.0 schema (used
    # by Bicep) uses a dict keyed by symbolic name. Support both.
    raw_resources = arm.get("resources") or []

    # First pass: hoist `existing: true` resources into `data` blocks AND
    # register their symbolic names so reference('<sym>') resolves to the
    # data source instead of producing a TODO null. The data_sources ctx is
    # scoped per-module: save & restore around child-module recursion.
    if isinstance(raw_resources, dict):
        existing_iter = list(raw_resources.items())
    else:
        existing_iter = [(r.get("_symbolicName") or r.get("name", ""), r) for r in raw_resources if isinstance(r, dict)]
    ctx = _expr.get_context() or {}
    prev_ds = ctx.get("data_sources")
    ds_ctx: dict[str, str] = {}
    for sym, arm_res in existing_iter:
        if not isinstance(arm_res, dict) or arm_res.get("existing") is not True:
            continue
        rule = lookup(rules, arm_res.get("type", ""))
        if rule is None or rule.tf_type is None:
            continue
        ds_tf_type = _arm_to_data_source(rule.tf_type)
        if ds_tf_type is None:
            continue
        ds_sym = _safe_input_name(sym)
        ds_res = Resource(
            arm_type=arm_res.get("type", ""),
            tf_type=ds_tf_type,
            symbolic_name=ds_sym,
            attributes={},
            is_data_source=True,
        )
        if "name" in arm_res:
            ds_res.attributes["name"] = translate(arm_res["name"])
        if "resourceGroup" in arm_res:
            ds_res.attributes["resource_group_name"] = translate(arm_res["resourceGroup"])
        else:
            ds_res.attributes["resource_group_name"] = "var.resource_group_name"
            _ensure_rg_param(module)
        module.resources.append(ds_res)
        ds_ctx[sym] = f"data.{ds_tf_type}.{ds_sym}"
    ctx["data_sources"] = ds_ctx
    _expr.set_context(ctx)

    try:
        if isinstance(raw_resources, dict):
            for sym, arm_res in raw_resources.items():
                if isinstance(arm_res, dict):
                    arm_res.setdefault("_symbolicName", sym)
                    _process_resource(arm_res, module, rules, ir, config)
        else:
            for arm_res in raw_resources:
                if isinstance(arm_res, dict):
                    _process_resource(arm_res, module, rules, ir, config)

        # Outputs — translated under THIS module's data_sources scope.
        for name, schema in (arm.get("outputs") or {}).items():
            out_value = translate(schema.get("value"))
            module.outputs.append(
                Output(
                    name=name.upper() if module.is_root else name,
                    type=_TYPE_MAP.get(str(schema.get("type", "string")).lower(), "string"),
                    value=out_value,
                    description=schema.get("metadata", {}).get("description")
                    if isinstance(schema.get("metadata"), dict)
                    else None,
                    sensitive=bool(schema.get("metadata", {}).get("sensitive"))
                    if isinstance(schema.get("metadata"), dict)
                    else False,
                )
            )
            if isinstance(out_value, str) and "data.azurerm_resource_group.main" in out_value:
                _ensure_rg_param(module)
    finally:
        # Restore parent's data_sources scope for sibling traversal.
        ctx2 = _expr.get_context() or {}
        if prev_ds is None:
            ctx2.pop("data_sources", None)
        else:
            ctx2["data_sources"] = prev_ds
        _expr.set_context(ctx2)


def _parameter(name: str, schema: dict[str, Any]) -> Parameter:
    arm_type = str(schema.get("type", "string")).lower()
    default = schema.get("defaultValue")
    tf_type = _TYPE_MAP.get(arm_type, "string")
    # Widen the type if the declared type can't hold the default literal.
    if tf_type in ("string", "number", "bool") and isinstance(default, (dict, list)):
        tf_type = "any"
    # ARM-expression defaults: translate first; keep only if the result is a
    # literal (no var/local/module/data refs), otherwise Terraform will reject
    # the variable default.
    if isinstance(default, str) and is_arm_expression(default):
        translated = translate(default)
        if any(t in translated for t in ("var.", "local.", "module.", "data.", "TODO")):
            default = None
        else:
            default = _RawHcl(translated)
    return Parameter(
        name=_safe_input_name(name),
        type=tf_type,
        default=default,
        allowed_values=schema.get("allowedValues"),
        description=(schema.get("metadata") or {}).get("description")
        if isinstance(schema.get("metadata"), dict)
        else None,
        secure=arm_type.startswith("secure"),
    )


def _process_resource(arm_res: dict, module: Module, rules: dict[str, MappingRule], ir: IR, config: Config) -> None:
    arm_type = arm_res.get("type", "")

    # Bicep `existing` keyword compiles to {"existing": true} in ARM. These
    # resources are NOT deployed — they only enable symbolic references for
    # other resources in the same template. Skip emission entirely. Where the
    # body uses reference(<sym>), translation falls back to a TODO marker.
    if arm_res.get("existing") is True:
        return

    # Bicep modules compile to Microsoft.Resources/deployments. Emit a child
    # Terraform module so reference('depName').outputs.X can resolve cleanly.
    if arm_type == "Microsoft.Resources/deployments":
        _emit_child_module(arm_res, module, rules, ir, config)
        return

    rule = lookup(rules, arm_type)

    if rule is None or rule.tf_type is None:
        ir.unmapped_types.append(arm_type)
        module.resources.append(
            Resource(
                arm_type=arm_type,
                tf_type="",
                symbolic_name=_symbolic(arm_res.get("name", arm_type)),
                todo=f"No mapping for ARM type {arm_type}",
            )
        )
        ir.todos.append(f"unmapped:{arm_type}")
        return

    if rule.inline_into_parent:
        # Skip for now — parent emission handles this.
        return

    res = Resource(
        arm_type=arm_type,
        tf_type=rule.tf_type,
        symbolic_name=_uniq_symbolic(module, rule.tf_type, _symbolic(arm_res.get("name", arm_type))),
        attributes={},
    )

    arm_top = {k: v for k, v in arm_res.items() if k not in ("type", "apiVersion", "properties")}

    # Standard top-level → attribute mapping
    if "name" in arm_top:
        res.attributes["name"] = translate(arm_top["name"])
    if "location" in arm_top:
        res.attributes["location"] = translate(arm_top["location"])
    if "tags" in arm_top:
        res.attributes["tags"] = translate(arm_top["tags"])

    # Apply attribute_map: dotted ARM property paths → TF attribute name
    for arm_path, tf_attr in rule.attribute_map.items():
        v = _dig(arm_res, arm_path)
        if v is not None:
            res.attributes[tf_attr] = translate(v)

    # Drop attributes that aren't supported on the TF resource.
    for k in rule.drop_attributes:
        res.attributes.pop(k, None)

    # Rename attributes that the converter auto-derived under ARM names.
    for old, new in rule.rename_attributes.items():
        if old in res.attributes:
            res.attributes[new] = res.attributes.pop(old)

    # Wrap scalars into lists where TF expects a list.
    for attr in rule.wrap_list_attributes:
        v = res.attributes.get(attr)
        if v is not None and not v.startswith("["):
            res.attributes[attr] = f"[{v}]"

    # Inject required defaults — declared on the rule, often referencing a
    # `var.<x>` that the converter then auto-creates on the module.
    for tf_attr, default_expr in rule.required_defaults.items():
        if tf_attr in res.attributes:
            continue
        res.attributes[tf_attr] = default_expr
        # If the default references `var.<name>`, ensure that variable exists
        # on the module with a sensible declaration.
        m = re.match(r"^var\.([A-Za-z_][A-Za-z0-9_]*)$", default_expr)
        if m:
            vname = m.group(1)
            if not any(p.name == vname for p in module.parameters):
                module.parameters.append(
                    Parameter(
                        name=vname,
                        type="any",
                        default=None,
                        optional=True,
                        description=f"Auto-injected by bicep2tf for required {rule.tf_type}.{tf_attr}.",
                    )
                )

    # Inject required nested blocks (e.g. site_config {}, plan {}). Skip if the
    # block is already present.
    existing_block_names = {b.name for b in res.nested_blocks}
    for block_name, block_attrs in rule.required_blocks.items():
        if block_name in existing_block_names:
            continue
        res.nested_blocks.append(
            NestedBlock(
                name=block_name,
                attributes=dict(block_attrs),
            )
        )
        # Auto-declare any var.<x> referenced in the block.
        for v in block_attrs.values():
            for vname in re.findall(r"\bvar\.([A-Za-z_][A-Za-z0-9_]*)", v):
                if not any(p.name == vname for p in module.parameters):
                    module.parameters.append(
                        Parameter(
                            name=vname,
                            type="any",
                            default=None,
                            optional=True,
                            description=f"Auto-injected by bicep2tf for required {rule.tf_type}.{block_name}.",
                        )
                    )

    # Condition → count
    cond = arm_res.get("condition")
    if cond is not None:
        cond_hcl = translate(cond) if is_arm_expression(cond) else ("true" if cond else "false")
        res.count_expr = f"({cond_hcl}) ? 1 : 0"

    # copy → for_each / count
    copy = arm_res.get("copy")
    if isinstance(copy, dict) and "count" in copy:
        res.count_expr = translate(copy["count"])

    # Auto-derive resource_group_name. Most azurerm types require it but the
    # source Bicep modules omit it because they deploy at RG scope.
    if (
        rule.tf_type.startswith("azurerm_")
        and rule.tf_type not in _NO_RG_TYPES
        and "resource_group_name" not in res.attributes
        and "resource_group_name" not in rule.drop_attributes
    ):
        res.attributes["resource_group_name"] = "var.resource_group_name"
        _ensure_rg_param(module)
    # azurerm_user_assigned_identity also needs RG, just under a different
    # blocklist nuance — handle it here explicitly.
    if (
        rule.tf_type == "azurerm_user_assigned_identity"
        and "resource_group_name" not in res.attributes
        and "resource_group_name" not in rule.drop_attributes
    ):
        res.attributes["resource_group_name"] = "var.resource_group_name"
        _ensure_rg_param(module)

    # Auto-derive `location` similarly. Bicep AVM modules accept a `location`
    # parameter that's then applied; most azurerm_* types require it.
    if (
        rule.tf_type.startswith("azurerm_")
        and rule.tf_type not in _NO_LOCATION_TYPES
        and "location" not in res.attributes
        and "location" not in rule.drop_attributes
    ):
        res.attributes["location"] = "var.location"
        _ensure_location_param(module)

    # azurerm_role_assignment requires `scope`. Where the source ARM template
    # used resourceId()/guid() helpers we end up with a TODO null. Provide a
    # safe fallback so terraform validate passes — the user must review.
    if rule.tf_type == "azurerm_role_assignment" and "scope" not in res.attributes:
        res.attributes["scope"] = "data.azurerm_resource_group.main.id  # TODO: review scope"
        _ensure_rg_param(module)

    # ── Cat 2: storage child resource_id synthesis ─────────────────────────
    # ARM nests storage children under the parent
    # (Microsoft.Storage/storageAccounts/{blob,file}Services/{containers,shares},
    #  /managementPolicies). The TF resources expect a single storage_account_id
    # and a clean child name — not the ARM-style "{parent}/default/{child}" path.
    arm_t = (rule.arm_type or "").lower()
    storage_child_types = {
        "microsoft.storage/storageaccounts/blobservices/containers",
        "microsoft.storage/storageaccounts/fileservices/shares",
        "microsoft.storage/storageaccounts/queueservices/queues",
        "microsoft.storage/storageaccounts/tableservices/tables",
        "microsoft.storage/storageaccounts/managementpolicies",
    }
    if arm_t in storage_child_types:
        # Strip "${parent}/default/" or "${parent}/{services}/" prefix from name.
        nm = res.attributes.get("name", "")
        # Match patterns like "${var.x}/default/${var.y}" → "${var.y}"
        # or "${var.x}/${var.y}/${var.z}" → "${var.z}"
        cleaned = re.sub(r'^"\$\{[^}]+\}/(?:[^/"]+|\$\{[^}]+\})/', '"', nm)
        if cleaned != nm:
            res.attributes["name"] = cleaned
        # management_policy: drop name entirely (TF doesn't accept it).
        if arm_t.endswith("/managementpolicies"):
            res.attributes.pop("name", None)
        # Synthesize storage_account_id. Prefer existing data source if present.
        if "storage_account_id" not in res.attributes:
            ctx = _expr.get_context() or {}
            ds_map = ctx.get("data_sources") or {}
            sa_ref = next(
                (v for v in ds_map.values() if v.startswith("data.azurerm_storage_account.")),
                None,
            )
            if sa_ref:
                res.attributes["storage_account_id"] = f"{sa_ref}.id"
            else:
                res.attributes["storage_account_id"] = (
                    '"/subscriptions/${data.azurerm_client_config.current.subscription_id}'
                    "/resourceGroups/${data.azurerm_resource_group.main.name}"
                    '/providers/Microsoft.Storage/storageAccounts/${var.storage_account_name}"'
                )
                if not any(p.name == "storage_account_name" for p in module.parameters):
                    module.parameters.append(
                        Parameter(
                            name="storage_account_name",
                            type="string",
                            default=None,
                            optional=False,
                            description="Auto-injected by bicep2tf for storage child resource.",
                        )
                    )
                _ensure_rg_param(module)

    # ── Cat 2 (slot): set app_service_id from the data source for the parent.
    if rule.tf_type in {
        "azurerm_linux_web_app_slot",
        "azurerm_windows_web_app_slot",
        "azurerm_linux_function_app_slot",
        "azurerm_windows_function_app_slot",
    }:
        ctx = _expr.get_context() or {}
        ds_map = ctx.get("data_sources") or {}
        app_ref = next(
            (
                v
                for v in ds_map.values()
                if v.startswith("data.azurerm_linux_function_app.")
                or v.startswith("data.azurerm_windows_function_app.")
                or v.startswith("data.azurerm_linux_web_app.")
                or v.startswith("data.azurerm_windows_web_app.")
            ),
            None,
        )
        if app_ref:
            res.attributes["app_service_id"] = f"{app_ref}.id"
        # Strip parent prefix from name: "${var.app_name}/${var.name}" → "${var.name}"
        nm = res.attributes.get("name", "")
        cleaned = re.sub(r'^"\$\{[^}]+\}/', '"', nm)
        if cleaned != nm:
            res.attributes["name"] = cleaned

    module.resources.append(res)


def _ensure_rg_param(module: Module) -> None:
    """Ensure the module declares a `resource_group_name` input variable."""
    if any(p.name == "resource_group_name" for p in module.parameters):
        return
    module.parameters.append(
        Parameter(
            name="resource_group_name",
            type="string",
            description="Auto-injected by bicep2tf. Resource group hosting these resources.",
        )
    )


def _ensure_location_param(module: Module) -> None:
    """Ensure the module declares a `location` input variable."""
    if any(p.name == "location" for p in module.parameters):
        return
    module.parameters.append(
        Parameter(
            name="location",
            type="string",
            description="Auto-injected by bicep2tf. Azure region for these resources.",
        )
    )


# Map azurerm resource types to their nearest data-source equivalent. Where no
# obvious data-source exists, fall back to the same name (often correct).
_RESOURCE_TO_DATA_SOURCE = {
    "azurerm_linux_function_app": "azurerm_linux_function_app",
    "azurerm_windows_function_app": "azurerm_windows_function_app",
    "azurerm_linux_web_app": "azurerm_linux_web_app",
    "azurerm_windows_web_app": "azurerm_windows_web_app",
    "azurerm_application_insights": "azurerm_application_insights",
    "azurerm_storage_account": "azurerm_storage_account",
    "azurerm_key_vault": "azurerm_key_vault",
    "azurerm_user_assigned_identity": "azurerm_user_assigned_identity",
    "azurerm_virtual_network": "azurerm_virtual_network",
    "azurerm_subnet": "azurerm_subnet",
    "azurerm_log_analytics_workspace": "azurerm_log_analytics_workspace",
    "azurerm_service_plan": "azurerm_service_plan",
    "azurerm_resource_group": "azurerm_resource_group",
    "azurerm_private_dns_zone": "azurerm_private_dns_zone",
    "azurerm_dns_zone": "azurerm_dns_zone",
    "azurerm_cosmosdb_account": "azurerm_cosmosdb_account",
    "azurerm_app_service": "azurerm_app_service",
    "azurerm_function_app": "azurerm_function_app",
}

# Resource types with NO data-source equivalent in azurerm. Skip emission as a
# data block; consumers will get a TODO from reference().
_NO_DATA_SOURCE = {
    "azurerm_linux_web_app_slot",
    "azurerm_windows_web_app_slot",
    "azurerm_linux_function_app_slot",
    "azurerm_windows_function_app_slot",
    "azurerm_private_endpoint",
    "azurerm_role_assignment",
    "azurerm_federated_identity_credential",
    "azurerm_storage_container",
    "azurerm_storage_share",
    "azurerm_storage_management_policy",
    "azurerm_monitor_diagnostic_setting",
    "azurerm_management_lock",
}


def _arm_to_data_source(tf_type: str) -> str | None:
    if tf_type in _NO_DATA_SOURCE:
        return None
    return _RESOURCE_TO_DATA_SOURCE.get(tf_type, tf_type)


def _dig(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")
_SAFE_RE = re.compile(r"[^A-Za-z0-9_]+")


def _snake(s: str) -> str:
    return _SAFE_RE.sub("_", _SNAKE_RE.sub("_", s).lower()).strip("_")


def _symbolic(s: Any) -> str:
    return _snake(str(s))[:80] or "resource"


def _uniq_symbolic(module: Module, tf_type: str, base: str) -> str:
    """Return a symbolic name unique within the module for the given TF type."""
    used = {(r.tf_type, r.symbolic_name) for r in module.resources}
    name = base
    n = 2
    while (tf_type, name) in used:
        name = f"{base}_{n}"
        n += 1
    return name


def _emit_child_module(arm_res: dict, parent: Module, rules: dict[str, MappingRule], ir: IR, config: Config) -> None:
    """Recurse into a Microsoft.Resources/deployments and emit a child TF module."""
    raw_name = arm_res.get("name", "module")
    # Use a literal deployment name as the symbol-table key; otherwise prefer
    # the ARM symbolic name (set by _convert_template), then a synthetic id.
    if isinstance(raw_name, str) and not is_arm_expression(raw_name):
        deployment_key = raw_name
        sym_seed = raw_name
    elif arm_res.get("_symbolicName"):
        deployment_key = arm_res["_symbolicName"]
        sym_seed = arm_res["_symbolicName"]
    else:
        deployment_key = f"dep_{len(ir.modules)}"
        sym_seed = deployment_key

    sym = _symbolic(sym_seed)
    if len(sym) > 40:
        sym = sym[:32] + f"_{len(ir.modules)}"

    # Avoid collisions; suffix a counter if a module with this name exists.
    base = sym
    n = 2
    while sym in ir.modules:
        sym = f"{base}_{n}"
        n += 1

    # If the deployment was authored as `module x 'br/public:avm/...' = { ... }`,
    # Bicep stamps the resolved registry ref into metadata. Detect it and emit
    # a single registry-backed `module {}` call instead of expanding internals.
    avm_ref = _detect_avm_ref(arm_res)
    if avm_ref:
        bridge = _avm_bridge().get(avm_ref)
        if bridge:
            inputs: dict[str, str] = {}
            arm_params = (arm_res.get("properties") or {}).get("parameters") or {}
            for pname, pval in arm_params.items():
                if isinstance(pval, dict) and "value" in pval:
                    inputs[_safe_input_name(pname)] = translate(pval["value"])
            call = ModuleCall(
                name=sym,
                source=bridge["tf_source"],
                inputs=inputs,
            )
            # version handled via versions.tf in a future slice; for now record it.
            parent.submodule_calls.append(call)
            ctx = _expr.get_context() or {"modules": {}}
            ctx.setdefault("modules", {})[deployment_key] = f"module.{sym}"
            _expr.set_context(ctx)
            return

    nested = ((arm_res.get("properties") or {}).get("template")) or {}
    if not isinstance(nested, dict):
        nested = {}
    child = Module(name=sym)
    ir.modules[sym] = child

    # Populate the symbol table BEFORE recursing so child outputs that
    # reference sibling deployments via reference() resolve correctly.
    ctx = _expr.get_context() or {"modules": {}}
    ctx.setdefault("modules", {})[deployment_key] = f"module.{sym}"
    _expr.set_context(ctx)

    _convert_template(nested, child, rules, ir, config)

    # Build the parent's `module "x" { ... }` call, mapping ARM deployment
    # parameters → child variable names. Drop inputs the child doesn't
    # actually declare — Terraform errors with "Unsupported argument" otherwise.
    raw_inputs: dict[str, str] = {}
    arm_params = (arm_res.get("properties") or {}).get("parameters") or {}
    for pname, pval in arm_params.items():
        if isinstance(pval, dict) and "value" in pval:
            raw_inputs[_safe_input_name(pname)] = translate(pval["value"])

    declared = {p.name for p in child.parameters}
    # When the child declared zero parameters, pass nothing; otherwise filter
    # raw inputs down to only what the child actually accepts.
    inputs = {k: v for k, v in raw_inputs.items() if k in declared} if declared else {}

    # If the child auto-injected a resource_group_name parameter (because it
    # houses azurerm_* resources) and the parent didn't pass one, plumb the
    # parent's own var.resource_group_name through. Also auto-add the
    # parameter on the parent if missing.
    if "resource_group_name" in declared and "resource_group_name" not in inputs:
        inputs["resource_group_name"] = "var.resource_group_name"
        _ensure_rg_param(parent)
    # Same plumbing for `location`.
    if "location" in declared and "location" not in inputs:
        inputs["location"] = "var.location"
        _ensure_location_param(parent)

    call = ModuleCall(
        name=sym,
        source=(f"./modules/{sym}" if parent.is_root else f"../{sym}"),
        inputs=inputs,
    )
    cond = arm_res.get("condition")
    if cond is not None:
        cond_hcl = translate(cond) if is_arm_expression(cond) else ("true" if cond else "false")
        call.count_expr = f"({cond_hcl}) ? 1 : 0"

    copy = arm_res.get("copy")
    if isinstance(copy, dict) and "count" in copy:
        call.count_expr = translate(copy["count"])

    # Bicep treats unsupplied parameters with no defaultValue as nullable when
    # the source declared them with `param x type?`. ARM doesn't preserve the
    # `?` so we infer: any child variable not passed by the parent and lacking
    # a default becomes optional (default = null, type = any).
    supplied = set(inputs.keys())
    for p in child.parameters:
        supplied_value = inputs.get(p.name)
        if supplied_value and p.type in {"string", "number", "bool"}:
            stripped = supplied_value.strip()
            if stripped.startswith("{") or stripped.startswith("[") or "try(" in stripped:
                p.type = "any"
        if p.default is None and not p.secure and p.name not in supplied:
            p.default = None  # explicit null
            p.type = "any"
            p.optional = True

    # If a parent variable is passed straight through to a child variable with
    # a wider type, widen the parent too. This avoids string→list/object module
    # validation failures in nested AVM-generated modules.
    child_param_types = {p.name: p.type for p in child.parameters}
    parent_params = {p.name: p for p in parent.parameters}
    for input_name, input_value in inputs.items():
        m = re.fullmatch(r"var\.([A-Za-z_][A-Za-z0-9_]*)", input_value.strip())
        if not m:
            continue
        parent_param = parent_params.get(m.group(1))
        child_type = child_param_types.get(input_name)
        if (
            parent_param
            and child_type
            and parent_param.type in {"string", "number", "bool"}
            and child_type not in {"string", "number", "bool"}
        ):
            parent_param.type = child_type

    parent.submodule_calls.append(call)


def _detect_avm_ref(arm_res: dict) -> str | None:
    """Detect an AVM br/public:avm/... module reference in deployment metadata."""
    md = arm_res.get("metadata") or {}
    # Bicep stamps `_generator` and sometimes `description`/`templateHash`.
    for key in ("_module", "description", "templateLink"):
        v = md.get(key)
        if isinstance(v, str) and v.startswith("br/public:avm/"):
            return v.split(":", 2)[0] + ":" + v.split(":", 2)[1].split(":", 1)[0]
    # Fallback: many AVM modules carry an `_metadata` block containing the ref.
    nested = ((arm_res.get("properties") or {}).get("template")) or {}
    if isinstance(nested, dict):
        nm = nested.get("metadata") or {}
        name = nm.get("name") or nm.get("_module")
        owner = nm.get("owner")
        if isinstance(name, str) and "avm" in name.lower() and owner == "Azure/avm":
            # Best-effort: synthesize a bicep_ref — we won't always match.
            return None
    return None
