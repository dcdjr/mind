from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mind.agent.trace import AgentTrace, format_traced_response


AgentRunStatus = Literal["completed", "failed"]


@dataclass(frozen=True)
class AgentRunResult:
    """Structured result from one Mind agent run.

    This is the API-ready return type. CLI code can render it as text, while
    future WebUI/API code can expose the fields directly as JSON.
    """

    final_answer: str
    status: AgentRunStatus
    error: str | None
    trace: AgentTrace | None
    model: str
    tool_calls: int
    model_calls: int
    protocol_repairs: int

    def render(self, include_trace: bool = False) -> str:
        """Render this result for terminal display."""
        if include_trace and self.trace is not None:
            return format_traced_response(self.final_answer, self.trace)

        return self.final_answer
