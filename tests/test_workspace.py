from pathlib import Path

import pytest

from mind.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.workspace import ensure_workspace, list_workspace_files, read_workspace_file


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create an isolated config so workspace tests do not touch the real repo workspace."""
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


def test_ensure_workspace_creates_directory(test_config: Config):
    """ensure_workspace should create the workspace directory if it does not exist."""
    workspace = test_config.paths.workspace

    assert not workspace.exists()

    result = ensure_workspace(workspace)

    assert result == workspace
    assert workspace.exists()
    assert workspace.is_dir()


def test_list_workspace_files_returns_empty_list_for_empty_workspace(test_config: Config):
    """An empty workspace should return an empty list, not a user-facing message string."""
    files = list_workspace_files(test_config)

    assert files == []


def test_list_workspace_files_returns_relative_file_paths(test_config: Config):
    """Workspace listing should return file paths relative to the workspace root."""
    workspace = ensure_workspace(test_config.paths.workspace)
    nested_dir = workspace / "notes"
    nested_dir.mkdir()

    (workspace / "root.txt").write_text("root file", encoding="utf-8")
    (nested_dir / "nested.txt").write_text("nested file", encoding="utf-8")

    files = list_workspace_files(test_config)

    assert Path("root.txt") in files
    assert Path("notes/nested.txt") in files
    assert all(not file.is_absolute() for file in files)


def test_read_workspace_file_returns_file_contents(test_config: Config):
    """A valid file inside the workspace should be read successfully."""
    workspace = ensure_workspace(test_config.paths.workspace)
    target = workspace / "notes.txt"
    target.write_text("These are my notes.", encoding="utf-8")

    content = read_workspace_file(test_config, Path("notes.txt"))

    assert content == "These are my notes."


def test_read_workspace_file_handles_nested_files(test_config: Config):
    """A valid nested file inside the workspace should be read successfully."""
    workspace = ensure_workspace(test_config.paths.workspace)
    nested_dir = workspace / "projects"
    nested_dir.mkdir()

    target = nested_dir / "mind.md"
    target.write_text("# Mind\nLocal assistant notes.", encoding="utf-8")

    content = read_workspace_file(test_config, Path("projects/mind.md"))

    assert content == "# Mind\nLocal assistant notes."


def test_read_workspace_file_rejects_missing_file(test_config: Config):
    """A missing workspace file should return a clear error message."""
    result = read_workspace_file(test_config, Path("missing.txt"))

    assert "Error:" in result
    assert "not found" in result


def test_read_workspace_file_rejects_directories(test_config: Config):
    """The reader should reject directories instead of trying to read them as files."""
    workspace = ensure_workspace(test_config.paths.workspace)
    (workspace / "folder").mkdir()

    result = read_workspace_file(test_config, Path("folder"))

    assert "Error:" in result
    assert "directory" in result


def test_read_workspace_file_rejects_parent_directory_traversal(test_config: Config, tmp_path: Path):
    """The reader should not allow paths like ../secret.txt to escape the workspace."""
    ensure_workspace(test_config.paths.workspace)

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("do not expose this", encoding="utf-8")

    result = read_workspace_file(test_config, Path("../secret.txt"))

    assert "Error:" in result
    assert "Access denied" in result
    assert "do not expose this" not in result


def test_read_workspace_file_rejects_symlink_escape(test_config: Config, tmp_path: Path):
    """A symlink inside the workspace should not be allowed to point outside the workspace."""
    workspace = ensure_workspace(test_config.paths.workspace)

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("symlink secret", encoding="utf-8")

    symlink_path = workspace / "link.txt"

    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation is not supported in this environment.")

    result = read_workspace_file(test_config, Path("link.txt"))

    assert "Error:" in result
    assert "Access denied" in result
    assert "symlink secret" not in result
