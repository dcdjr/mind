from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mind.config import Config
from mind.memory import format_memories_for_prompt, list_memories
from mind.workspace import read_workspace_file


@dataclass(frozen=True)
class ContextBundle:
    memory_context: str | None
    workspace_context: str | None


def format_workspace_file_context(file_path: Path, contents: str) -> str:
    """Format a workspace file for inclusion in the model prompt."""
    return f"FILE: {file_path}\n---\n{contents}"


def build_memory_context(config: Config) -> str | None:
    """Load recent saved memories and format them for the prompt."""
    if not config.memory.auto_memory:
        return None

    memories = list_memories(config)
    recent_memories = memories[-config.memory.max_relevant_memories:]

    return format_memories_for_prompt(recent_memories)


def build_workspace_context(
    config: Config,
    file_paths: list[Path] | None = None,
) -> str | None:
    """Read and format one or more workspace files for the model prompt."""
    if not file_paths:
        return None

    file_blocks = []

    for file_path in file_paths:
        contents = read_workspace_file(config, file_path)
        file_blocks.append(format_workspace_file_context(file_path, contents))

    return "\n\n".join(file_blocks)


def build_context(
    config: Config,
    file_paths: list[Path] | None = None,
) -> ContextBundle:
    """Build all optional context that should be included in the model prompt."""
    memory_context = build_memory_context(config)
    workspace_context = build_workspace_context(config, file_paths)

    return ContextBundle(
        memory_context=memory_context,
        workspace_context=workspace_context,
    )
