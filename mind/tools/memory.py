from __future__ import annotations

from typing import Any

from mind.core.config import Config
from mind.memory import list_memories


def tool_memory_list(config: Config, args: dict[str, Any]) -> str:
    """List saved memories."""
    memories = list_memories(config)

    if not memories:
        return "No memories stored."

    lines = ["Saved memories:"]

    for _, memory_text in memories:
        lines.append(f"- {memory_text}")

    return "\n".join(lines)
