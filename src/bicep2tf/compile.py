"""Invoke `bicep build` and return the resulting ARM template as a Python dict."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class BicepCompileError(RuntimeError):
    pass


def compile_bicep(input_file: Path) -> dict:
    """Run `bicep build --stdout` against *input_file* and return parsed ARM JSON."""
    bicep = shutil.which("bicep")
    if bicep is None:
        raise BicepCompileError(
            "The `bicep` CLI was not found on PATH. Install from "
            "https://learn.microsoft.com/azure/azure-resource-manager/bicep/install"
        )

    proc = subprocess.run(
        [bicep, "build", "--stdout", str(input_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise BicepCompileError(f"bicep build failed:\n{proc.stderr}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BicepCompileError(f"bicep produced invalid JSON: {exc}") from exc
