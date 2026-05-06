from pathlib import Path

from mind.cli import main
from mind.config import (
    AssistantConfig,
    Config,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)


def test_mind_home_runs(capsys):
    """The bare `mind` command should run and print the app identity."""
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind" in captured.out
    assert "local-first personal AI assistant" in captured.out


def test_mind_doctor_runs(capsys):
    """The `mind doctor` command should run and report basic setup status."""
    exit_code = main(["doctor"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind doctor" in captured.out
    assert "Config: OK" in captured.out
    assert "Workspace: OK" in captured.out
    assert "Default model: gemma4:e4b" in captured.out


def test_mind_ask_runs_with_mocked_llm(capsys, monkeypatch):
    """The `mind ask` command should route the prompt to the LLM layer and print the response."""
    def fake_ask(config, prompt, workspace_context=None):
        assert prompt == "hello"
        return "fake response"

    monkeypatch.setattr("mind.cli.ask", fake_ask)

    exit_code = main(["ask", "hello"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fake response" in captured.out


def test_mind_ask_with_file_passes_workspace_context(capsys, monkeypatch, tmp_path: Path):
    """The `mind ask --file` command should read a workspace file and pass its contents to the LLM layer."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    notes_file = workspace / "notes.txt"
    notes_file.write_text("These are workspace notes.", encoding="utf-8")

    test_config = Config(
        assistant=AssistantConfig(
            name="Mind",
            description="Test assistant",
        ),
        paths=PathConfig(
            workspace=workspace,
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

    def fake_ask(config, prompt, workspace_context=None):
        assert config == test_config
        assert prompt == "summarize this"
        assert workspace_context == "These are workspace notes."
        return "fake summary"

    monkeypatch.setattr("mind.cli.load_config", lambda: test_config)
    monkeypatch.setattr("mind.cli.ask", fake_ask)

    exit_code = main(["ask", "summarize this", "--file", "notes.txt"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fake summary" in captured.out


def test_mind_files_prints_empty_workspace(capsys, monkeypatch, tmp_path: Path):
    """The `mind files` command should report when the workspace has no files."""
    test_config = Config(
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

    monkeypatch.setattr("mind.cli.load_config", lambda: test_config)

    exit_code = main(["files"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Workspace is empty." in captured.out


def test_mind_files_prints_relative_file_paths(capsys, monkeypatch, tmp_path: Path):
    """The `mind files` command should print workspace files as relative paths."""
    workspace = tmp_path / "workspace"
    nested_dir = workspace / "projects"
    nested_dir.mkdir(parents=True)

    (workspace / "notes.txt").write_text("notes", encoding="utf-8")
    (nested_dir / "mind.md").write_text("mind notes", encoding="utf-8")

    test_config = Config(
        assistant=AssistantConfig(
            name="Mind",
            description="Test assistant",
        ),
        paths=PathConfig(
            workspace=workspace,
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

    monkeypatch.setattr("mind.cli.load_config", lambda: test_config)

    exit_code = main(["files"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Workspace files:" in captured.out
    assert "notes.txt" in captured.out
    assert "projects/mind.md" in captured.out
    assert str(workspace.resolve()) not in captured.out
