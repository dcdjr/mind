from __future__ import annotations

from mind.agent import run_agent
from mind.core.config import Config
from mind.core.context import build_context
from mind.core.llm import complete
from mind.core.prompt import build_initial_chat_messages
from mind.memory import add_memory, extract_memories, memory_exists
from mind.runtime.confirmation import confirm_tool_run


def maybe_extract_and_store_memories(
    config: Config,
    user_input: str,
    response: str,
) -> None:
    """Extract and save durable memories from one chat turn."""
    if not config.memory.auto_memory:
        return

    try:
        memories = extract_memories(config, user_input, response)
    except Exception:
        return

    for memory in memories:
        if not memory_exists(config, memory):
            add_memory(
                config,
                memory,
                kind="general",
                source="chat_auto",
                status="auto_extracted",
                confidence=0.6,
            )


def _strip_trace_for_history(response: str) -> str:
    """
    Keep chat history clean when trace mode is enabled.

    Agent trace output is useful for the terminal, but it should not be fed back
    into later turns as if it were normal assistant conversation.
    """
    marker = "\n\nFinal answer:\n"

    if marker not in response:
        return response

    return response.rsplit(marker, maxsplit=1)[-1].strip()


def run_chat(
    config: Config,
    tools: bool = False,
    trace: bool = False,
) -> None:
    """Run an interactive terminal chat session with optional tool use."""
    context = build_context(config)

    messages = build_initial_chat_messages(
        config,
        memory_context=context.memory_context,
    )

    agent_history: list[dict[str, str]] = []

    if tools:
        print("Mind chat with tools. Type /exit or /quit to quit.")
    else:
        print("Mind chat. Type /exit or /quit to quit.")

    print()

    while True:
        try:
            user_input = input("mind> ")
        except (EOFError, KeyboardInterrupt):
            print()
            print("Exiting Mind chat.")
            break

        user_input = user_input.strip()

        if not user_input:
            continue

        if user_input in {"/exit", "/quit"}:
            print("Exiting Mind chat.")
            break

        if tools:
            response = run_agent(
                config,
                user_input,
                trace=trace,
                prior_messages=agent_history,
                confirm=confirm_tool_run,
            )
            history_response = _strip_trace_for_history(response)

            agent_history.append(
                {
                    "role": "user",
                    "content": user_input,
                }
            )
            agent_history.append(
                {
                    "role": "assistant",
                    "content": history_response,
                }
            )

            print()
            print(response)
            print()

            maybe_extract_and_store_memories(config, user_input, history_response)
            continue

        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        response = complete(config, messages)

        messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        print()
        print(response)
        print()

        maybe_extract_and_store_memories(config, user_input, response)


