from pathlib import Path

import mind.memory.backfill as backfill
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


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for memory-backfill tests."""
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


def test_backfill_embeddings_embeds_all_missing_memories(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)
    stored_calls = []

    monkeypatch.setattr(
        backfill,
        "list_memories_missing_embeddings",
        lambda config, model: [
            (1, "First memory."),
            (2, "Second memory."),
        ],
    )

    monkeypatch.setattr(
        backfill,
        "embed_text",
        lambda config, text: [0.1, 0.2, 0.3],
    )

    def fake_store_memory_embedding(config, memory_id, model, embedding):
        stored_calls.append((memory_id, model, embedding))
        return True

    monkeypatch.setattr(
        backfill,
        "store_memory_embedding",
        fake_store_memory_embedding,
    )

    result = backfill.backfill_embeddings(config)

    assert result.model == "nomic-embed-text"
    assert result.total_missing == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.errors == []

    assert stored_calls == [
        (1, "nomic-embed-text", [0.1, 0.2, 0.3]),
        (2, "nomic-embed-text", [0.1, 0.2, 0.3]),
    ]


def test_backfill_embeddings_continues_after_embedding_failure(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)
    stored_calls = []

    monkeypatch.setattr(
        backfill,
        "list_memories_missing_embeddings",
        lambda config, model: [
            (1, "Good memory."),
            (2, "Bad memory."),
            (3, "Another good memory."),
        ],
    )

    def fake_embed_text(config, text):
        if text == "Bad memory.":
            raise RuntimeError("embedding provider exploded")

        return [0.4, 0.5, 0.6]

    def fake_store_memory_embedding(config, memory_id, model, embedding):
        stored_calls.append(memory_id)
        return True

    monkeypatch.setattr(backfill, "embed_text", fake_embed_text)
    monkeypatch.setattr(
        backfill,
        "store_memory_embedding",
        fake_store_memory_embedding,
    )

    result = backfill.backfill_embeddings(config)

    assert result.total_missing == 3
    assert result.succeeded == 2
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].memory_id == 2
    assert "RuntimeError" in result.errors[0].message
    assert "embedding provider exploded" in result.errors[0].message

    assert stored_calls == [1, 3]


def test_backfill_embeddings_records_storage_failure(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        backfill,
        "list_memories_missing_embeddings",
        lambda config, model: [
            (1, "Memory that cannot be stored."),
        ],
    )

    monkeypatch.setattr(
        backfill,
        "embed_text",
        lambda config, text: [0.1, 0.2, 0.3],
    )

    monkeypatch.setattr(
        backfill,
        "store_memory_embedding",
        lambda config, memory_id, model, embedding: False,
    )

    result = backfill.backfill_embeddings(config)

    assert result.total_missing == 1
    assert result.succeeded == 0
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].memory_id == 1
    assert "could not be stored" in result.errors[0].message


def test_backfill_embeddings_handles_no_missing_memories(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        backfill,
        "list_memories_missing_embeddings",
        lambda config, model: [],
    )

    result = backfill.backfill_embeddings(config)

    assert result.model == "nomic-embed-text"
    assert result.total_missing == 0
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.errors == []
