from __future__ import annotations

from mind.tools import ToolSpec


def confirm_tool_run(spec: ToolSpec) -> bool:
    """Ask the terminal user whether Mind should run a confirmation-required tool."""
    response = input(
        f"Tool '{spec.name}' requires confirmation.\n"
        f"Permission: {spec.permission}\n"
        f"Description: {spec.description}\n"
        "Run this tool? (y/n): "
    ).strip().lower()

    return response in {"y", "yes"}
