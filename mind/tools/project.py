from __future__ import annotations

from typing import Any

from mind.core.config import Config
from mind.project.status import build_project_status


def tool_project_status(config: Config, args: dict[str, Any]) -> str:
    """Return a project status summary."""
    

    from mind.tools.registry import TOOL_REGISTRY, count_available_agent_tools

    return build_project_status(
        config,
        registered_tool_count=len(TOOL_REGISTRY),
        available_tool_count=count_available_agent_tools(config),
    )
