from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from mind.tools.result import ToolResult


MAX_TRACE_OUTPUT_CHARS = 2_000


def _preview_text(text: str, max_chars: int = MAX_TRACE_OUTPUT_CHARS) -> str:
    """
    Return a terminal-friendly preview of a long text block.

    Tool outputs can be very large, especially when reading source files or
    repository dumps. The agent may still receive the full tool output in its
    model context, but the human trace should stay readable.
    """
    if len(text) <= max_chars:
        return text

    preview = text[:max_chars].rstrip()
    omitted = len(text) - len(preview)

    return (
        f"{preview}\n"
        f"[Trace output truncated: {omitted} characters omitted]"
    )


@dataclass
class AgentTrace:
    """Collect human-readable trace entries for one agent run."""

    entries: list[str] = field(default_factory=list)

    def record_tool_call(
        self,
        step_number: int,
        tool_name: str,
        args: dict[str, Any],
        result: ToolResult,
    ) -> None:
        formatted_args = json.dumps(args, sort_keys=True)
        output_preview = _preview_text(result.output)

        lines = [
            f"Step {step_number}",
            "Action: tool_call",
            f"Tool: {tool_name}",
            f"Args: {formatted_args}",
            f"Success: {'yes' if result.success else 'no'}",
            "Result:",
            output_preview,
        ]

        if result.error:
            lines.extend(
                [
                    "Error:",
                    result.error,
                ]
            )

        self.entries.append("\n".join(lines))

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
                    "Raw model response preview:",
                    _preview_text(raw_response),
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
