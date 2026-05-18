from __future__ import annotations

import json

from mind.agent.prompts import build_agent_system_prompt
from mind.agent.protocol import (
    FinalAnswer,
    InvalidAgentResponse,
    ToolCall,
    extract_json_object,
    parse_agent_action,
)
from mind.agent.trace import AgentTrace, format_traced_response
from mind.core.config import Config
from mind.core.llm import complete
from mind.tools import run_tool


MAX_AGENT_STEPS = 3


def run_agent(
    config: Config,
    user_prompt: str,
    max_steps: int = MAX_AGENT_STEPS,
    trace: bool = False,
) -> str:
    """Run a small bounded agent loop with safe internal tools."""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": build_agent_system_prompt(config),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    agent_trace = AgentTrace() if trace else None

    def finish(answer: str) -> str:
        if agent_trace is None:
            return answer

        return format_traced_response(answer, agent_trace)

    for step_number in range(1, max_steps + 1):
        raw_response = complete(config, messages)
        action = parse_agent_action(raw_response)

        if isinstance(action, InvalidAgentResponse):
            if agent_trace is not None:
                agent_trace.record_parse_failure(step_number, action.raw_output)
                agent_trace.record_error(step_number, action.message)

            return finish(action.message)

        if isinstance(action, FinalAnswer):
            if agent_trace is not None:
                agent_trace.record_final(step_number, action.answer)

            return finish(action.answer)

        if isinstance(action, ToolCall):
            tool_result = run_tool(config, action.tool, action.args)

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

            continue

    message = "Error: Agent reached the maximum number of tool steps without a final answer."

    if agent_trace is not None:
        agent_trace.record_error(max_steps, message)

    return finish(message)
