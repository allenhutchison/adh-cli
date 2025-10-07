#!/usr/bin/env python3
"""
Generate a Tools Reference from registered ToolSpecs.

Writes docs/TOOLS.md with an overview of each tool, its parameters,
tags, and effects. Uses the same registry ADHApp uses.
"""

from pathlib import Path
from textwrap import indent


def format_param_table(params: dict) -> str:
    if not params:
        return "(no parameters)\n"

    lines = ["| Name | Type | Default | Description |", "|---|---|---|---|"]
    for name, spec in params.items():
        ptype = spec.get("type", "-")
        default = spec.get("default", spec.get("nullable", ""))
        if default is True:
            default = "true"
        elif default is False:
            default = "false"
        lines.append(
            f"| `{name}` | `{ptype}` | {default} | {spec.get('description', '')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    # Lazy import to avoid side effects until needed
    from adh_cli.tools.specs import register_default_specs
    from adh_cli.tools.base import registry

    register_default_specs()
    specs = sorted(registry.all(), key=lambda s: s.name)

    out = [
        "# Tools Reference",
        "",
        "This document is generated from `ToolSpec` entries. Edit `adh_cli/tools/specs.py` to change metadata or add new tools.",
        "",
    ]

    for spec in specs:
        out.append(f"## `{spec.name}`")
        out.append("")
        out.append(spec.description)
        out.append("")
        if spec.tags:
            out.append(f"- Tags: {', '.join(spec.tags)}")
        if spec.effects:
            out.append(f"- Effects: {', '.join(spec.effects)}")
        out.append("")
        out.append("Parameters:")
        out.append("")
        out.append(format_param_table(spec.parameters))
        out.append("")

    project_root = Path(__file__).parent.parent
    docs_path = project_root / "docs" / "TOOLS.md"
    docs_path.write_text("\n".join(out), encoding="utf-8")
    print(f"✅ Wrote {docs_path}")


if __name__ == "__main__":
    main()
