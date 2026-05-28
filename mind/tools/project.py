from __future__ import annotations

from typing import Any

from mind.core.config import Config
from mind.project.status import build_project_status
from mind.project.devlog import append_project_devlog


def tool_project_status(config: Config, args: dict[str, Any]) -> str:
    """Return a project status summary."""


    from mind.tools.registry import TOOL_REGISTRY, count_available_agent_tools

    return build_project_status(
        config,
        registered_tool_count=len(TOOL_REGISTRY),
        available_tool_count=count_available_agent_tools(config),
    )


def tool_project_devlog(config: Config, args: dict[str, Any]) -> str:
    """Append a project devlog entry to workspace/devlog.md"""
    summary = args.get("summary")
    next_steps = args.get("next_steps")

    if not isinstance(summary, str) or not summary.strip():
        return "Error: project.devlog requires a non-empty string argument named 'summary'."

    if next_steps is None:
        parsed_next_steps = None
    elif isinstance(next_steps, list) and all(isinstance(step, str) for step in next_steps):
        parsed_next_steps = next_steps
    else:
        return "Error: project.devlog requires 'next_steps' to be a list of strings when provided."

    result = append_project_devlog(
        config,
        summary=summary,
        next_steps=parsed_next_steps,
    )

    if result.startswith("Error:"):
        return result

    return "Appended project devlog entry to workspace/devlog.md."
