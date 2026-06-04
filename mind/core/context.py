from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mind.core.config import Config
from mind.memory import (
    format_memories_for_prompt,
    list_memories,
    retrieve_relevant_memories,
    update_memories_after_use,
)
from mind.workspace import read_workspace_file


TRUNCATION_MARKER = "\n[Workspace context truncated]"


@dataclass(frozen=True)
class ContextBundle:
    """Optional memory and workspace context prepared for a prompt."""

    memory_context: str | None
    workspace_context: str | None


def format_workspace_file_context(file_path: Path, contents: str) -> str:
    """Format a workspace file for inclusion in the model prompt."""
    return f"FILE: {file_path}\n---\n{contents}"


# Prefer query-specific semantic memory when embeddings are available.
# If embedding generation or vector lookup fails, fall back to recent memories
# so prompt construction remains reliable.
def build_memory_context(
    config: Config,
    query: str | None = None,
) -> str | None:
    """
    Build saved-memory context for a model prompt.
    """
    if not config.memory.inject_context:
        return None

    limit = config.memory.max_relevant_memories

    if query and query.strip() and config.embeddings.enabled:
        try:
            relevant_memories = retrieve_relevant_memories(
                config,
                query=query,
                limit=limit,
                min_similarity=config.memory.min_similarity,
            )
        except Exception:
            # Embeddings are an enhancement, not a hard dependency for chat.
            # If Ollama, the embedding model, or stored vectors fail, fall back.
            pass
        else:
            if relevant_memories:
                update_memories_after_use(config, relevant_memories)
                return format_memories_for_prompt(relevant_memories)

            # Retrieval succeeded, but no memories cleared the relevance
            # threshold. Do not replace them with unrelated recent memories.
            return None

    memories = list_memories(config)
    recent_memories = memories[-limit:]
    if recent_memories:
        update_memories_after_use(config, recent_memories)

    return format_memories_for_prompt(recent_memories)


def truncate_workspace_context(context: str, max_chars: int) -> str:
    """Truncate workspace context to fit the configured character budget."""
    if len(context) <= max_chars:
        return context

    available_chars = max_chars - len(TRUNCATION_MARKER)

    if available_chars <= 0:
        return TRUNCATION_MARKER.strip()

    return context[:available_chars].rstrip() + TRUNCATION_MARKER


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

    workspace_context = "\n\n".join(file_blocks)

    return truncate_workspace_context(
        workspace_context,
        config.context.max_workspace_chars,
    )


def build_context(
    config: Config,
    file_paths: list[Path] | None = None,
    query: str | None = None,
) -> ContextBundle:
    """Build optional memory and workspace context for a model prompt."""
    memory_context = build_memory_context(config, query=query)
    workspace_context = build_workspace_context(config, file_paths)

    return ContextBundle(
        memory_context=memory_context,
        workspace_context=workspace_context,
    )
