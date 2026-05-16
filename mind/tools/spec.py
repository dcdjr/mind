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
    name: str
    description: str
    args_description: str
    permission: PermissionLevel
    function: ToolFunction
    available_to_agent: bool = True
