from pathlib import Path

import mind.cli as cli
from mind.config import (
    AssistantConfig,
    Config,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.context import ContextBundle


def make_test_config(tmp_path: Path) -> Config:
    """Create an isolated test config so CLI tests do not touch real project state."""
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


def test_mind_home_runs(capsys):
    """The bare `mind` command should run and print the app identity."""
    exit_code = cli.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind" in captured.out
    assert "local-first personal AI assistant" in captured.out


def test_mind_doctor_runs(capsys, monkeypatch):
    """The `mind doctor` command should run and report basic setup status."""
    monkeypatch.setattr(cli, "is_ollama_running", lambda config: False)

    exit_code = cli.main(["doctor"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind doctor" in captured.out
    assert "Config: OK" in captured.out
    assert "Workspace: OK" in captured.out
    assert "Default model: gemma4:e4b" in captured.out


def test_mind_ask_runs_with_mocked_llm(capsys, monkeypatch, tmp_path: Path):
    """The `mind ask` command should route the prompt to the LLM layer and print the response."""
    test_config = make_test_config(tmp_path)

    def fake_build_context(config, file_path=None):
        assert config == test_config
        assert file_path is None

        return ContextBundle(
            memory_context=None,
            workspace_context=None,
        )

    def fake_ask(config, prompt, workspace_context=None, memory_context=None):
        assert config == test_config
        assert prompt == "hello"
        assert workspace_context is None
        assert memory_context is None

        return "fake response"

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "build_context", fake_build_context)
    monkeypatch.setattr(cli, "ask", fake_ask)

    exit_code = cli.main(["ask", "hello"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fake response" in captured.out


def test_mind_ask_with_file_passes_context_to_llm(capsys, monkeypatch, tmp_path: Path):
    """The `mind ask --file` command should pass built context to the LLM layer."""
    test_config = make_test_config(tmp_path)

    def fake_build_context(config, file_path=None):
        assert config == test_config
        assert file_path == Path("notes.txt")

        return ContextBundle(
            memory_context="Saved memory context.",
            workspace_context="These are workspace notes.",
        )

    def fake_ask(config, prompt, workspace_context=None, memory_context=None):
        assert config == test_config
        assert prompt == "summarize this"
        assert workspace_context == "These are workspace notes."
        assert memory_context == "Saved memory context."

        return "fake summary"

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "build_context", fake_build_context)
    monkeypatch.setattr(cli, "ask", fake_ask)

    exit_code = cli.main(["ask", "summarize this", "--file", "notes.txt"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fake summary" in captured.out


def test_mind_files_prints_empty_workspace(capsys, monkeypatch, tmp_path: Path):
    """The `mind files` command should report when the workspace has no files."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(cli, "load_config", lambda: test_config)

    exit_code = cli.main(["files"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Workspace is empty." in captured.out


def test_mind_files_prints_relative_file_paths(capsys, monkeypatch, tmp_path: Path):
    """The `mind files` command should print workspace files as relative paths."""
    test_config = make_test_config(tmp_path)

    workspace = test_config.paths.workspace
    nested_dir = workspace / "projects"
    nested_dir.mkdir(parents=True)

    (workspace / "notes.txt").write_text("notes", encoding="utf-8")
    (nested_dir / "mind.md").write_text("mind notes", encoding="utf-8")

    monkeypatch.setattr(cli, "load_config", lambda: test_config)

    exit_code = cli.main(["files"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Workspace files:" in captured.out
    assert "notes.txt" in captured.out
    assert "projects/mind.md" in captured.out
    assert str(workspace.resolve()) not in captured.out


def test_mind_chat_routes_to_chat_runner(monkeypatch, tmp_path: Path):
    """The `mind chat` command should route to the chat module's runner."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_chat(config):
        nonlocal called
        assert config == test_config
        called = True

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_chat", fake_run_chat)

    exit_code = cli.main(["chat"])

    assert exit_code == 0
    assert called is True


def test_mind_remember_stores_memory(capsys, monkeypatch, tmp_path: Path):
    """The `mind remember` command should store a memory."""
    test_config = make_test_config(tmp_path)
    stored = []

    def fake_add_memory(config, text):
        assert config == test_config
        stored.append(text)

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "add_memory", fake_add_memory)

    exit_code = cli.main(["remember", "The project is named Mind."])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert stored == ["The project is named Mind."]
    assert "Memory saved." in captured.out


def test_mind_memories_prints_empty_message(capsys, monkeypatch, tmp_path: Path):
    """The `mind memories` command should report when no memories exist."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "list_memories", lambda config: [])

    exit_code = cli.main(["memories"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No memories stored." in captured.out


def test_mind_memories_prints_stored_memories_with_ids(capsys, monkeypatch, tmp_path: Path):
    """The `mind memories` command should print stored memories using database IDs."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(
        cli,
        "list_memories",
        lambda config: [(1, "First memory."), (7, "Second memory.")],
    )

    exit_code = cli.main(["memories"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Memories:" in captured.out
    assert "1. First memory." in captured.out
    assert "7. Second memory." in captured.out


def test_mind_forget_deletes_existing_memory(capsys, monkeypatch, tmp_path: Path):
    """The `mind forget` command should delete a memory by ID."""
    test_config = make_test_config(tmp_path)
    deleted_ids = []

    def fake_delete_memory(config, memory_id):
        assert config == test_config
        deleted_ids.append(memory_id)
        return True

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "delete_memory", fake_delete_memory)

    exit_code = cli.main(["forget", "3"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert deleted_ids == [3]
    assert "Memory deleted." in captured.out


def test_mind_forget_reports_missing_memory(capsys, monkeypatch, tmp_path: Path):
    """The `mind forget` command should report when no memory exists with that ID."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "delete_memory", lambda config, memory_id: False)

    exit_code = cli.main(["forget", "999"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No memory found with ID 999." in captured.out
