from __future__ import annotations

from mind.agent import run_agent
from mind.core.config import Config
from mind.core.context import build_context
from mind.core.llm import complete
from mind.core.prompt import build_initial_chat_messages, build_system_prompt
from mind.memory import add_memory, extract_memories, index_memory
from mind.runtime.confirmation import confirm_tool_run


def _refresh_chat_system_message(
    config: Config,
    messages: list[dict[str, str]],
    user_input: str,
) -> None:
    """
    Refresh the first system message with memory context relevant to this turn.

    Chat history stays intact, but the memory block changes based on the latest
    user input instead of being frozen when the chat session starts.
    """
    context = build_context(config, query=user_input)

    messages[0] = {
        "role": "system",
        "content": build_system_prompt(
            config,
            memory_context=context.memory_context,
        ),
    }


def maybe_extract_and_store_memories(
    config: Config,
    user_input: str,
    response: str,
) -> None:
    """Extract and save durable memories from one chat turn."""
    if not config.memory.auto_extract:
        return

    try:
        memories = extract_memories(config, user_input, response)
    except Exception:
        # Memory extraction is best-effort; chat should continue even if the
        # extractor model is unavailable or returns something unexpected.
        return

    for memory in memories:
        added = add_memory(
            config,
            memory,
            kind="general",
            source="chat_auto",
            status="auto_extracted",
            confidence=0.6,
        )

        if not added or not config.embeddings.enabled:
            continue

        try:
            index_memory(config, memory)
        except Exception:
            # Indexing is derived, recoverable data. Never break chat because
            # embedding generation or storage failed.
            continue


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
    model: str | None = None,
) -> None:
    """Run an interactive terminal chat session with optional tool use."""
    messages = build_initial_chat_messages(config)

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
            if model:
                response = run_agent(
                    config,
                    user_input,
                    trace=trace,
                    prior_messages=agent_history,
                    confirm=confirm_tool_run,
                    model=model,
                )
            else:
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

        _refresh_chat_system_message(config, messages, user_input)

        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        if model:
            response = complete(config, messages, model=model)
        else:
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
