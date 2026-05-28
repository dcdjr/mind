from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mind.core.config import Config
from mind.tools.codebase import (
    tool_codebase_list_files,
    tool_codebase_read_file,
)
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
from mind.tools.project import tool_project_status, tool_project_devlog


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
    "project.status": ToolSpec(
        name="project.status",
        description="List information about the current status of the Mind project.",
        args_description="{}",
        permission="read_only",
        function=tool_project_status,
        requires_confirmation=False,
    ),
    "project.devlog": ToolSpec(
        name="project.devlog",
        description="Append a dated project devlog entry to workspace/devlog.md.",
        args_description='{"summary": "What changed today.", "next_steps": ["Next task."]}',
        permission="local_write",
        function=tool_project_devlog,
        requires_confirmation=True,
    ),
}


def count_available_agent_tools(config: Config) -> int:
    """Return the number of agent-visible tools allowed by the current config."""
    return sum(
        1
        for spec in TOOL_REGISTRY.values()
        if spec.available_to_agent and tool_is_allowed_to_run(config, spec)
    )


def tool_is_allowed_to_run(config: Config, spec: ToolSpec) -> bool:
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
    confirm: Callable[[ToolSpec], bool] | None = None,
) -> ToolResult:
    """Run a known safe internal Mind tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=f"Unknown tool '{tool_name}'.",
        )

    safe_args = args or {}
    spec = TOOL_REGISTRY[tool_name]

    if not tool_is_allowed_to_run(config, spec):
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=(
                f"Error: Tool '{tool_name}' requires permission "
                f"'{spec.permission}', but that permission is disabled."
            ),
        )

    if config.tools.require_confirmation and spec.requires_confirmation:
        if confirm is None:
            return ToolResult.failure_result(
                tool_name=tool_name,
                error=(
                    f"Tool '{tool_name}' requires confirmation, "
                    "but no confirmation handler was provided."
                ),
            )

        if not confirm(spec):
            return ToolResult.failure_result(
                tool_name=tool_name,
                error=f"User did not confirm tool '{tool_name}'.",
            )

    try:
        output = spec.function(config, safe_args)

        if not isinstance(output, str):
            return ToolResult.failure_result(
                tool_name=tool_name,
                error=(
                    f"Tool '{tool_name}' returned {type(output).__name__}, "
                    "but Mind tools must return strings."
                ),
            )

        if output.startswith("Error:"):
            # Tool implementations return user-facing strings; this prefix is
            # the lightweight convention that marks the string as a failure.
            return ToolResult.failure_result(
                tool_name=tool_name,
                error=output,
            )

    except Exception as error:
        return ToolResult.failure_result(
            tool_name=tool_name,
            error=f"Tool raised {type(error).__name__}: {error}.",
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

        if not tool_is_allowed_to_run(config, spec):
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
