from pathlib import Path

from mind.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.memory import add_memory
from mind.tools import run_tool


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
        context=ContextConfig(
            max_workspace_chars=12000,
        ),
    )


def test_run_tool_rejects_unknown_tool(tmp_path: Path):
    config = make_test_config(tmp_path)

    result = run_tool(config, "unknown.tool", {})

    assert "Error:" in result
    assert "Unknown tool" in result


def test_workspace_list_files_tool_lists_relative_files(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.list_files", {})

    assert "Workspace files:" in result
    assert "- notes.txt" in result


def test_workspace_read_file_tool_reads_workspace_file(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "notes.txt"})

    assert "FILE: notes.txt" in result
    assert "hello" in result


def test_workspace_read_file_tool_rejects_escape_path(tmp_path: Path):
    config = make_test_config(tmp_path)

    config.paths.workspace.mkdir(parents=True)

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secretsauce", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "../secret.txt"})

    assert "Access denied" in result
    assert "secretsauce" not in result


def test_memory_list_tool_lists_memories(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    result = run_tool(config, "memory.list", {})

    assert "Saved memories:" in result
    assert "- The project is named Mind." in result
