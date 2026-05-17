from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentTrace:
    """Collect human-readable trace entries for one agent run."""

    entries: list[str] = field(default_factory=list)

    def record_tool_call(
        self,
        step_number: int,
        tool_name: str,
        args: dict[str, Any],
        result: str,
    ) -> None:
        formatted_args = json.dumps(args, sort_keys=True)

        self.entries.append(
            "\n".join(
                [
                    f"Step {step_number}",
                    "Action: tool_call",
                    f"Tool: {tool_name}",
                    f"Args: {formatted_args}",
                    "Result:",
                    result,
                ]
            )
        )

    def record_final(self, step_number: int, answer: str) -> None:
        self.entries.append(
            "\n".join(
                [
                    f"Step {step_number}",
                    "Action: final",
                    f"Answer: {answer}",
                ]
            )
        )

    def record_error(self, step_number: int, message: str) -> None:
        self.entries.append(
            "\n".join(
                [
                    f"Step {step_number}",
                    "Action: error",
                    f"Error: {message}",
                ]
            )
        )

    def record_parse_failure(self, step_number: int, raw_response: str) -> None:
        self.entries.append(
            "\n".join(
                [
                    f"Step {step_number}",
                    "Action: parse_failure",
                    "Raw model response:",
                    raw_response,
                ]
            )
        )

    def render(self) -> str:
        if not self.entries:
            return "Agent trace: no steps recorded."

        return "Agent trace:\n\n" + "\n\n".join(self.entries)


def format_traced_response(answer: str, trace: AgentTrace) -> str:
    """Combine trace output with the final user-facing answer."""
    return f"{trace.render()}\n\nFinal answer:\n{answer}"
