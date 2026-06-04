from pathlib import Path

import pytest

import mind.memory.indexing as indexing
from mind.core.config import load_config


def test_index_memory_embeds_and_stores_existing_memory(monkeypatch):
    config = load_config(Path("configs/config.toml"))
    calls = []

    monkeypatch.setattr(indexing, "get_memory_id", lambda config, text: 7)

    def fake_embed_text(config, text):
        calls.append(("embed", text))
        return [0.1, 0.2, 0.3]

    def fake_store_memory_embedding(config, memory_id, model, embedding):
        calls.append(("store", memory_id, model, embedding))
        return True

    monkeypatch.setattr(indexing, "embed_text", fake_embed_text)
    monkeypatch.setattr(indexing, "store_memory_embedding", fake_store_memory_embedding)

    indexed = indexing.index_memory(config, "User prefers concise answers.")

    assert indexed is True
    assert calls == [
        ("embed", "User prefers concise answers."),
        (
            "store",
            7,
            config.embeddings.model,
            [0.1, 0.2, 0.3],
        ),
    ]


def test_index_memory_returns_false_without_embedding_when_memory_is_missing(
    monkeypatch,
):
    config = load_config(Path("configs/config.toml"))

    monkeypatch.setattr(indexing, "get_memory_id", lambda config, text: None)

    def fail_embed_text(config, text):
        raise AssertionError("embed_text should not be called")

    monkeypatch.setattr(indexing, "embed_text", fail_embed_text)

    assert indexing.index_memory(config, "Missing memory.") is False


def test_index_memory_returns_storage_result(monkeypatch):
    config = load_config(Path("configs/config.toml"))

    monkeypatch.setattr(indexing, "get_memory_id", lambda config, text: 7)
    monkeypatch.setattr(indexing, "embed_text", lambda config, text: [0.1, 0.2])
    monkeypatch.setattr(
        indexing,
        "store_memory_embedding",
        lambda config, memory_id, model, embedding: False,
    )

    assert indexing.index_memory(config, "Memory that cannot be stored.") is False


def test_index_memory_propagates_embedding_failure(monkeypatch):
    config = load_config(Path("configs/config.toml"))

    monkeypatch.setattr(indexing, "get_memory_id", lambda config, text: 7)

    def broken_embed_text(config, text):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(indexing, "embed_text", broken_embed_text)

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        indexing.index_memory(config, "Existing memory.")
