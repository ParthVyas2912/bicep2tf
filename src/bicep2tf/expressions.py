"""Translate ARM-template expressions to HCL.

This is a deliberately small, hand-written translator covering the most common
ARM functions encountered in Bicep output. Unsupported expressions are returned
verbatim as a quoted string with a TODO comment.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Conversion-time context (e.g. module symbol table). Set by convert.py.
_CTX: dict[str, Any] | None = None


def set_context(ctx: dict[str, Any] | None) -> None:
    global _CTX
    _CTX = ctx


def get_context() -> dict[str, Any] | None:
    return _CTX


# Match an ARM expression: a string starting with "[" and ending with "]" (with
# escaping handled — "[[" means a literal "[").
_ARM_EXPR = re.compile(r"^\[(?!\[)(.+)\]$")


def is_arm_expression(value: Any) -> bool:
    return isinstance(value, str) and bool(_ARM_EXPR.match(value))


def translate(value: Any) -> str:
    """Translate an ARM JSON value to an HCL expression string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(translate(v) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{_obj_key(k)} = {translate(v)}" for k, v in value.items())
        return "{ " + items + " }"
    if isinstance(value, str):
        m = _ARM_EXPR.match(value)
        if m:
            return _translate_expr(m.group(1).strip())
        # plain string literal — escape and quote
        return json.dumps(value)
    return json.dumps(str(value))


def _obj_key(k: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
        return _camel_to_snake(k)
    return json.dumps(k)


# ------------------------------------------------------------------
# Tiny ARM expression parser: identifiers, literals, function calls,
# member access (.foo), index access ([n], ['x']).
# ------------------------------------------------------------------


class _P:
    def __init__(self, src: str) -> None:
        self.s = src
        self.i = 0

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def skip_ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def consume(self, ch: str) -> bool:
        self.skip_ws()
        if self.i < len(self.s) and self.s[self.i] == ch:
            self.i += 1
            return True
        return False


def _translate_expr(src: str) -> str:
    p = _P(src)
    out = _parse(p)
    p.skip_ws()
    if not p.eof():
        return _todo(src, "trailing tokens")
    return out


def _parse(p: _P) -> str:
    p.skip_ws()
    c = p.peek()
    # string literal
    if c == "'":
        return _read_string(p)
    # numeric literal
    if c.isdigit() or (c == "-" and p.s[p.i + 1 : p.i + 2].isdigit()):
        return _read_number(p)
    # identifier / function call
    if c.isalpha() or c == "_":
        ident = _read_ident(p)
        p.skip_ws()
        if p.peek() == "(":
            args = _read_args(p)
            return _apply_postfix(p, _call(ident, args, p))
        return _apply_postfix(p, ident)
    return _todo(p.s, f"unexpected char {c!r}")


def _read_string(p: _P) -> str:
    assert p.peek() == "'"
    p.i += 1
    start = p.i
    while p.i < len(p.s):
        if p.s[p.i] == "'":
            # ARM doubles single quotes to escape
            if p.s[p.i + 1 : p.i + 2] == "'":
                p.i += 2
                continue
            break
        p.i += 1
    val = p.s[start : p.i].replace("''", "'")
    p.i += 1  # closing quote
    return json.dumps(val)


def _read_number(p: _P) -> str:
    start = p.i
    if p.peek() == "-":
        p.i += 1
    while p.i < len(p.s) and (p.s[p.i].isdigit() or p.s[p.i] == "."):
        p.i += 1
    return p.s[start : p.i]


def _read_ident(p: _P) -> str:
    start = p.i
    while p.i < len(p.s) and (p.s[p.i].isalnum() or p.s[p.i] == "_"):
        p.i += 1
    return p.s[start : p.i]


def _read_args(p: _P) -> list[str]:
    assert p.consume("(")
    args: list[str] = []
    p.skip_ws()
    if p.peek() == ")":
        p.i += 1
        return args
    while True:
        args.append(_parse(p))
        p.skip_ws()
        if p.consume(","):
            continue
        if p.consume(")"):
            break
        return [_todo(p.s, "expected , or )")]
    return args


def _apply_postfix(p: _P, expr: str) -> str:
    while True:
        p.skip_ws()
        c = p.peek()
        if c == ".":
            p.i += 1
            name = _read_ident(p)
            # If the base is a TODO marker, swallow further postfix to avoid
            # producing invalid HCL like `null /* TODO */.foo.bar`.
            if expr.startswith("null /* TODO"):
                continue
            # Rewrite reference(...).outputs.X.value pattern when base is a
            # module address: `module.x.outputs.X.value` → `module.x.X`.
            if expr.startswith("module.") and name.lower() == "outputs":
                # expect .<OUTPUT_NAME>[.value]
                p.skip_ws()
                if p.peek() == ".":
                    p.i += 1
                    out_name = _read_ident(p)
                    p.skip_ws()
                    if p.peek() == ".":
                        # consume optional .value
                        save = p.i
                        p.i += 1
                        tail = _read_ident(p)
                        if tail.lower() != "value":
                            p.i = save  # not .value, keep it
                    expr = f"{expr}.{out_name}"
                    continue
                # bare .outputs with nothing after — leave as-is
                expr = f"{expr}.outputs"
                continue
            if expr.startswith("data.azurerm_storage_account."):
                if name == "kind":
                    expr = f"{expr}.account_kind"
                    continue
                if name == "primaryEndpoints":
                    p.skip_ws()
                    if p.peek() == ".":
                        p.i += 1
                        service = _read_ident(p)
                        service_attr = {
                            "blob": "primary_blob_endpoint",
                            "queue": "primary_queue_endpoint",
                            "table": "primary_table_endpoint",
                            "file": "primary_file_endpoint",
                            "web": "primary_web_endpoint",
                        }.get(service)
                        if service_attr:
                            expr = f"{expr}.{service_attr}"
                            continue
                    expr = f"{expr}.primary_endpoints"
                    continue
            expr = f"{expr}.{_camel_to_snake(name)}"
        elif c == "[":
            p.i += 1
            inner = _parse(p)
            p.skip_ws()
            if not p.consume("]"):
                return _todo(p.s, "expected ]")
            if expr.startswith("null /* TODO"):
                continue
            expr = f"{expr}[{inner}]"
        else:
            break
    return expr


# ------------------------------------------------------------------
# Function call dispatch
# ------------------------------------------------------------------


def _call(name: str, args: list[str], p: _P) -> str:
    n = name.lower()
    if n == "parameters":
        return _var_ref(_unquote(args[0]))
    if n == "variables":
        return f"local.{_camel_to_snake(_unquote(args[0]))}"
    if n == "concat":
        safe_args = ["[]" if a.startswith("null /* TODO") else a for a in args]
        return "concat(" + ", ".join(safe_args) + ")"
    if n == "format":
        return _translate_format(args)
    if n == "if":
        return f"({args[0]} ? {args[1]} : {args[2]})"
    if n == "and":
        return "(" + " && ".join(args) + ")"
    if n == "or":
        return "(" + " || ".join(args) + ")"
    if n == "not":
        return f"!({args[0]})"
    if n == "equals":
        return f"({args[0]} == {args[1]})"
    if n == "empty":
        if args and args[0].startswith("null /* TODO"):
            return "true"
        return f"(length({args[0]}) == 0)"
    if n == "length":
        if args and args[0].startswith("null /* TODO"):
            return "0"
        return f"length({args[0]})"
    if n == "coalesce":
        # ARM coalesce returns the first non-null arg. Terraform's coalesce
        # additionally requires every arg to share a type, which fails when
        # combining `any`-typed variables with literal `[]` / `{}` defaults
        # — a very common pattern in AVM modules. Wrap each arg in `try()`
        # so type coercion errors gracefully fall through to the next arg.
        wrapped = ", ".join(f"try({a}, null)" for a in args)
        return f"try(coalesce({wrapped}), {args[-1]})"
    if n == "tolower":
        return f"lower({args[0]})"
    if n == "toupper":
        return f"upper({args[0]})"
    if n == "uniquestring":
        # deterministic-ish pseudo-equivalent
        safe_args = ['"todo"' if a.startswith("null /* TODO") else a for a in args]
        return f'substr(sha1(join("-", [{", ".join(safe_args)}])), 0, 13)'
    if n == "guid":
        return f'uuidv5("oid", join("-", [{", ".join(args)}]))'
    if n == "subscription":
        return "data.azurerm_client_config.current"
    if n == "tenant":
        return "data.azurerm_client_config.current"
    if n == "resourcegroup":
        return "data.azurerm_resource_group.main"
    if n == "copyindex":
        return "count.index"
    if n == "replace":
        # ARM: replace(orig, find, with) ; TF: replace(orig, find, with)
        return f"replace({args[0]}, {args[1]}, {args[2]})"
    if n == "contains":
        # ARM contains(container, item) is overloaded across strings/arrays/objects.
        # Use a try() chain that evaluates lazily — the first non-erroring branch wins.
        # Object/map first (most common in role-assignment templates checking for a key),
        # then array, then substring on a string. Default false if all error.
        return (
            f"try(contains(keys({args[0]}), {args[1]}), "
            f"contains({args[0]}, {args[1]}), "
            f"strcontains(tostring({args[0]}), tostring({args[1]})), false)"
        )
    if n == "subscriptionresourceid":
        # subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'guid')
        # → "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/<type>/<name>/<name>..."
        if len(args) >= 2:
            type_lit = _strip_quotes(args[0])
            name_parts: list[str] = []
            for a in args[1:]:
                if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
                    # Quoted literal — embed the literal text directly.
                    name_parts.append(a[1:-1])
                else:
                    # Expression — interpolate it.
                    name_parts.append("${" + a + "}")
            tail = "/".join(name_parts)
            return (
                f'"/subscriptions/${{data.azurerm_client_config.current.subscription_id}}/providers/{type_lit}/{tail}"'
            )
        return _todo(p.s, "subscriptionResourceId() needs at least 2 args")
    if n == "resourceid":
        # resourceId('Microsoft.Resources/deployments', 'depName')
        # → module.<sym>  (only for the deployments shortcut; everything else
        # still needs human review).
        ctx = _CTX or {}
        modmap = ctx.get("modules", {})
        if len(args) >= 2 and args[-2].lower() in ('"microsoft.resources/deployments"',):
            dep = _unquote(args[-1])
            if dep in modmap:
                return modmap[dep]
        # Generic synthesis: produce a best-effort RG-scoped resource ID. The
        # provider/type/name segments come from the args; subscription/RG come
        # from ambient data. The resulting string is *not* guaranteed correct
        # (the source might have intended a sub-scoped or extension ID), but
        # it gives downstream functions like join()/uuidv5() a non-null value
        # to operate on.
        if len(args) >= 2:
            type_lit = _strip_quotes(args[0])
            name_parts: list[str] = []
            for a in args[1:]:
                if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
                    name_parts.append(a[1:-1])
                else:
                    name_parts.append("${" + a + "}")
            tail = "/".join(name_parts)
            return (
                '"/subscriptions/${data.azurerm_client_config.current.subscription_id}'
                "/resourceGroups/${data.azurerm_resource_group.main.name}"
                f'/providers/{type_lit}/{tail}"'
            )
        return _todo(p.s, "resourceId() — depends on context, please review")
    if n == "extensionresourceid":
        ctx = _CTX or {}
        modmap = ctx.get("modules", {})
        # extensionResourceId(scope, type, name [, name2...]) — same shortcut
        # as resourceId() above when the type is a deployment.
        if len(args) >= 3 and args[1].lower() in ('"microsoft.resources/deployments"',):
            dep = _unquote(args[2])
            if dep in modmap:
                return modmap[dep]
        # Generic synthesis: scope + /providers/<type>/<name...>
        if len(args) >= 3:
            scope = args[0]
            type_lit = _strip_quotes(args[1])
            name_parts = []
            for a in args[2:]:
                if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
                    name_parts.append(a[1:-1])
                else:
                    name_parts.append("${" + a + "}")
            tail = "/".join(name_parts)
            scope_lit = _strip_quotes(scope) if (len(scope) >= 2 and scope[0] == '"') else ("${" + scope + "}")
            return f'"{scope_lit}/providers/{type_lit}/{tail}"'
        return _todo(p.s, "extensionResourceId() — depends on context, please review")
    if n == "reference":
        # reference(resourceIdLikeExpr, apiVersion).outputs.X.value
        # If the inner expression already resolved to module.<sym>, return
        # that — the .outputs.X postfix will be rewritten below.
        if args and args[0].startswith("module."):
            return args[0]
        # If the source bicep used `existing` for this symbol, we promoted it
        # to a `data` block during conversion and registered it in context.
        ctx = _CTX or {}
        ds_map = ctx.get("data_sources", {})
        if args:
            sym = _unquote(args[0])
            if sym in ds_map:
                return ds_map[sym]
            if "Microsoft.Storage/storageAccounts" in args[0]:
                sa_ref = next(
                    (v for v in ds_map.values() if v.startswith("data.azurerm_storage_account.")),
                    None,
                )
                if sa_ref:
                    return sa_ref
                return "data.azurerm_storage_account.storage_account"
        return _todo(p.s, "reference() — translate to module/resource attribute")
    if n == "split":
        return f"split({args[1]}, {args[0]})"
    if n == "last":
        return f"element({args[0]}, length({args[0]}) - 1)"
    if n == "take":
        return f"substr({args[0]}, 0, {args[1]})"
    if n == "tryget":
        # tryGet(obj, "key")
        return f"try({args[0]}.{_unquote(args[1])}, null)"
    if n == "createobject":
        return "{}"
    if n == "createarray":
        return f"[{', '.join(args)}]"
    if n == "union":
        return f"merge({', '.join(args)})"
    if n == "items":
        return f"[ for k, v in {args[0]} : {{ key = k, value = v }} ]"
    if n == "deployer":
        return "data.azurerm_client_config.current"
    return _todo(p.s, f"unsupported ARM function {name}()")


_FORMAT_TOKEN = re.compile(r"\{(\d+)\}")


def _translate_format(args: list[str]) -> str:
    if not args:
        return '""'
    # First arg is the format string (already JSON-quoted). Strip quotes.
    fmt = json.loads(args[0])
    rest = args[1:]

    # Walk the format string and only escape `"` / `$` / `%` in literal
    # segments. Interpolated `${expr}` segments are inserted verbatim because
    # they may contain quoted string literals that must not be escaped again.
    out: list[str] = []
    pos = 0
    for m in _FORMAT_TOKEN.finditer(fmt):
        literal = fmt[pos : m.start()]
        out.append(literal.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$").replace("%", "%%"))
        idx = int(m.group(1))
        out.append("${" + (rest[idx] if idx < len(rest) else "") + "}")
        pos = m.end()
    tail = fmt[pos:]
    out.append(tail.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$").replace("%", "%%"))
    return '"' + "".join(out) + '"'


# ------------------------------------------------------------------


def _unquote(arg: str) -> str:
    if len(arg) >= 2 and arg[0] == '"' and arg[-1] == '"':
        try:
            return json.loads(arg)
        except json.JSONDecodeError:
            return arg
    return arg


def _strip_quotes(arg: str) -> str:
    """Return the inner literal of a double-quoted string, or the arg as-is."""
    if len(arg) >= 2 and arg[0] == '"' and arg[-1] == '"':
        return arg[1:-1]
    return arg


def _var_ref(arm_param_name: str) -> str:
    return f"var.{_camel_to_snake(arm_param_name)}"


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")
_IDENT_SAFE = re.compile(r"[^A-Za-z0-9_]+")


def _camel_to_snake(s: str) -> str:
    # Already snake or ALL_CAPS — just normalize unsafe chars and lower.
    if "_" in s or s.isupper() or s.islower():
        out = _IDENT_SAFE.sub("_", s).lower()
    else:
        out = _CAMEL_RE.sub("_", s).lower()
        out = _IDENT_SAFE.sub("_", out)
    out = out.strip("_")
    if out and out[0].isdigit():
        out = "_" + out
    return out or "_"


def _todo(src: str, msg: str) -> str:
    return f"null /* TODO: {msg} — original: {src!r} */"
