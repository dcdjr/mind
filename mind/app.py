from __future__ import annotations

from pathlib import Path

from mind.config import Config
from mind.context import build_context
from mind.llm import ask


def ask_once(
    config: Config,
    prompt: str,
    file_paths: list[Path] | None = None,
) -> str:
    """Run one prompt through Mind with optional workspace and memory context."""
    context = build_context(config, file_paths)

    return ask(
        config,
        prompt,
        workspace_context=context.workspace_context,
        memory_context=context.memory_context,
    )
