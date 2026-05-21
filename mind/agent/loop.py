from __future__ import annotations

import json
from collections.abc import Callable

from mind.agent.prompts import build_agent_system_prompt
from mind.agent.protocol import (
    FinalAnswer,
    InvalidAgentResponse,
    ToolCall,
    parse_agent_action,
)
from mind.agent.trace import AgentTrace, format_traced_response
from mind.core.config import Config
from mind.core.llm import complete
from mind.tools import ToolSpec, run_tool


MAX_AGENT_STEPS = 5

PROTOCOL_REPAIR_MESSAGE = (
    "Your previous response did not follow Mind's agent protocol. "
    "Return strict JSON only. "
    "Use either a tool call object or a final answer object. "
    "Do not include markdown, explanation, or extra text."
)


def run_agent(
    config: Config,
    user_prompt: str,
    max_steps: int = MAX_AGENT_STEPS,
    trace: bool = False,
    prior_messages: list[dict[str, str]] | None = None,
    confirm: Callable[[ToolSpec], bool] | None = None,
) -> str:
    """Run a bounded agent loop with optional prior conversation context."""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": build_agent_system_prompt(config),
        },
    ]

    if prior_messages:
        messages.extend(prior_messages)

    messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    agent_trace = AgentTrace() if trace else None

    repair_attempted = False
    tool_steps = 0
    step_number = 1

    def finish(answer: str) -> str:
        if agent_trace is None:
            return answer

        return format_traced_response(answer, agent_trace)

    while tool_steps < max_steps:
        try:
            raw_response = complete(config, messages)
        except Exception as error:
            message = f"Error: Agent model call failed: {type(error).__name__}: {error}."

            if agent_trace is not None:
                agent_trace.record_error(step_number, message)

            return finish(message)

        action = parse_agent_action(raw_response)

        if isinstance(action, InvalidAgentResponse):
            if agent_trace is not None:
                agent_trace.record_parse_failure(step_number, action.raw_output)

            if not repair_attempted:
                repair_attempted = True

                messages.append(
                    {
                        "role": "assistant",
                        "content": raw_response,
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"{PROTOCOL_REPAIR_MESSAGE}\n\n"
                            f"Protocol error: {action.message}"
                        ),
                    }
                )

                step_number += 1
                continue

            if agent_trace is not None:
                agent_trace.record_error(step_number, action.message)

            return finish(action.message)

        if isinstance(action, FinalAnswer):
            if agent_trace is not None:
                agent_trace.record_final(step_number, action.answer)

            return finish(action.answer)

        if isinstance(action, ToolCall):
            tool_steps += 1

            tool_result = run_tool(config, action.tool, action.args, confirm=confirm)

            if agent_trace is not None:
                agent_trace.record_tool_call(
                    step_number,
                    action.tool,
                    action.args,
                    tool_result,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "type": "tool_call",
                            "tool": action.tool,
                            "args": action.args,
                        }
                    ),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool result:\n"
                        f"Tool: {action.tool}\n"
                        f"Success: {'yes' if tool_result.success else 'no'}\n"
                        f"Result:\n{tool_result.output}\n\n"
                        "Now either call another tool or give a final answer as strict JSON."
                    ),
                }
            )

            step_number += 1
            continue

    message = "Error: Agent reached the maximum number of tool steps without a final answer."

    if agent_trace is not None:
        agent_trace.record_error(step_number, message)

    return finish(message)
