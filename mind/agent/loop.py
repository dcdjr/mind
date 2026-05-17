from __future__ import annotations

import json

from mind.core.config import Config
from mind.core.llm import complete
from mind.agent.prompts import build_agent_system_prompt
from mind.agent.protocol import extract_json_object
from mind.agent.trace import AgentTrace, format_traced_response
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
        parsed = extract_json_object(raw_response)

        if parsed is None:
            if agent_trace is not None:
                agent_trace.record_parse_failure(step_number, raw_response)

            return finish(raw_response)

        response_type = parsed.get("type")
        
        # Handle final answer
        if response_type == "final":
            answer = parsed.get("answer")

            if isinstance(answer, str) and answer.strip():
                if agent_trace is not None:
                    agent_trace.record_final(step_number, answer)

                return finish(answer.strip())

            message = "Error: Agent returned a final response without a valid answer."

            if agent_trace is not None:
                agent_trace.record_error(step_number, message)

            return finish(message)

        # Handle tool call
        if response_type == "tool_call":
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})

            if not isinstance(tool_name, str):
                message = "Error: Agent requested a tool without a valid tool name."

                if agent_trace is not None:
                    agent_trace.record_error(step_number, message)

                return finish(message)

            if not isinstance(args, dict):
                message = "Error: Agent requested a tool with invalid args."

                if agent_trace is not None:
                    agent_trace.record_error(step_number, message)

                return finish(message)

            tool_result = run_tool(config, tool_name, args)

            if agent_trace is not None:
                agent_trace.record_tool_call(step_number, tool_name, args, tool_result)

            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(parsed),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool result:\n"
                        f"Tool: {tool_name}\n"
                        f"Result:\n{tool_result}\n\n"
                        "Now either call another tool or give a final answer as strict JSON."
                    ),
                }
            )

            continue
        
        # Handle unknown response type
        message = "Error: Agent returned an unknown response type."

        if agent_trace is not None:
            agent_trace.record_error(step_number, message)

        return finish(message)
    
    # Handle reaching maximum number of tool steps
    message = "Error: Agent reached the maximum number of tool steps without a final answer."

    if agent_trace is not None:
        agent_trace.record_error(max_steps, message)

    return finish(message)
