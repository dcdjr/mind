from pathlib import Path


from mind.config import (
    AssistantConfig,
    Config,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.memory import add_memory, init_db, list_memories


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

    assert list_memories(config) == ["The project is named Mind."]


def test_list_memories_returns_memories_in_insertion_order(tmp_path: Path):
    """Memories should be returned oldest to newest."""
    config = make_test_config(tmp_path)

    add_memory(config, "First memory.")
    add_memory(config, "Second memory.")

    assert list_memories(config) == [
        "First memory.",
        "Second memory.",
    ]
