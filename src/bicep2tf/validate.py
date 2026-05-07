"""Run `terraform fmt` and `terraform validate` and capture results."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run_terraform_validate(output_dir: Path) -> dict[str, Any]:
    if shutil.which("terraform") is None:
        return {"valid": None, "skipped": "terraform CLI not found"}

    init = subprocess.run(
        ["terraform", "init", "-backend=false", "-input=false", "-no-color"],
        cwd=output_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if init.returncode != 0:
        result = {"valid": False, "stage": "init", "stderr": init.stderr, "stdout": init.stdout}
        (output_dir / "terraform_validate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    val = subprocess.run(
        ["terraform", "validate", "-json", "-no-color"],
        cwd=output_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        parsed = json.loads(val.stdout)
    except json.JSONDecodeError:
        parsed = {"valid": False, "stage": "validate", "stderr": val.stderr, "stdout": val.stdout}
    (output_dir / "terraform_validate.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    return parsed
