import sqlite3
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
from mind.memory import (
    add_memory,
    archive_memory,
    confirm_memory,
    delete_memory,
    format_memories_for_prompt,
    get_memory_embedding,
    init_db,
    list_memories_missing_embeddings,
    list_memory_embeddings,
    list_memory_records,
    list_memories,
    memory_exists,
    reject_memory,
    store_memory_embedding,
    update_memories_after_use,
)


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for memory-store tests."""
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


def test_init_db_creates_database_file(tmp_path: Path):
    """init_db should create the SQLite database file."""
    config = make_test_config(tmp_path)

    assert not config.paths.database.exists()

    init_db(config)

    assert config.paths.database.exists()


def test_list_memories_returns_empty_list_for_empty_database(tmp_path: Path):
    """An initialized database with no memories should return an empty list."""
    config = make_test_config(tmp_path)

    init_db(config)

    assert list_memories(config) == []


def test_add_memory_stores_memory(tmp_path: Path):
    """add_memory should store a memory that can be listed later."""
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    assert list_memories(config) == [(1, "The project is named Mind.")]


def test_init_db_creates_memory_metadata_columns(tmp_path: Path):
    """init_db should create the current memory metadata schema."""
    config = make_test_config(tmp_path)

    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        columns = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA table_info(memories)").fetchall()
        }

    assert columns == {
        "id": "INTEGER",
        "text": "TEXT",
        "normalized_text": "TEXT",
        "kind": "TEXT",
        "source": "TEXT",
        "status": "TEXT",
        "confidence": "REAL",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "last_used_at": "TEXT",
        "use_count": "INTEGER",
    }


def test_init_db_creates_memory_embeddings_table(tmp_path: Path):
    """init_db should create the semantic retrieval embedding table."""
    config = make_test_config(tmp_path)

    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        columns = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA table_info(memory_embeddings)").fetchall()
        }

    assert columns == {
        "memory_id": "INTEGER",
        "model": "TEXT",
        "embedding_json": "TEXT",
        "created_at": "TEXT",
    }


def test_add_memory_stores_default_metadata(tmp_path: Path):
    """Manual memories should be stored as confirmed high-confidence memories."""
    config = make_test_config(tmp_path)

    added = add_memory(config, "The project is named Mind.")

    with sqlite3.connect(config.paths.database) as conn:
        row = conn.execute(
            """
            SELECT text, normalized_text, kind, source, status, confidence, use_count
            FROM memories
            """
        ).fetchone()

    assert added is True
    assert row == (
        "The project is named Mind.",
        "the project is named mind",
        "general",
        "manual",
        "confirmed",
        1.0,
        0,
    )


def test_add_memory_stores_custom_metadata(tmp_path: Path):
    """Automatic extraction can store source and review metadata with a memory."""
    config = make_test_config(tmp_path)

    added = add_memory(
        config,
        "User wants Mind to stay local-first.",
        kind="general",
        source="chat_auto",
        status="auto_extracted",
        confidence=0.6,
    )

    with sqlite3.connect(config.paths.database) as conn:
        row = conn.execute(
            """
            SELECT kind, source, status, confidence
            FROM memories
            """
        ).fetchone()

    assert added is True
    assert row == ("general", "chat_auto", "auto_extracted", 0.6)


def test_list_memories_returns_memories_in_insertion_order(tmp_path: Path):
    """Memories should be returned oldest to newest with their database IDs."""
    config = make_test_config(tmp_path)

    add_memory(config, "First memory.")
    add_memory(config, "Second memory.")

    assert list_memories(config) == [
        (1, "First memory."),
        (2, "Second memory."),
    ]


def test_delete_memory_removes_existing_memory(tmp_path: Path):
    """delete_memory should remove a memory by database ID."""
    config = make_test_config(tmp_path)

    add_memory(config, "First memory.")
    add_memory(config, "Second memory.")

    deleted = delete_memory(config, 1)

    assert deleted is True
    assert list_memories(config) == [(2, "Second memory.")]


def test_delete_memory_returns_false_for_missing_id(tmp_path: Path):
    """delete_memory should return False when no memory exists with that ID."""
    config = make_test_config(tmp_path)

    add_memory(config, "Only memory.")

    deleted = delete_memory(config, 999)

    assert deleted is False
    assert list_memories(config) == [(1, "Only memory.")]


def test_format_memories_for_prompt_uses_memory_text_only():
    """Memory prompt formatting should include memory text, not raw database tuples."""
    context = format_memories_for_prompt(
        [
            (1, "First memory."),
            (2, "Second memory."),
        ]
    )

    assert context is not None
    assert "Saved memories about the user and project:" in context
    assert "- First memory." in context
    assert "- Second memory." in context
    assert "(1," not in context
    assert "(2," not in context


def test_memory_exists_returns_true_for_existing_memory(tmp_path: Path):
    """memory_exists should return True when the exact memory text exists."""
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    assert memory_exists(config, "The project is named Mind.") is True


def test_memory_exists_returns_false_for_missing_memory(tmp_path: Path):
    """memory_exists should return False when the exact memory text does not exist."""
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    assert memory_exists(config, "User prefers concise answers.") is False


def test_add_memory_deduplicates_normalized_text(tmp_path: Path):
    """Memory deduplication should ignore case, repeated whitespace, and punctuation."""
    config = make_test_config(tmp_path)

    first_added = add_memory(config, "The project is named Mind.")
    second_added = add_memory(config, "  the   PROJECT is named mind!  ")

    assert first_added is True
    assert second_added is False
    assert list_memories(config) == [(1, "The project is named Mind.")]
    assert memory_exists(config, "THE PROJECT IS NAMED MIND") is True


def test_store_memory_embedding_round_trips_vector(tmp_path: Path):
    """Stored memory embeddings should be read back as floats."""
    config = make_test_config(tmp_path)
    add_memory(config, "The project is named Mind.")

    stored = store_memory_embedding(config, 1, "nomic-embed-text", [1, 2.5, 3])

    assert stored is True
    assert get_memory_embedding(config, 1, "nomic-embed-text") == [1.0, 2.5, 3.0]


def test_store_memory_embedding_replaces_existing_model_vector(tmp_path: Path):
    """Regenerating a vector for the same memory/model should replace the old one."""
    config = make_test_config(tmp_path)
    add_memory(config, "The project is named Mind.")

    assert store_memory_embedding(config, 1, "nomic-embed-text", [1, 2]) is True
    assert store_memory_embedding(config, 1, "nomic-embed-text", [3, 4]) is True

    assert get_memory_embedding(config, 1, "nomic-embed-text") == [3.0, 4.0]


def test_store_memory_embedding_returns_false_for_missing_memory(tmp_path: Path):
    """Embeddings should not be stored without a source memory row."""
    config = make_test_config(tmp_path)

    stored = store_memory_embedding(config, 999, "nomic-embed-text", [1, 2])

    assert stored is False
    assert get_memory_embedding(config, 999, "nomic-embed-text") is None


def test_store_memory_embedding_rejects_invalid_vectors(tmp_path: Path):
    """Embedding storage should reject empty, boolean, and non-numeric vectors."""
    config = make_test_config(tmp_path)
    add_memory(config, "The project is named Mind.")

    with pytest.raises(ValueError, match="Embedding cannot be empty"):
        store_memory_embedding(config, 1, "nomic-embed-text", [])

    with pytest.raises(ValueError, match="Embedding values must be numeric"):
        store_memory_embedding(config, 1, "nomic-embed-text", [True])

    with pytest.raises(ValueError, match="Embedding values must be numeric"):
        store_memory_embedding(config, 1, "nomic-embed-text", ["bad"])


def test_list_memory_embeddings_returns_active_memories_with_vectors(tmp_path: Path):
    """Semantic retrieval should only list active memories with matching vectors."""
    config = make_test_config(tmp_path)
    add_memory(config, "Confirmed memory.")
    add_memory(
        config,
        "Auto memory.",
        source="chat_auto",
        status="auto_extracted",
        confidence=0.6,
    )
    add_memory(config, "Archived memory.", status="archived")
    store_memory_embedding(config, 1, "nomic-embed-text", [1, 0])
    store_memory_embedding(config, 2, "nomic-embed-text", [0, 1])
    store_memory_embedding(config, 3, "nomic-embed-text", [9, 9])
    store_memory_embedding(config, 1, "other-model", [5, 5])

    embeddings = list_memory_embeddings(config, "nomic-embed-text")

    assert embeddings == [
        (1, "Confirmed memory.", [1.0, 0.0]),
        (2, "Auto memory.", [0.0, 1.0]),
    ]


def test_list_memories_missing_embeddings_is_model_specific(tmp_path: Path):
    """A memory embedded for one model can still be missing for another model."""
    config = make_test_config(tmp_path)
    add_memory(config, "Embedded memory.")
    add_memory(config, "Missing memory.")
    add_memory(config, "Archived memory.", status="archived")
    store_memory_embedding(config, 1, "nomic-embed-text", [1, 0])

    assert list_memories_missing_embeddings(config, "nomic-embed-text") == [
        (2, "Missing memory.")
    ]
    assert list_memories_missing_embeddings(config, "other-model") == [
        (1, "Embedded memory."),
        (2, "Missing memory."),
    ]


def test_delete_memory_removes_stored_embeddings(tmp_path: Path):
    """Deleting a memory should delete its derived embedding rows."""
    config = make_test_config(tmp_path)
    add_memory(config, "The project is named Mind.")
    store_memory_embedding(config, 1, "nomic-embed-text", [1, 2])

    assert delete_memory(config, 1) is True

    assert get_memory_embedding(config, 1, "nomic-embed-text") is None


def test_list_memory_records_returns_review_metadata(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "Manual memory.")
    add_memory(
        config,
        "Auto memory.",
        source="chat_auto",
        status="auto_extracted",
        confidence=0.6,
    )

    records = list_memory_records(config)

    assert len(records) == 2
    assert records[0].text == "Manual memory."
    assert records[0].status == "confirmed"
    assert records[0].source == "manual"
    assert records[1].text == "Auto memory."
    assert records[1].status == "auto_extracted"
    assert records[1].source == "chat_auto"
    assert records[1].confidence == 0.6


def test_list_memory_records_filters_by_status(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "Confirmed memory.")
    add_memory(
        config,
        "Auto memory.",
        source="chat_auto",
        status="auto_extracted",
        confidence=0.6,
    )

    records = list_memory_records(config, status="auto_extracted")

    assert len(records) == 1
    assert records[0].text == "Auto memory."


def test_confirm_memory_updates_status(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(
        config,
        "Auto memory.",
        source="chat_auto",
        status="auto_extracted",
        confidence=0.6,
    )

    assert confirm_memory(config, 1) is True

    records = list_memory_records(config)
    assert records[0].status == "confirmed"


def test_reject_memory_excludes_memory_from_active_list(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "Keep me.")
    add_memory(config, "Reject me.")

    assert reject_memory(config, 2) is True

    assert list_memories(config) == [(1, "Keep me.")]

    rejected = list_memory_records(config, status="rejected")
    assert rejected[0].text == "Reject me."


def test_add_memory_rejects_invalid_status(tmp_path: Path):
    config = make_test_config(tmp_path)

    with pytest.raises(ValueError, match="Invalid memory status"):
        add_memory(config, "Bad memory.", status="banana")


def test_archive_memory_excludes_memory_from_active_list(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "Keep me.")
    add_memory(config, "Archive me.")

    assert archive_memory(config, 2) is True

    assert list_memories(config) == [(1, "Keep me.")]

    archived = list_memory_records(config, status="archived")
    assert len(archived) == 1
    assert archived[0].text == "Archive me."
    assert archived[0].status == "archived"


def test_mark_memories_used_updates_usage_metadata(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "Hello.")
    add_memory(config, "How are you.")
    
    # The "Hello." memory is used here
    memory = [list_memories(config)[0]]

    update_memories_after_use(config, memory)

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT use_count, last_used_at
            FROM memories
            """
        ).fetchall()
    
    assert rows[0][0] == 1
    assert rows[0][1] is not None
    assert rows[1][0] == 0
    assert rows[1][1] is None


def test_mark_memories_used_ignores_inactive_memories(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "plz don't update archived", status="archived")
    add_memory(config, "plz do not update rejected", status="rejected")
    add_memory(config, "plz update", status="confirmed")

    memories = list_memories(config)

    update_memories_after_use(config, memories)

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT use_count, last_used_at
            FROM memories
            WHERE status = 'confirmed'
            """
        ).fetchone()

    assert rows[0] == 1
    assert rows[1] is not None
    
    
