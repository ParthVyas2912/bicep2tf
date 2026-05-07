"""Configuration model + YAML loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    output: Path = Path("./terraform-output")
    layout: str = "bicep"
    provider_version: str = "~> 4.0"
    avm_mode: str = "reference"
    strict: bool = False
    post_validate: bool = True
    emit_import_blocks: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)

    def merge_cli(self, **overrides: Any) -> None:
        for k, v in overrides.items():
            if v is not None and hasattr(self, k):
                setattr(self, k, v)


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = Config()
    if "output" in data:
        cfg.output = Path(data["output"])
    if "layout" in data:
        cfg.layout = data["layout"]
    if "providers" in data and "azurerm" in data["providers"]:
        cfg.provider_version = data["providers"]["azurerm"]
    if "avm_mode" in data:
        cfg.avm_mode = data["avm_mode"]
    if "strict" in data:
        cfg.strict = bool(data["strict"])
    if "post_validate" in data:
        cfg.post_validate = bool(data["post_validate"])
    if "emit_import_blocks" in data:
        cfg.emit_import_blocks = bool(data["emit_import_blocks"])
    if "tags" in data:
        cfg.tags = dict(data["tags"])
    if "rules" in data:
        cfg.rules = dict(data["rules"])
    return cfg
