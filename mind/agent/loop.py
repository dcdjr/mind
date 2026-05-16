from __future__ import annotations

import json

from mind.core.config import Config
from mind.core.llm import complete
from mind.agent.prompts import build_agent_system_prompt
from mind.agent.protocol import extract_json_object
from mind.tools import run_tool


MAX_AGENT_STEPS = 3


def run_agent(config: Config, user_prompt: str, max_steps: int = MAX_AGENT_STEPS) -> str:
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

    for _ in range(max_steps):
        raw_response = complete(config, messages)
        parsed = extract_json_object(raw_response)

        if parsed is None:
            return raw_response

        response_type = parsed.get("type")

        if response_type == "final":
            answer = parsed.get("answer")

            if isinstance(answer, str) and answer.strip():
                return answer.strip()

            return "Error: Agent returned a final response without a valid answer."

        if response_type == "tool_call":
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})

            if not isinstance(tool_name, str):
                return "Error: Agent requested a tool without a valid tool name."

            if not isinstance(args, dict):
                return "Error: Agent requested a tool with invalid args."

            tool_result = run_tool(config, tool_name, args)

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

        return "Error: Agent returned an unknown response type."

    return "Error: Agent reached the maximum number of tool steps without a final answer."
