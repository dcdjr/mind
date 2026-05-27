import sqlite3
from pathlib import Path

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
    delete_memory,
    format_memories_for_prompt,
    init_db,
    list_memories,
    memory_exists,
)


def make_test_config(tmp_path: Path) -> Config:
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
            auto_memory=True,
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
