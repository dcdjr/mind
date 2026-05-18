from __future__ import annotations

from typing import Any

from mind.core.config import Config
from mind.tools.internet import tool_internet_github_zen
from mind.tools.memory import tool_memory_list
from mind.tools.result import ToolResult
from mind.tools.spec import ToolSpec
from mind.tools.workspace import (
    tool_workspace_list_files,
    tool_workspace_read_file,
)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "workspace.list_files": ToolSpec(
        name="workspace.list_files",
        description="List files in the workspace.",
        args_description="{}",
        permission="read_only",
        function=tool_workspace_list_files,
    ),
    "workspace.read_file": ToolSpec(
        name="workspace.read_file",
        description="Read a workspace-relative file.",
        args_description='{"path": "notes.txt"}',
        permission="read_only",
        function=tool_workspace_read_file,
    ),
    "memory.list": ToolSpec(
        name="memory.list",
        description="List saved memories.",
        args_description="{}",
        permission="read_only",
        function=tool_memory_list,
    ),
    "internet.github_zen": ToolSpec(
        name="internet.github_zen",
        description="Fetch a short random phrase from GitHub's public Zen API.",
        args_description="{}",
        permission="external_read",
        function=tool_internet_github_zen,
    ),
}


def _tool_is_allowed_to_run(config: Config, spec: ToolSpec) -> bool:
    if spec.permission == "local_write" and not config.tools.allow_local_write:
        return False
    elif spec.permission == "external_read" and not config.tools.allow_external_read:
        return False
    elif spec.permission == "external_write" and not config.tools.allow_external_write:
        return False
    elif spec.permission == "dangerous" and not config.tools.allow_dangerous:
        return False

    return True


def run_tool(config: Config, tool_name: str, args: dict[str, Any] | None = None) -> ToolResult:
    """Run a known safe internal Mind tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=f"Unknown tool '{tool_name}'.",
        )

    safe_args = args or {}
    spec = TOOL_REGISTRY[tool_name]

    if not _tool_is_allowed_to_run(config, spec):
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=f"Error: Tool '{tool_name}' requires permission 'external_read', but that permission is disabled."
        )

    try:
        output = spec.function(config, safe_args)
    except Exception as error:
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=f"Tool raised {type(error).__name__}: {error}.",
        )
    
    if not isinstance(output, str):
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=(
                f"Tool '{tool_name}' returned {type(output).__name__}, "
                "but Mind tools must return strings."
            ),
        )

    return ToolResult.success_result(
        tool_name=tool_name,
        output=output,
    )


def format_available_tools() -> str:
    """Return a prompt-friendly list of available tools."""
    available_tools = []

    for _, spec in TOOL_REGISTRY.items():
        if spec.available_to_agent:
            available_tools.append(
                f"- {spec.name}: {spec.description} Args: {spec.args_description}"
            )
            
    return "\n".join(available_tools)
