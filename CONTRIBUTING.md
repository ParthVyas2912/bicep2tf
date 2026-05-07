# Contributing to bicep2tf

Thanks for your interest in improving `bicep2tf`! The two highest-leverage
contributions are:

1. **Adding a mapping rule** for an unmapped `Microsoft.*` resource type.
2. **Adding a golden-file test case** that locks in correct conversion
   behaviour for a real Bicep snippet.

---

## Dev setup

```bash
git clone https://github.com/ParthVyas2912/bicep2tf
cd bicep2tf
python -m venv .venv && . .venv/bin/activate     # or use uv / poetry
pip install -e ".[dev]"
pre-commit install
```

You will also need:

- `bicep` CLI (>= 0.27)
- `terraform` CLI (>= 1.6)
- `tflint` (optional, for extended checks)

Run the test suite:

```bash
pytest -q
```

---

## Adding a mapping rule

Mappings live under [`mappings/`](mappings/), one YAML file per ARM provider:

```yaml
# mappings/microsoft.web.yaml
- arm_type: Microsoft.Web/sites
  tf_type: azurerm_linux_web_app
  attribute_map:
    properties.serverFarmId: service_plan_id
    properties.httpsOnly:    https_only
  child_resources:
    - arm_type: Microsoft.Web/sites/config
      strategy: inline             # merged into parent's site_config
```

Open the issue tracker filter `label:unmapped-type` to find prioritised
candidates.

---

## Adding a golden-file test

```text
tests/cases/<case-name>/
├── input.bicep
├── bicep2tf.yaml          # optional, per-case overrides
└── expected/
    ├── main.tf
    ├── variables.tf
    └── ...
```

CI runs `bicep2tf` against `input.bicep`, diffs against `expected/`, then runs
`terraform init && terraform validate` against the produced output.

To regenerate snapshots after intentional changes:

```bash
pytest --update-snapshots
```

---

## Coding standards

- Python: `ruff check` + `ruff format` are enforced by CI and pre-commit.
- `mypy` is run in non-strict mode today; tightening to `--strict` is tracked
  as a future-work item, contributions welcome.
- Conventional Commits for commit messages (`feat:`, `fix:`, `docs:`, …).
- One PR = one logical change. Add tests.

## Releases

Releases are cut manually by tagging `vMAJOR.MINOR.PATCH` on `main`. The
[`release.yml`](.github/workflows/release.yml) workflow then builds the
Python wheel + sdist, publishes the package to PyPI (via OIDC trusted
publishing), pushes a container image to GHCR, and creates a GitHub Release
with the built artefacts attached.
