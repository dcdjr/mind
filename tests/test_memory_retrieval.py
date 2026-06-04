from pathlib import Path

import pytest

from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    EmbeddingConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ToolConfig,
)
import mind.memory.retrieval as retrieval


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for memory-retrieval tests."""
    return Config(
        assistant=AssistantConfig(
            name="Mind",
            description="Test assistant",
        ),
        paths=PathConfig(
            workspace=tmp_path / "workspace",
            database=tmp_path / "data" / "mind.db",
        ),
        model=ModelConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            default="gemma4:e4b",
        ),
        memory=MemoryConfig(
            auto_extract=True,
            inject_context=True,
            max_relevant_memories=8,
        ),
        embeddings=EmbeddingConfig(
            provider="ollama",
            model="nomic-embed-text",
            enabled=True,
        ),
        context=ContextConfig(
            max_workspace_chars=12000,
        ),
        tools=ToolConfig(
            allow_external_read=True,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        ),
    )


def test_cosine_similarity_returns_expected_scores():
    """Cosine similarity should handle identical, orthogonal, and opposite vectors."""
    assert retrieval.cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert retrieval.cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert retrieval.cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_cosine_similarity_rejects_invalid_vectors():
    """Similarity should fail for vectors that cannot produce a meaningful score."""
    with pytest.raises(ValueError, match="empty embedding vectors"):
        retrieval.cosine_similarity([], [1])

    with pytest.raises(ValueError, match="same length"):
        retrieval.cosine_similarity([1], [1, 2])

    with pytest.raises(ValueError, match="zero-magnitude"):
        retrieval.cosine_similarity([0, 0], [1, 2])


def test_rank_memory_embeddings_orders_by_similarity_and_applies_limit():
    """Ranking should return highest-score memories first and keep the score."""
    memories = [
        (1, "orthogonal", [0, 1]),
        (2, "best match", [1, 0]),
        (3, "opposite", [-1, 0]),
    ]

    ranked = retrieval.rank_memory_embeddings([1, 0], memories, limit=2)

    assert ranked == [
        (2, "best match", pytest.approx(1.0)),
        (1, "orthogonal", pytest.approx(0.0)),
    ]


def test_rank_memory_embeddings_returns_empty_list_for_non_positive_limit():
    memories = [(1, "memory", [1, 0])]

    assert retrieval.rank_memory_embeddings([1, 0], memories, limit=0) == []
    assert retrieval.rank_memory_embeddings([1, 0], memories, limit=-1) == []


def test_rank_memory_embeddings_surfaces_invalid_stored_vectors():
    """Corrupt stored vectors should not be silently ignored during retrieval."""
    memories = [(1, "bad vector", [0, 0])]

    with pytest.raises(ValueError, match="zero-magnitude"):
        retrieval.rank_memory_embeddings([1, 0], memories, limit=1)


def test_retrieve_relevant_memories_embeds_query_and_uses_configured_model(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)
    calls = []

    def fake_embed_text(received_config, query):
        calls.append(("embed", received_config, query))
        return [1, 0]

    def fake_list_memory_embeddings(received_config, model):
        calls.append(("list", received_config, model))
        return [
            (1, "less relevant", [0, 1]),
            (2, "most relevant", [1, 0]),
        ]

    monkeypatch.setattr(retrieval, "embed_text", fake_embed_text)
    monkeypatch.setattr(retrieval, "list_memory_embeddings", fake_list_memory_embeddings)

    memories = retrieval.retrieve_relevant_memories(config, "project name", limit=2)

    assert calls == [
        ("embed", config, "project name"),
        ("list", config, "nomic-embed-text"),
    ]
    assert memories == [
        (2, "most relevant"),
        (1, "less relevant"),
    ]


def test_retrieve_relevant_memories_respects_limit(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(retrieval, "embed_text", lambda config, query: [1, 0])
    monkeypatch.setattr(
        retrieval,
        "list_memory_embeddings",
        lambda config, model: [
            (1, "best", [1, 0]),
            (2, "second", [0.5, 0.5]),
        ],
    )

    assert retrieval.retrieve_relevant_memories(config, "query", limit=1) == [
        (1, "best")
    ]


def test_retrieve_relevant_memories_filters_below_minimum_similarity(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(retrieval, "embed_text", lambda config, query: [1, 0])
    monkeypatch.setattr(
        retrieval,
        "list_memory_embeddings",
        lambda config, model: [
            (1, "strong match", [1, 0]),
            (2, "weak match", [0, 1]),
            (3, "opposite match", [-1, 0]),
        ],
    )

    memories = retrieval.retrieve_relevant_memories(
        config,
        "query",
        limit=3,
        min_similarity=0.5,
    )

    assert memories == [(1, "strong match")]


def test_retrieve_relevant_memories_short_circuits_for_non_positive_limit(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)

    def fail_embed_text(config, query):
        raise AssertionError("embed_text should not be called")

    def fail_list_memory_embeddings(config, model):
        raise AssertionError("list_memory_embeddings should not be called")

    monkeypatch.setattr(retrieval, "embed_text", fail_embed_text)
    monkeypatch.setattr(retrieval, "list_memory_embeddings", fail_list_memory_embeddings)

    assert retrieval.retrieve_relevant_memories(config, "query", limit=0) == []
