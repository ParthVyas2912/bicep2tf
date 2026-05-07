"""Write conversion_report.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .ir import IR


def write_report(output_dir: Path, source: Path, ir: IR, validate_result: dict | None) -> dict[str, Any]:
    mappings = []
    total_resources = 0
    total_todos = 0
    for mod in [ir.root, *ir.modules.values()]:
        for r in mod.resources:
            mappings.append(
                {
                    "module": mod.name,
                    "arm_type": r.arm_type,
                    "tf_type": r.tf_type,
                    "symbolic_name": r.symbolic_name,
                    "is_data_source": r.is_data_source,
                    "todo": r.todo,
                }
            )
            if r.todo:
                total_todos += 1
            else:
                total_resources += 1

    report = {
        "tool": "bicep2tf",
        "version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": str(source),
        "output": str(output_dir),
        "summary": {
            "total_resources_mapped": total_resources,
            "total_modules": 1 + len(ir.modules),
            "total_variables": len(ir.root.parameters),
            "total_outputs": len(ir.root.outputs),
            "total_unmapped": len(ir.unmapped_types),
            "total_todos": total_todos,
            "total_warnings": sum(len(m.warnings) for m in [ir.root, *ir.modules.values()]),
        },
        "unmapped_types": sorted(set(ir.unmapped_types)),
        "mappings": mappings,
        "validate": validate_result or {},
    }

    (output_dir / "conversion_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report
