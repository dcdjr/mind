from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from mind.config import Config
from mind.memory import list_memories
from mind.workspace import list_workspace_files, read_workspace_file


# Defines the type of a ToolFunction.
# This means every tool function most follow the same signature.
# This allows different tools to be stored in a dictionary.
ToolFunction = Callable[[Config, dict[str, Any]], str]


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


def tool_memory_list(config: Config, args: dict[str, Any]) -> str:
    """List saved memories."""
    memories = list_memories(config)

    if not memories:
        return "No memories stored."

    lines = ["Saved memories:"]

    for _, memory_text in memories:
        lines.append(f"- {memory_text}")

    return "\n".join(lines)


TOOL_REGISTRY: dict[str, ToolFunction] = {
    "workspace.list_files": tool_workspace_list_files,
    "workspace.read_file": tool_workspace_read_file,
    "memory.list": tool_memory_list,
}


def run_tool(config: Config, tool_name: str, args: dict[str, Any] | None = None) -> str:
    """Run a known safe internal Mind tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Unknown tool '{tool_name}'."

    safe_args = args or {}

    return TOOL_REGISTRY[tool_name](config, safe_args)


def format_available_tools() -> str:
    """Return a prompt-friendly list of available tools."""
    return "\n".join(
        [
            "- workspace.list_files: list files in the workspace. Args: {}",
            '- workspace.read_file: read a workspace-relative file. Args: {"path": "notes.txt"}',
            "- memory.list: list saved memories. Args: {}",
        ]
    )
