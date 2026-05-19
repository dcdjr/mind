from __future__ import annotations

from typing import Any

from mind.core.config import Config
from mind.tools.internet import tool_internet_github_zen
from mind.tools.memory import tool_memory_list
from mind.tools.result import ToolResult
from mind.tools.spec import ToolSpec
from mind.tools.workspace import (
    tool_workspace_append_file,
    tool_workspace_list_files,
    tool_workspace_read_file,
    tool_workspace_write_file,
)
from mind.tools.codebase import (
    tool_codebase_read_file,
    tool_codebase_list_files,
)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "workspace.list_files": ToolSpec(
        name="workspace.list_files",
        description="List files in the workspace.",
        args_description="{}",
        permission="read_only",
        function=tool_workspace_list_files,
        requires_confirmation=False,
    ),
    "workspace.read_file": ToolSpec(
        name="workspace.read_file",
        description="Read a workspace-relative file.",
        args_description='{"path": "notes.txt"}',
        permission="read_only",
        function=tool_workspace_read_file,
        requires_confirmation=False,
    ),
    "workspace.write_file": ToolSpec(
        name="workspace.write_file",
        description="Write text to a workspace-relative file.",
        args_description='{"path": "notes.txt", "content": "text", "overwrite": false}',
        permission="local_write",
        function=tool_workspace_write_file,
        requires_confirmation=True,
    ),
    "workspace.append_file": ToolSpec(
        name="workspace.append_file",
        description="Append text to a workspace-relative file.",
        args_description='{"path": "notes.txt", "content": "text", "create": true}',
        permission="local_write",
        function=tool_workspace_append_file,
        requires_confirmation=True,
    ),
    "memory.list": ToolSpec(
        name="memory.list",
        description="List saved memories.",
        args_description="{}",
        permission="read_only",
        function=tool_memory_list,
        requires_confirmation=False,
    ),
    "codebase.list_files": ToolSpec(
        name="codebase.list_files",
        description="List source files in the configured project codebase.",
        args_description="{}",
        permission="read_only",
        function=tool_codebase_list_files,
        requires_confirmation=False,
    ),
    "codebase.read_file": ToolSpec(
        name="codebase.read_file",
        description="Read a project-relative source file from the configured codebase.",
        args_description='{"path": "mind/agent/loop.py"}',
        permission="read_only",
        function=tool_codebase_read_file,
        requires_confirmation=False,
    ),
    "internet.github_zen": ToolSpec(
        name="internet.github_zen",
        description="Fetch a short random phrase from GitHub's public Zen API.",
        args_description="{}",
        permission="external_read",
        function=tool_internet_github_zen,
        requires_confirmation=False,
    ),
}


def _tool_is_allowed_to_run(config: Config, spec: ToolSpec) -> bool:
    """Return whether a tool is allowed under the current config."""
    if spec.permission == "local_write" and not config.tools.allow_local_write:
        return False

    if spec.permission == "external_read" and not config.tools.allow_external_read:
        return False

    if spec.permission == "external_write" and not config.tools.allow_external_write:
        return False

    if spec.permission == "dangerous" and not config.tools.allow_dangerous:
        return False

    return True


def run_tool(
    config: Config,
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> ToolResult:
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
            error=(
                f"Error: Tool '{tool_name}' requires permission "
                f"'{spec.permission}', but that permission is disabled."
            ),
        )

    if spec.requires_confirmation is True and config.tools.require_confirmation:
        user_confirmation = input(
            f"Tool: {tool_name}\n"
            f"Args: {safe_args}\n"
            "This tool requires confirmation to be run.\n"
            "Run this tool? (y/n): "
        ).strip().lower()

        if user_confirmation not in {"y", "yes"}:
            return ToolResult.failure_result(
                tool_name=tool_name,
                error=f"User did not confirm that {tool_name} can be run.",
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


def format_available_tools(config: Config) -> str:
    """Return a prompt-friendly list of tools available under the current config."""
    available_tools = []

    for spec in TOOL_REGISTRY.values():
        if not spec.available_to_agent:
            continue

        if not _tool_is_allowed_to_run(config, spec):
            continue

        confirmation = "yes" if spec.requires_confirmation else "no"

        available_tools.append(
            "\n".join(
                [
                    f"- {spec.name}",
                    f"  Description: {spec.description}",
                    f"  Args: {spec.args_description}",
                    f"  Permission: {spec.permission}",
                    f"  Requires confirmation: {confirmation}",
                ]
            )
        )

    if not available_tools:
        return "No tools are currently available."

    return "\n".join(available_tools)
