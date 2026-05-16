from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.core.config import Config
from mind.workspace import list_workspace_files, read_workspace_file


def tool_workspace_list_files(config: Config, args: dict[str, Any]) -> str:
    """List files in Mind's controlled workspace."""
    files = list_workspace_files(config)

    if not files:
        return "Workspace is empty."

    lines = ["Workspace files:"]

    for file in files:
        lines.append(f"- {file}")

    return "\n".join(lines)


def tool_workspace_read_file(config: Config, args: dict[str, Any]) -> str:
    """Read a workspace-relative file path."""
    path = args.get("path")

    if not isinstance(path, str) or not path.strip():
        return "Error: workspace.read_file requires a non-empty string argument named 'path'."

    content = read_workspace_file(config, Path(path))

    return f"FILE: {path}\n---\n{content}"
