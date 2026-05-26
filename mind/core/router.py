from __future__ import annotations

from ollama import Client

from mind.core.config import Config
from mind.core.json_utils import extract_json_object


VALID_ROUTE_LABELS = {"default", "cloud"}


def complete_small(config: Config, messages: list[dict[str, str]]) -> str:
    """Send a prepared message list to the small local model."""
    client = Client(host=config.model.base_url)

    response = client.chat(
        model=config.model.small,
        messages=messages,
    )

    return response["message"]["content"]


def build_router_system_prompt() -> str:
    return (
        """
        You are a high-speed, accurate incoming request router for an LLM gateway.
        Analyze the user's prompt and categorize it into exactly one of three destinations:

        1. "cloud": Use this if the prompt requires advanced reasoning, deep mathematical logic, 
           real-time search engine data, complex code debugging, or massive analytical processing.
           NEVER USE CLOUD IF THE PROMPT CONTAINS SENSITIVE OR PRIVATE DATA.
        2. "default": Use this for everything else, including general conversation, basic tasks, 
           private data parsing, simple summaries, or routine scripts.

        JSON format output example: {"model": "default"}

        CRITICAL: You must output a valid JSON object like above. Do not include markdown formatting or extra text.
        STRICT JSON.
        """
    )


def build_router_messages(user_prompt: str) -> list[dict[str, str]]:
    """Build the message list sent to the small model to route responsiblity based on prompt."""
    return [
        {
            "role": "system",
            "content": build_router_system_prompt(),
        },
        {
            "role": "user",
            "content": user_prompt,
        }
    ]


def resolve_model(config: Config, route_label: str) -> str:
    if route_label == "cloud" and config.model.cloud:
        return config.model.cloud

    return config.model.default


def route(config: Config, user_prompt: str) -> str:
    """Route a user prompt to a known model route label."""
    try:
        messages = build_router_messages(user_prompt)
        raw_response = complete_small(config, messages)
    except Exception:
        return "default"

    parsed = extract_json_object(raw_response)

    if not isinstance(parsed, dict):
        return "default"

    route_label = parsed.get("model")

    if not isinstance(route_label, str):
        return "default"

    route_label = route_label.strip().lower()

    if route_label not in VALID_ROUTE_LABELS:
        return "default"

    return route_label
