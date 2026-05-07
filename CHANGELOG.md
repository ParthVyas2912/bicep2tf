# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-07

Initial public preview. The converter is functional end-to-end for the
sample workloads in [`examples/`](examples/) and the test fixtures under
[`tests/cases/`](tests/cases/), and the generated Terraform passes
`terraform init` + `terraform validate` against `hashicorp/azurerm ~> 4.0`.

### Added

- **Bicep → Terraform conversion** with module fidelity (each Bicep `module`
  becomes a Terraform module under `terraform-output/modules/<name>/`).
- **Subscription-scope handling** — `targetScope = 'subscription'` is converted
  to a real `azurerm_resource_group` resource (not a stale `data` lookup).
- **Conditional modules** — Bicep `if (cond)` becomes `count = cond ? 1 : 0`.
- **For-expressions / `copyIndex()`** — converted to `for_each` / `count`.
- **AVM bridge** with `--avm-mode {reference,expand,skip}` to control how Bicep
  `br/public:avm/res/<x>` references are emitted.
- **RBAC** — `Microsoft.Authorization/roleAssignments` becomes
  `azurerm_role_assignment` with `scope`, `role_definition_name`,
  `principal_id`, and `principal_type`.
- **Networking** — VNets, subnets (with delegations), private endpoints, and
  private DNS zone groups are emitted as first-class resources.
- **`@secure()` parameters** translated to `sensitive = true` variables.
- **Mapping rule extensions:** `required_defaults`, `required_blocks`,
  `drop_attributes`, `rename_attributes`, `wrap_list_attributes` — letting
  YAML mapping authors satisfy provider schema requirements without code.
- **`--strict` flag** fails the run if any unmapped type or TODO marker is
  emitted.
- **Auto-validation:** `terraform fmt -recursive` and `terraform validate`
  run after every conversion; a machine-readable `terraform_validate.json`
  is written next to the output.
- **`conversion_report.json`** summarising mappings, warnings, and unmapped
  resource types.
- **CI:** GitHub Actions workflow runs ruff + pytest on every PR and validates
  the generated Terraform for each fixture under `tests/cases/`.
- **Container image** published from the included [`Dockerfile`](Dockerfile).

### Known limitations

- Some `Microsoft.*` resource types are still unmapped — the run will emit a
  `TODO_unmapped_<type>` Terraform resource and a row in
  `conversion_report.json`. Contributions of new mapping YAMLs are welcome
  (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).
- `mypy --strict` is not yet enforced; tightening type coverage is tracked
  as future work.