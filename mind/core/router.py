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
    """Build the system prompt used by the small model router."""
    return (
        "You are a high-speed, accurate incoming request router for an LLM "
        "gateway.\n"
        "Analyze the user's prompt and categorize it into exactly one of two "
        "destinations:\n\n"
        '1. "cloud": Use this if the prompt requires advanced reasoning, deep '
        "mathematical logic,\n"
        "   real-time search engine data, complex code debugging, or massive "
        "analytical processing.\n"
        "   NEVER USE CLOUD IF THE PROMPT CONTAINS SENSITIVE OR PRIVATE DATA.\n"
        '2. "default": Use this for everything else, including general '
        "conversation, basic tasks,\n"
        "   private data parsing, simple summaries, or routine scripts.\n\n"
        'JSON output shape: {"model": "<route_label>"}\n'
        'Allowed route labels: "default" or "cloud".\n\n'
        "CRITICAL: You must output a valid JSON object like above. Do not "
        "include markdown formatting or extra text.\n"
        "STRICT JSON."
    )


def build_router_messages(user_prompt: str) -> list[dict[str, str]]:
    """Build messages sent to the small model for prompt routing."""
    return [
        {
            "role": "system",
            "content": build_router_system_prompt(),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def resolve_model(config: Config, route_label: str) -> str:
    """Resolve a known route label to a configured model name."""
    if route_label == "cloud" and config.model.cloud:
        return config.model.cloud

    return config.model.default


def route(config: Config, user_prompt: str) -> str:
    """Route a user prompt to a known model route label."""
    try:
        messages = build_router_messages(user_prompt)
        raw_response = complete_small(config, messages)
    except Exception:
        # Routing is an optimization. If the router is unavailable or confused,
        # stay on the default local model instead of failing the user request.
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
