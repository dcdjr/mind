from __future__ import annotations

from typing import Any, Callable

from mind.core.config import Config
from mind.tools.internet import tool_internet_github_zen
from mind.tools.memory import tool_memory_list
from mind.tools.workspace import (
    tool_workspace_list_files,
    tool_workspace_read_file,
)


ToolFunction = Callable[[Config, dict[str, Any]], str]


TOOL_REGISTRY: dict[str, ToolFunction] = {
    "workspace.list_files": tool_workspace_list_files,
    "workspace.read_file": tool_workspace_read_file,
    "memory.list": tool_memory_list,
    "internet.github_zen": tool_internet_github_zen,
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
            "- internet.github_zen: fetch a short random phrase from GitHub's public Zen API. Args: {}",
        ]
    )
