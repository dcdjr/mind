from __future__ import annotations

import json

from mind.config import Config
from mind.llm import complete


MAX_MEMORY_LENGTH = 300


def build_memory_extraction_messages(
    user_message: str,
    assistant_response: str,
) -> list[dict[str, str]]:
    """Build the message list used to extract durable memories from one chat turn."""
    system_prompt = (
        "You are a memory extraction system for a local-first personal assistant.\n\n"
        "Your job is to extract durable facts that may be useful in future conversations.\n\n"
        "RETURN STRICT JSON ONLY. NO EXCEPTIONS.\n"
        "Return a JSON array of strings.\n"
        "If nothing should be remembered, return [].\n\n"
        "Store only stable, useful facts such as:\n"
        "- user preferences\n"
        "- project names\n"
        "- project goals\n"
        "- recurring constraints\n"
        "- long-term plans\n"
        "- important technical decisions\n\n"
        "Do not store:\n"
        "- temporary moods or emotions\n"
        "- random one-off facts\n"
        "- sensitive personal details\n"
        "- assistant opinions\n"
        "- generic information\n"
        "- facts only relevant to this single turn\n"
    )

    user_prompt = (
        "Analyze this conversation turn and extract memories if appropriate.\n\n"
        "USER MESSAGE:\n"
        f"{user_message}\n\n"
        "ASSISTANT RESPONSE:\n"
        f"{assistant_response}\n"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_array(raw_output: str) -> str | None:
    """Extract the first JSON array from model output."""
    start = raw_output.find("[")
    end = raw_output.rfind("]")

    if start == -1 or end == -1 or end < start:
        return None

    return raw_output[start : end + 1]


def parse_extracted_memories(raw_output: str) -> list[str]:
    """Parse and validate the model's memory extraction output."""
    json_text = extract_json_array(raw_output.strip())

    if json_text is None:
        return []

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    memories = []

    for item in parsed:
        if not isinstance(item, str):
            continue

        memory = item.strip()

        if not memory:
            continue

        if len(memory) > MAX_MEMORY_LENGTH:
            memory = memory[:MAX_MEMORY_LENGTH].rstrip()

        memories.append(memory)

    return memories


def extract_memories(
    config: Config,
    user_message: str,
    assistant_response: str,
) -> list[str]:
    """Extract durable memories from one user/assistant turn."""
    messages = build_memory_extraction_messages(user_message, assistant_response)
    raw_output = complete(config, messages)
    parsed_output = parse_extracted_memories(raw_output)

    return parsed_output
