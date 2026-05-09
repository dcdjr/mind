from __future__ import annotations

from ollama import Client

from mind.config import Config
from mind.prompt import build_messages


def complete(config: Config, messages: list[dict[str, str]]) -> str:
    """Send a prepared message list to the configured local model."""
    client = Client(host=config.model.base_url)

    response = client.chat(
        model=config.model.default,
        messages=messages,
    )

    return response["message"]["content"]


def ask(config: Config, prompt: str, workspace_context: str | None = None) -> str:
    """Send a single prompt to the configured local model."""
    messages = build_messages(config, prompt, workspace_context)
    return complete(config, messages)
