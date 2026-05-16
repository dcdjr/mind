from __future__ import annotations

import json
from typing import Any

from mind.core.config import Config
from mind.core.llm import complete
from mind.tools import format_available_tools, run_tool


MAX_AGENT_STEPS = 3


def extract_json_object(raw_output: str) -> dict[str, Any] | None:
    """Extract and parse the first JSON object from model output."""
    start = raw_output.find("{")
    end = raw_output.rfind("}")

    if start == -1 or end == -1 or end < start:
        return None

    json_text = raw_output[start : end + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def build_agent_system_prompt(config: Config) -> str:
    """Build the system prompt for Mind's simple tool-using agent mode."""
    return (
        f"You are {config.assistant.name}, a local-first personal AI assistant.\n\n"
        "You can either call one safe internal tool or give a final answer.\n"
        "RETURN STRICT JSON ONLY. NO MARKDOWN. NO EXTRA COMMENTARY.\n\n"
        "Available tools:\n"
        f"{format_available_tools()}\n\n"
        "Tool call format (THIS IS JUST AN EXAMPLE):\n"
        '{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "notes.txt"}}\n\n'
        "Final answer format:\n"
        '{"type": "final", "answer": "Your answer here."}\n\n'
        "Rules:\n"
        "- Use tools when you need workspace or memory information.\n"
        "- Do not invent file contents or memories.\n"
        "- If a tool returns an error, explain the error in the final answer.\n"
        "- Prefer a final answer when enough information is available."
    )


def run_agent(config: Config, user_prompt: str, max_steps: int = MAX_AGENT_STEPS) -> str:
    """Run a small bounded agent loop with safe internal tools"""
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
