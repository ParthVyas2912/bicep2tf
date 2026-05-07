"""End-to-end smoke test (skipped if bicep/terraform aren't installed)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from bicep2tf.compile import compile_bicep
from bicep2tf.config import Config
from bicep2tf.convert import convert
from bicep2tf.render import render
from bicep2tf.report import write_report

CASE_DIR = Path(__file__).parent / "cases" / "simple-rg"


@pytest.mark.skipif(shutil.which("bicep") is None, reason="bicep CLI not installed")
def test_simple_rg_conversion(tmp_path: Path):
    arm = compile_bicep(CASE_DIR / "input.bicep")
    ir = convert(arm, source=CASE_DIR / "input.bicep", config=Config())
    render(ir, output_dir=tmp_path, config=Config())

    main_tf = (tmp_path / "main.tf").read_text(encoding="utf-8")
    assert 'resource "azurerm_resource_group"' in main_tf

    if shutil.which("terraform"):
        subprocess.run(["terraform", "init", "-backend=false"], cwd=tmp_path, check=True)
        subprocess.run(["terraform", "validate"], cwd=tmp_path, check=True)

    write_report(tmp_path, CASE_DIR / "input.bicep", ir, validate_result=None)
    assert (tmp_path / "conversion_report.json").exists()
