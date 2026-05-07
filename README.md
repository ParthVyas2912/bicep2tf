# bicep2tf

> **Convert Azure Bicep to Terraform — module-aware, AVM-aware, validation-checked.**

`bicep2tf` is an open-source converter that takes a Bicep deployment (including
subscription-scope, AVM modules, and custom local modules) and produces a clean
Terraform configuration that:

- mirrors your Bicep module boundaries (one TF module per Bicep module),
- targets the current `hashicorp/azurerm` provider (v4.x),
- generates the networking / RBAC / private endpoints implied by your Bicep,
- runs `terraform fmt` + `terraform validate` as part of every conversion, and
- emits a machine-readable `conversion_report.json` summarising mappings,
  warnings, and unmapped resource types.

> **Status:** early preview (`v0.1.x`). API and CLI surface may change.

---

## Why another converter?

| Tool | Direction | Notes |
|---|---|---|
| `aztfexport` (HashiCorp) | Live Azure → Terraform | Reads existing resources, not source-of-truth IaC. |
| `decompile` (Bicep) | ARM JSON → Bicep | Opposite direction. |
| **`bicep2tf`** | **Bicep → Terraform** | The missing piece. |

If your team has a Bicep estate but is consolidating on Terraform — or you want
to evaluate Terraform without rewriting your IaC by hand — this tool gives you
a high-fidelity starting point.

---

## Quickstart

```bash
# 1. Install (until v0.1.0 hits PyPI, install from source)
git clone https://github.com/ParthVyas2912/bicep2tf && cd bicep2tf
pip install -e .

# 2. Convert your Bicep → Terraform
bicep2tf ./infra/main.bicep -o ./terraform-output
cd terraform-output
terraform init && terraform plan
```

You will need the [`bicep` CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install)
and [Terraform ≥ 1.6](https://developer.hashicorp.com/terraform/install).

Sample input ships in this repo — see [`examples/`](examples/). The end-to-end
smoke test under [`tests/test_smoke.py`](tests/test_smoke.py) compiles
[`tests/cases/simple-rg/input.bicep`](tests/cases/simple-rg/input.bicep) and
asserts that the generated Terraform passes `terraform validate` against
`hashicorp/azurerm ~> 4.0`.

---

## Features

- **Bicep module fidelity** — each `module` in Bicep becomes a TF module under
  `terraform-output/modules/<name>/`.
- **Subscription-scope handling** — `targetScope = 'subscription'` is converted
  to an `azurerm_resource_group` resource (not a stale `data` lookup).
- **Conditional modules** — Bicep `if (cond)` becomes `count = cond ? 1 : 0`.
- **For-expressions / `copyIndex()`** — converted to `for_each` / `count`.
- **AVM bridge** — Bicep `br/public:avm/res/<x>` references are mapped to the
  equivalent `Azure/avm-res-<x>/azurerm` Terraform module when one exists, with
  a `--avm-mode {reference,expand,skip}` flag.
- **RBAC** — `Microsoft.Authorization/roleAssignments` becomes
  `azurerm_role_assignment` with `scope`, `role_definition_name`, `principal_id`,
  and `principal_type`.
- **Networking** — VNets, subnets (with delegations), private endpoints, and
  private DNS zone groups are emitted as first-class resources.
- **`@secure()` parameters** — translated to `sensitive = true` variables.
- **Determinism** — re-running on identical input produces byte-identical output.
- **Post-validation** — runs `terraform fmt -recursive` and `terraform validate`
  and writes `terraform_validate.json` next to the output.
- **Coverage matrix** — every supported / partial / unsupported `Microsoft.*`
  type is published in [`docs/coverage.md`](docs/coverage.md).

---

## CLI

```text
bicep2tf <input.bicep> [options]

Options:
  -o, --output <dir>             Output directory (default: ./terraform-output)
      --layout {bicep,service,flat}
                                 Module grouping strategy (default: bicep)
      --provider-version <ver>   azurerm version constraint (default: ~> 4.0)
      --avm-mode {reference,expand,skip}
                                 How to handle AVM Bicep modules (default: reference)
      --strict                   Fail if any unmapped type or TODO is emitted
      --no-validate              Skip terraform fmt/validate post-step
      --import                   Emit `import {}` blocks for resources that
                                 already exist (Terraform 1.5+)
      --json                     Emit machine-readable logs to stdout
      --config <file>            Load defaults from bicep2tf.yaml
  -h, --help
```

---

## Configuration (`bicep2tf.yaml`)

See [`bicep2tf.yaml.example`](bicep2tf.yaml.example) for all options.

---

## How conversion works

1. `bicep build` compiles Bicep → ARM JSON.
2. The ARM resource graph is walked and each resource is matched against
   mapping rules in [`mappings/`](mappings/) (one YAML per ARM provider).
3. Bicep modules are preserved as Terraform modules; outputs flow between them
   via a dependency graph extracted from the ARM template.
4. ARM functions (`resourceId`, `reference`, `tryGet`, `copyIndex`, `format`,
   `concat`, `union`, `if`, …) are translated to their HCL/Terraform equivalents.
5. The result is formatted with `terraform fmt` and verified with
   `terraform validate`. Failures are written to `terraform_validate.json`.

---

## Coverage

Top-50 most-used `Microsoft.*` types — see
[`docs/coverage.md`](docs/coverage.md).

Have an unmapped type? Open an [unmapped-type
issue](.github/ISSUE_TEMPLATE/unmapped-type.md) — that's the highest-leverage
contribution you can make.

---

## Contributing

We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md). The fastest
way to help is to add a YAML mapping rule under [`mappings/`](mappings/) and a
golden-file test under [`tests/cases/`](tests/cases/).

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) and report security
issues per [SECURITY.md](SECURITY.md).

---

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
