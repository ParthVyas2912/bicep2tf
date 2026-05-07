# Architecture

```
┌──────────┐   bicep build   ┌──────────┐   walk   ┌────────────┐   render   ┌────────────┐
│  *.bicep │ ───────────────▶│ ARM JSON │ ────────▶│ IR (graph) │ ──────────▶│   *.tf     │
└──────────┘                 └──────────┘          └────────────┘            └────────────┘
                                                          │
                                                          │ resolve refs,
                                                          │ apply mappings/*.yaml,
                                                          │ build module DAG
                                                          ▼
                                                    bicep2tf core
```

## Stages

1. **Compile.** `bicep build --stdout` produces an ARM JSON template per
   Bicep file. AVM `br/public:avm/...` references are resolved to their
   compiled JSON and tagged so the renderer can later choose to
   reference / expand / skip them.
2. **Parse to IR.** Each ARM template becomes an in-memory `Module` with
   `Parameter`, `Variable`, `Resource`, `Output`, and `Reference` nodes.
   Cross-module references are resolved using each Bicep `module` call's
   inputs and outputs.
3. **Map.** For every ARM resource type, a YAML rule under
   [`mappings/`](../mappings/) declares the target Terraform type and an
   attribute map. Unknown types become a `Resource` of kind `unmapped`
   that renders to a `# TODO` comment in the output.
4. **Lower ARM expressions.** A small AST translator converts
   `[parameters('x')]`, `[variables('y')]`, `[reference(...)]`,
   `[resourceId(...)]`, `[format('{0}/{1}', a, b)]`, `[copyIndex()]`,
   `[if(c, a, b)]`, and friends into HCL expressions.
5. **Build module DAG.** Bicep `module` boundaries become Terraform
   modules under `modules/<name>/`. Outputs declared by a Bicep module
   are emitted as TF `output` blocks; the parent's `module.<name>.<out>`
   becomes the input wiring on the consumer side.
6. **Render.** HCL is emitted with deterministic key ordering (so
   re-runs are byte-identical) and run through `terraform fmt -recursive`.
7. **Validate.** `terraform init -backend=false && terraform validate`
   runs on the output. Diagnostics are written to
   `terraform_validate.json` and a human summary to
   `conversion_report.json`.

## Module grouping

Two strategies, controlled by `--layout`:

- **`bicep` (default):** one TF module per Bicep `module`. Best for
  teams who want to keep the same mental model.
- **`service`:** resources grouped by Azure service category. Useful
  when the source Bicep is a single flat file.

## AVM bridge

Bicep references to `br/public:avm/res/<service>/<name>:<version>` are
mapped to the equivalent Terraform module
`Azure/avm-res-<service>-<name>/azurerm` when one exists, with the
parameter map maintained in [`mappings/avm.yaml`](../mappings/avm.yaml).
This avoids exploding ~10 source modules into 100+ inline resources
(which is what naive expansion does — see CHANGELOG `v0.1.0`).

## Determinism guarantees

- Symbol names are derived from a stable hash of the source location
  plus the resource path; never from `dict` iteration order.
- All emitted maps/lists are sorted before rendering.
- Generated comments include source-file line ranges to ease review.
