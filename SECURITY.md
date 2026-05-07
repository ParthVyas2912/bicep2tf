# Security Policy

## Supported versions

Only the latest minor release of `bicep2tf` receives security fixes.

## Reporting a vulnerability

**Do not open a public issue.** Instead, use GitHub's private vulnerability
reporting:

1. Go to the **Security** tab of the repository.
2. Click **Report a vulnerability**.

If GitHub Security Advisories is unavailable, email the maintainers (address
listed in the repository profile). We aim to acknowledge within 3 business
days and to publish a fix or mitigation within 30 days for high-severity
issues.

## Scope

In scope:

- Code execution, path traversal, or arbitrary write via crafted Bicep input.
- Secrets exfiltration via generated Terraform.
- Supply-chain issues in published artefacts (PyPI, GHCR).

Out of scope:

- Generated Terraform that fails to deploy (file a normal bug instead).
- Issues in upstream `bicep`, `terraform`, or `azurerm` provider — please
  report those upstream.
