"""CLI entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .compile import compile_bicep
from .config import Config, load_config
from .convert import convert
from .render import render
from .report import write_report
from .validate import run_terraform_validate

console = Console()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path("./terraform-output"),
    help="Output directory.",
)
@click.option(
    "--layout",
    type=click.Choice(["bicep", "service", "flat"]),
    default="bicep",
    help="Module grouping strategy.",
)
@click.option("--provider-version", default="~> 4.0", help="azurerm version constraint.")
@click.option(
    "--avm-mode",
    type=click.Choice(["reference", "expand", "skip"]),
    default="reference",
    help="How to handle Bicep AVM modules.",
)
@click.option("--strict", is_flag=True, help="Fail on any unmapped type or TODO marker.")
@click.option("--no-validate", is_flag=True, help="Skip terraform fmt/validate post-step.")
@click.option("--emit-import-blocks", is_flag=True, help="Emit Terraform 1.5+ import {} blocks.")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load defaults from a bicep2tf.yaml file.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable logs to stdout.")
@click.version_option(__version__, prog_name="bicep2tf")
def main(
    input_file: Path,
    output: Path,
    layout: str,
    provider_version: str,
    avm_mode: str,
    strict: bool,
    no_validate: bool,
    emit_import_blocks: bool,
    config_path: Path | None,
    json_output: bool,
) -> None:
    """Convert a Bicep file to Terraform.

    INPUT_FILE is the entrypoint .bicep file (typically main.bicep).
    """
    config = load_config(config_path) if config_path else Config()
    config.merge_cli(
        output=output,
        layout=layout,
        provider_version=provider_version,
        avm_mode=avm_mode,
        strict=strict,
        post_validate=not no_validate,
        emit_import_blocks=emit_import_blocks,
    )

    output.mkdir(parents=True, exist_ok=True)

    if not json_output:
        console.print(f"[bold]bicep2tf[/bold] v{__version__} — converting [cyan]{input_file}[/cyan]")

    arm_template = compile_bicep(input_file)
    ir = convert(arm_template, source=input_file, config=config)
    render(ir, output_dir=output, config=config)

    validate_result: dict | None = None
    if config.post_validate:
        validate_result = run_terraform_validate(output)

    report = write_report(
        output_dir=output,
        source=input_file,
        ir=ir,
        validate_result=validate_result,
    )

    if json_output:
        click.echo(json.dumps(report, indent=2, default=str))
    else:
        _print_summary(report)

    if config.strict and (report["summary"]["total_unmapped"] > 0 or report["summary"]["total_todos"] > 0):
        console.print("[red]--strict: unmapped types or TODOs were emitted.[/red]")
        sys.exit(2)
    if validate_result and not validate_result.get("valid", True):
        sys.exit(3)


def _print_summary(report: dict) -> None:
    s = report["summary"]
    table = Table(title="Conversion summary", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    for key in (
        "total_resources_mapped",
        "total_modules",
        "total_variables",
        "total_outputs",
        "total_unmapped",
        "total_todos",
        "total_warnings",
    ):
        table.add_row(key, str(s.get(key, 0)))
    console.print(table)
    if report.get("validate", {}).get("valid") is False:
        console.print("[red]terraform validate FAILED — see terraform_validate.json[/red]")
    elif report.get("validate", {}).get("valid"):
        console.print("[green]terraform validate passed[/green]")
