from __future__ import annotations

from mind import __version__
from mind.core.config import Config
from mind.memory import list_memories
from mind.workspace import list_workspace_files


def _enabled(value: bool) -> str:
    """Return a consistent enabled/disabled label for project status output."""
    return "enabled" if value else "disabled"


def build_project_status(
    config: Config,
    registered_tool_count: int | None = None,
    available_tool_count: int | None = None,
) -> str:
    """Build a deterministic project status summary."""
    workspace_file_count = len(list_workspace_files(config))
    memory_count = len(list_memories(config))

    registered_tools = (
        "unknown" if registered_tool_count is None else str(registered_tool_count)
    )
    available_tools = (
        "unknown" if available_tool_count is None else str(available_tool_count)
    )

    return (
        "PROJECT STATUS BEGIN\n\n"
        f"Mind version: {__version__}\n"
        f"Configured provider/model: {config.model.provider} / {config.model.default}\n"
        f"Workspace path: {config.paths.workspace}\n"
        f"Database path: {config.paths.database}\n"
        f"Project root: {config.project.root}\n"
        f"Workspace files: {workspace_file_count}\n"
        f"Stored memories: {memory_count}\n"
        f"Registered tools: {registered_tools}\n"
        f"Available agent tools: {available_tools}\n\n"
        "Tool safety:\n"
        f"  external_read: {_enabled(config.tools.allow_external_read)}\n"
        f"  local_write: {_enabled(config.tools.allow_local_write)}\n"
        f"  external_write: {_enabled(config.tools.allow_external_write)}\n"
        f"  dangerous: {_enabled(config.tools.allow_dangerous)}\n"
        f"  confirmation: {_enabled(config.tools.require_confirmation)}\n\n"
        "PROJECT STATUS END"
    )
