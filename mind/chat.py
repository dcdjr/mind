from __future__ import annotations

from mind.context import build_context
from mind.llm import complete
from mind.prompt import build_initial_chat_messages
from mind.memory import add_memory
from mind.memory_extractor import extract_memories
from mind.config import Config


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
        add_memory(config, memory)


def run_chat(config: Config) -> None:
    """Run an interactive terminal chat session with short-term message history."""
    context = build_context(config)

    messages = build_initial_chat_messages(
        config,
        memory_context=context.memory_context,
    )

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

