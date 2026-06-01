from __future__ import annotations

import math

from mind.core.config import Config
from mind.core.embeddings import embed_text
from mind.memory.store import list_memory_embeddings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Return the cosine similarity between two embedding vectors.

    Cosine similarity measures whether two vectors point in the same direction.
    For semantic retrieval, this is useful because embedding direction roughly
    represents meaning.
    """
    if not a or not b:
        raise ValueError("Cannot compare empty embedding vectors.")

    if len(a) != len(b):
        raise ValueError("Embedding vectors must have the same length.")

    # Cosine similarity is dot(a, b) divided by both vector magnitudes. It
    # ignores vector length and keeps ranking focused on direction/meaning.
    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x**2 for x in a))
    norm_b = math.sqrt(sum(x**2 for x in b))

    if not norm_a or not norm_b:
        raise ValueError("Cannot compare zero-magnitude embedding vectors.")

    return dot / (norm_a * norm_b)


def rank_memory_embeddings(
    query_embedding: list[float],
    memories: list[tuple[int, str, list[float]]],
    limit: int,
) -> list[tuple[int, str, float]]:
    """Rank stored memory embeddings by similarity to the query embedding."""
    if limit <= 0:
        return []

    scored_memories: list[tuple[int, str, float]] = []

    for memory_id, memory_text, memory_embedding in memories:
        # Invalid stored vectors should fail loudly here; retrieval cannot rank
        # safely if vector dimensions or magnitudes are corrupt.
        score = cosine_similarity(query_embedding, memory_embedding)
        scored_memories.append((memory_id, memory_text, score))

    # Keep the score out of the public retrieval return shape, but use it here
    # to order most relevant memories first.
    return sorted(
        scored_memories,
        key=lambda memory: memory[2],
        reverse=True,
    )[:limit]


def retrieve_relevant_memories(
    config: Config,
    query: str,
    limit: int,
) -> list[tuple[int, str]]:
    """
    Retrieve the most semantically relevant memories for a query.

    This function is the public retrieval pipeline:
        query text -> query embedding -> compare to stored memory embeddings
        -> return the highest-ranked memories
    """
    if limit <= 0:
        return []

    # Embed the query with the same model used to store memory vectors. Mixing
    # embedding models would make cosine scores meaningless.
    query_embedding = embed_text(config, query)

    memories = list_memory_embeddings(
        config,
        config.embeddings.model,
    )

    ranked_memories = rank_memory_embeddings(
        query_embedding,
        memories,
        limit,
    )

    return [
        (memory_id, memory_text)
        for memory_id, memory_text, _score in ranked_memories
    ]
