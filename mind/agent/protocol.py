from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mind.core.json_utils import extract_json_object


@dataclass(frozen=True)
class ToolCall:
    """A validated request from the model to run one tool."""

    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class FinalAnswer:
    """A validated final answer from the model."""

    answer: str


@dataclass(frozen=True)
class InvalidAgentResponse:
    """A model response that does not match Mind's agent protocol"""

    message: str
    raw_output: str


AgentAction = ToolCall | FinalAnswer | InvalidAgentResponse


def parse_agent_action(raw_output: str) -> AgentAction:
    """
    Parse and validate one model response according to Mind's agent protocol.

    The model is untrusted. This function is the boundary between raw model text
    and structured Python actions that the agent loop can execute.
    """
    parsed = extract_json_object(raw_output)

    if parsed is None:
        return InvalidAgentResponse(
            message="Error: Agent response did not contain a valid JSON object.",
            raw_output=raw_output,
        )

    response_type = parsed.get("type")

    if response_type == "final":
        return _parse_final_answer(parsed, raw_output)

    if response_type == "tool_call":
        return _parse_tool_call(parsed, raw_output)

    if response_type is None:
        return InvalidAgentResponse(
            message="Error: Agent response is missing required field 'type'.",
            raw_output=raw_output,
        )

    return InvalidAgentResponse(
        message=f"Error: Agent returned an unknown response type: {response_type!r}.",
        raw_output=raw_output,
    )


def _parse_final_answer(
    parsed: dict[str, Any],
    raw_output: str,
) -> FinalAnswer | InvalidAgentResponse:
    """Validate a final-answer response."""
    answer = parsed.get("answer")

    if not isinstance(answer, str) or not answer.strip():
        return InvalidAgentResponse(
            message="Error: Agent returned a final response without a valid answer.",
            raw_output=raw_output,
        )

    return FinalAnswer(answer=answer.strip())


def _parse_tool_call(parsed: dict[str, Any], raw_output: str) -> ToolCall | InvalidAgentResponse:
    """Validate a tool-call response."""
    tool = parsed.get("tool")
    args = parsed.get("args", {})

    if not isinstance(tool, str) or not tool.strip():
        return InvalidAgentResponse(
            message="Error: agent requested a tool without a valid tool name.",
            raw_output=raw_output,
        )

    if not isinstance(args, dict):
        return InvalidAgentResponse(
            message="Error: Agent requested a tool with invalid args.",
            raw_output=raw_output,
        )

    return ToolCall(tool=tool.strip(), args=args)
