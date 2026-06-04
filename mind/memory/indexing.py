from __future__ import annotations

from mind.core.config import Config
from mind.core.embeddings import embed_text
from mind.memory.store import (
    get_memory_id,
    store_memory_embedding,
)


def index_memory(config: Config, text: str) -> bool:
    """Generate and store an embedding for one existing memory."""
    memory_id = get_memory_id(config, text)

    if memory_id is None:
        return False

    embedding = embed_text(config, text)

    return store_memory_embedding(config, memory_id, config.embeddings.model, embedding)
