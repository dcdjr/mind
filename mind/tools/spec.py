from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from mind.core.config import Config


ToolFunction = Callable[[Config, dict[str, Any]], str]

PermissionLevel = Literal[
    "read_only",
    "external_read",
    "local_write",
    "external_write",
    "dangerous",
]


@dataclass(frozen=True)
class ToolSpec:
    """Metadata and callable for one controlled Mind tool."""

    name: str
    description: str
    args_description: str
    permission: PermissionLevel
    function: ToolFunction

    # New tools should fail closed: if the developer forgets to decide,
    # Mind treats the tool as needing explicit user confirmation.
    requires_confirmation: bool = True

    # Controls whether the model can see/request this tool in agent mode.
    available_to_agent: bool = True
