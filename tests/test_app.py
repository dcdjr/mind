from pathlib import Path

import mind.app as app
from mind.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.context import ContextBundle


def make_test_config(tmp_path: Path) -> Config:
    """Create an isolated test config so app tests do not touch real project state."""
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


def test_ask_once_builds_context_and_calls_llm(monkeypatch, tmp_path: Path):
    """ask_once should build context once and pass it to the LLM ask function."""
    test_config = make_test_config(tmp_path)

    def fake_build_context(config, file_paths=None):
        assert config == test_config
        assert file_paths == [Path("notes.txt")]

        return ContextBundle(
            memory_context="Saved memory context.",
            workspace_context="FILE: notes.txt\n---\nWorkspace notes.",
        )

    def fake_ask(config, prompt, workspace_context=None, memory_context=None):
        assert config == test_config
        assert prompt == "summarize"
        assert workspace_context == "FILE: notes.txt\n---\nWorkspace notes."
        assert memory_context == "Saved memory context."

        return "fake response"

    monkeypatch.setattr(app, "build_context", fake_build_context)
    monkeypatch.setattr(app, "ask", fake_ask)

    result = app.ask_once(test_config, "summarize", [Path("notes.txt")])

    assert result == "fake response"


def test_ask_once_handles_no_file_paths(monkeypatch, tmp_path: Path):
    """ask_once should support prompts without explicit workspace files."""
    test_config = make_test_config(tmp_path)

    def fake_build_context(config, file_paths=None):
        assert config == test_config
        assert file_paths is None

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

    monkeypatch.setattr(app, "build_context", fake_build_context)
    monkeypatch.setattr(app, "ask", fake_ask)

    result = app.ask_once(test_config, "hello")

    assert result == "fake response"
