from __future__ import annotations

from ollama import Client

from mind.core.config import Config
from mind.core.prompt import build_messages, build_system_prompt
from mind.core.router import route, resolve_model
from mind.core.uncensored_prompt import build_uncensored_system_prompt


def complete(
    config: Config,
    messages: list[dict[str, str]],
    model: str | None = None
) -> str:
    """Send a prepared message list to the configured local model."""
    client = Client(host=config.model.base_url)
    model = model or config.model.default

    response = client.chat(
        model=model,
        messages=messages,
    )

    return response["message"]["content"]


def ask(
    config: Config,
    prompt: str,
    workspace_context: str | None = None,
    memory_context: str | None = None,
    model: str | None = None,
    uncensored: bool = False,
) -> str:
    """
    Send a single prompt to the configured model.

    Prompts with local context stay on the default model for now.
    """

    if uncensored:
        system_prompt = (
            build_system_prompt(config, workspace_context, memory_context)
            + "\n\n"
            + build_uncensored_system_prompt()
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    else:
        messages = build_messages(config, prompt, workspace_context, memory_context)

    if model:
        return complete(config, messages, model=model)

    has_private_context = workspace_context is not None or memory_context is not None

    if has_private_context:
        # Context may include local files or memories, so do not route it to an
        # alternate/cloud model unless the caller explicitly selected one.
        return complete(config, messages, model=config.model.default)

    route_label = route(config, prompt)
    selected_model = resolve_model(config, route_label)

    return complete(config, messages, model=selected_model)
