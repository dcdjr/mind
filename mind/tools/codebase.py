from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.codebase import list_codebase_files, read_codebase_file
from mind.core.config import Config


def tool_codebase_list_files(config: Config, args: dict[str, Any]) -> str:
    """List files in the configured project codebase."""
    files = list_codebase_files(config)

    if not files:
        return "Codebase has no visible files."

    lines = ["Codebase files:"]

    for file in files:
        lines.append(f"- {file}")

    return "\n".join(lines)


def tool_codebase_read_file(config: Config, args: dict[str, Any]) -> str:
    """Read a project-relative source file from the configured codebase."""
    path = args.get("path")

    if not isinstance(path, str) or not path.strip():
        return "Error: codebase.read_file requires a non-empty string argument named 'path'."

    content = read_codebase_file(config, Path(path))

    return f"FILE: {path}\n---\n{content}"
