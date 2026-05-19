from pathlib import Path

import pytest

from mind.codebase import list_codebase_files, read_codebase_file
from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ProjectConfig,
    ToolConfig,
)


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create an isolated config so codebase tests do not touch the real repo."""
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
        tools=ToolConfig(
            allow_external_read=True,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        ),
        project=ProjectConfig(
            root=tmp_path / "project",
        ),
    )


def test_list_codebase_files_returns_project_relative_files(test_config: Config):
    """Codebase listing should return files relative to the configured project root."""
    root = test_config.project.root
    (root / "mind" / "agent").mkdir(parents=True)
    (root / "mind" / "agent" / "loop.py").write_text("print('loop')", encoding="utf-8")
    (root / "README.md").write_text("# Mind", encoding="utf-8")

    files = list_codebase_files(test_config)

    assert Path("README.md") in files
    assert Path("mind/agent/loop.py") in files
    assert all(not file.is_absolute() for file in files)


def test_list_codebase_files_ignores_runtime_and_build_directories(test_config: Config):
    """Codebase listing should skip local runtime/build directories."""
    root = test_config.project.root

    (root / "mind").mkdir(parents=True)
    (root / "mind" / "__init__.py").write_text("", encoding="utf-8")

    ignored_paths = [
        root / ".git" / "HEAD",
        root / ".venv" / "pyvenv.cfg",
        root / "__pycache__" / "module.pyc",
        root / ".pytest_cache" / "README.md",
        root / "mind_local.egg-info" / "PKG-INFO",
        root / "data" / "mind.db",
        root / "workspace" / "demo.md",
        root / "dist" / "artifact.whl",
        root / "build" / "temp.txt",
    ]

    for path in ignored_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored", encoding="utf-8")

    files = list_codebase_files(test_config)

    assert Path("mind/__init__.py") in files
    assert Path(".git/HEAD") not in files
    assert Path(".venv/pyvenv.cfg") not in files
    assert Path("__pycache__/module.pyc") not in files
    assert Path(".pytest_cache/README.md") not in files
    assert Path("mind_local.egg-info/PKG-INFO") not in files
    assert Path("data/mind.db") not in files
    assert Path("workspace/demo.md") not in files
    assert Path("dist/artifact.whl") not in files
    assert Path("build/temp.txt") not in files


def test_read_codebase_file_returns_file_contents(test_config: Config):
    """A valid project-relative file should be read successfully."""
    root = test_config.project.root
    target = root / "mind" / "agent" / "loop.py"
    target.parent.mkdir(parents=True)
    target.write_text("def run_agent():\n    pass\n", encoding="utf-8")

    result = read_codebase_file(test_config, Path("mind/agent/loop.py"))

    assert result == "def run_agent():\n    pass\n"


def test_read_codebase_file_rejects_missing_file(test_config: Config):
    """A missing project file should return a clear error."""
    result = read_codebase_file(test_config, Path("missing.py"))

    assert "Error:" in result
    assert "not found" in result


def test_read_codebase_file_rejects_directory(test_config: Config):
    """The reader should reject directories."""
    root = test_config.project.root
    (root / "mind").mkdir(parents=True)

    result = read_codebase_file(test_config, Path("mind"))

    assert "Error:" in result
    assert "directory" in result


def test_read_codebase_file_rejects_parent_directory_traversal(
    test_config: Config,
    tmp_path: Path,
):
    """Codebase reads should not allow ../ paths to escape the project root."""
    test_config.project.root.mkdir(parents=True)

    outside_file = tmp_path / "secret.py"
    outside_file.write_text("do not expose this", encoding="utf-8")

    result = read_codebase_file(test_config, Path("../secret.py"))

    assert "Error:" in result
    assert "Access denied" in result
    assert "do not expose this" not in result


def test_read_codebase_file_rejects_absolute_path(test_config: Config, tmp_path: Path):
    """Codebase reads should reject absolute paths."""
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("secret", encoding="utf-8")

    result = read_codebase_file(test_config, outside_file)

    assert "Error:" in result
    assert "Absolute paths are not allowed" in result
    assert "secret" not in result


def test_read_codebase_file_rejects_symlink_escape(
    test_config: Config,
    tmp_path: Path,
):
    """A symlink inside the project should not expose files outside the project root."""
    root = test_config.project.root
    root.mkdir(parents=True)

    outside_file = tmp_path / "secret.py"
    outside_file.write_text("symlink secret", encoding="utf-8")

    symlink_path = root / "link.py"

    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation is not supported in this environment.")

    result = read_codebase_file(test_config, Path("link.py"))

    assert "Error:" in result
    assert "Access denied" in result
    assert "symlink secret" not in result


def test_read_codebase_file_rejects_ignored_path(test_config: Config):
    """Ignored project paths should not be readable."""
    root = test_config.project.root
    target = root / "data" / "mind.db"
    target.parent.mkdir(parents=True)
    target.write_text("database contents", encoding="utf-8")

    result = read_codebase_file(test_config, Path("data/mind.db"))

    assert "Error:" in result
    assert "ignored" in result
    assert "database contents" not in result


def test_read_codebase_file_rejects_binary_file(test_config: Config):
    """Binary-ish files should not be returned as text context."""
    root = test_config.project.root
    target = root / "binary.bin"
    root.mkdir(parents=True)
    target.write_bytes(b"\x00\x01\x02\x03")

    result = read_codebase_file(test_config, Path("binary.bin"))

    assert "Error:" in result
    assert "binary" in result


def test_read_codebase_file_truncates_large_files(test_config: Config):
    """Large source files should be truncated instead of fully injected."""
    root = test_config.project.root
    target = root / "large.py"
    root.mkdir(parents=True)
    target.write_text("A" * 90_000, encoding="utf-8")

    result = read_codebase_file(test_config, Path("large.py"))

    assert len(result) < 90_000
    assert "[Codebase file truncated]" in result
