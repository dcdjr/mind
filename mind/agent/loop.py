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
from mind.core.context import build_context
from mind.core.llm import complete
from mind.tools import ToolSpec, run_tool


MAX_AGENT_STEPS = 10

PROTOCOL_REPAIR_MESSAGE = (
    "Your previous response was invalid for Mind's agent protocol.\n\n"
    "Continue the original user task using the information already gathered. "
    "Do not restart the task. Do not call unrelated tools. Do not copy placeholder "
    "tool names or placeholder arguments from these instructions.\n\n"
    "Return exactly one strict JSON object and nothing else.\n\n"
    "Valid response shapes:\n"
    "- Tool call: "
    '{"type": "tool_call", "tool": "<available_tool_name>", '
    '"args": {"<arg_name>": "<arg_value>"}}\n'
    "- Final answer: "
    '{"type": "final", "answer": "<final-answer-text>"}\n\n'
    "Tool-call rules:\n"
    "- Use only a tool name listed in the available tools section.\n"
    "- Use arguments that match that tool's Args description.\n"
    "- If a previous tool call succeeded, use its result instead of repeating work.\n"
    "- If a previous tool call failed, do not repeat the same tool call with the same args.\n"
    "- If enough information is already available, return a final answer.\n\n"
    "JSON rules:\n"
    "- Return one JSON object only.\n"
    "- Do not wrap the JSON in markdown code fences.\n"
    "- Do not include prose outside the JSON object.\n"
    "- Do not use raw multiline strings inside JSON values.\n"
    "- Escape newlines inside JSON strings as \\n.\n"
    "- Use either a tool_call object or a final answer object."
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
    context = build_context(config, query=user_prompt)

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": build_agent_system_prompt(
                config,
                memory_context=context.memory_context,
            ),
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

    failed_tool_calls: set[tuple[str, str]] = set()

    # repair_attempted is separate from tool_steps because a protocol repair is
    # a formatting retry, not a meaningful agent action toward the task.
    repair_attempted = False
    tool_steps = 0
    step_number = 1

    def finish(answer: str) -> str:
        """Attach trace output to an answer when tracing is enabled."""
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

                # Keep the bad assistant message in history so the model can
                # repair exactly the response that failed validation.
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

            tool_key = (action.tool, json.dumps(action.args, sort_keys=True))
            if tool_key in failed_tool_calls:
                return finish(
                    "Error: Agent repeated the same failing tool call instead of recovering."
                )

            # run_tool is the permission/confirmation boundary. The agent loop
            # never calls tool functions directly, even after protocol parsing.
            tool_result = run_tool(config, action.tool, action.args, confirm=confirm)

            if not tool_result.success:
                failed_tool_calls.add(tool_key)

            if agent_trace is not None:
                agent_trace.record_tool_call(
                    step_number,
                    action.tool,
                    action.args,
                    tool_result,
                )

            # Echo the validated tool call back as JSON so the transcript stays
            # aligned with the protocol the model is expected to continue.
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

            # step_number tracks every model-facing turn for trace readability;
            # tool_steps tracks only tool calls so the max_steps guard limits
            # actual side-effect opportunities.
            step_number += 1
            continue

    message = "Error: Agent reached the maximum number of tool steps without a final answer."

    if agent_trace is not None:
        agent_trace.record_error(step_number, message)

    return finish(message)
