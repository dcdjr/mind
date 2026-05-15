from pathlib import Path

import mind.chat as chat
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
    """Create an isolated test config so chat tests do not touch real project state."""
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


def test_run_chat_exits_on_quit(capsys, monkeypatch, tmp_path: Path):
    """The chat loop should exit cleanly when the user enters /quit."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config: ContextBundle(
            memory_context=None,
            workspace_context=None,
        ),
    )

    monkeypatch.setattr(
        chat,
        "build_initial_chat_messages",
        lambda config, workspace_context=None, memory_context=None: [
            {"role": "system", "content": "system prompt"}
        ],
    )

    inputs = iter(["/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config)
    captured = capsys.readouterr()

    assert "Mind chat. Type /exit or /quit to quit." in captured.out
    assert "Exiting Mind chat." in captured.out


def test_run_chat_sends_user_message_to_model_and_prints_response(
    capsys,
    monkeypatch,
    tmp_path: Path,
):
    """The chat loop should append a user message, call the model, and print the response."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config: ContextBundle(
            memory_context="Saved memory context.",
            workspace_context=None,
        ),
    )

    def fake_build_initial_chat_messages(config, workspace_context=None, memory_context=None):
        assert config == test_config
        assert memory_context == "Saved memory context."

        return [{"role": "system", "content": "system prompt"}]

    def fake_complete(config, messages):
        assert config == test_config
        assert messages[-1] == {
            "role": "user",
            "content": "hello",
        }

        return "fake assistant response"

    extracted_turns = []

    def fake_maybe_extract_and_store_memories(config, user_input, response):
        extracted_turns.append((user_input, response))

    monkeypatch.setattr(chat, "build_initial_chat_messages", fake_build_initial_chat_messages)
    monkeypatch.setattr(chat, "complete", fake_complete)
    monkeypatch.setattr(chat, "maybe_extract_and_store_memories", fake_maybe_extract_and_store_memories)

    inputs = iter(["hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config)
    captured = capsys.readouterr()

    assert "fake assistant response" in captured.out
    assert extracted_turns == [("hello", "fake assistant response")]


def test_maybe_extract_and_store_memories_saves_extracted_memories(monkeypatch, tmp_path: Path):
    """Automatic memory extraction should save each extracted memory."""
    test_config = make_test_config(tmp_path)
    stored = []

    monkeypatch.setattr(
        chat,
        "extract_memories",
        lambda config, user_input, response: ["User wants Mind to stay local-first."],
    )

    def fake_add_memory(config, text):
        stored.append(text)

    monkeypatch.setattr(chat, "add_memory", fake_add_memory)

    chat.maybe_extract_and_store_memories(
        test_config,
        "My project is Mind and I want it local-first.",
        "Got it.",
    )

    assert stored == ["User wants Mind to stay local-first."]


def test_maybe_extract_and_store_memories_does_nothing_when_auto_memory_disabled(
    monkeypatch,
    tmp_path: Path,
):
    """Automatic memory extraction should not run when auto memory is disabled."""
    base_config = make_test_config(tmp_path)

    test_config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=MemoryConfig(
            auto_memory=False,
            max_relevant_memories=8,
        ),
        context=base_config.context,
    )

    called = False

    def fake_extract_memories(config, user_input, response):
        nonlocal called
        called = True
        return ["Should not be stored."]

    monkeypatch.setattr(chat, "extract_memories", fake_extract_memories)

    chat.maybe_extract_and_store_memories(test_config, "hello", "hi")

    assert called is False


def test_maybe_extract_and_store_memories_skips_duplicate_memories(monkeypatch, tmp_path: Path):
    """Automatic memory extraction should not store an extracted memory that already exists."""
    test_config = make_test_config(tmp_path)
    stored = []

    monkeypatch.setattr(
        chat,
        "extract_memories",
        lambda config, user_input, response: ["User wants Mind to stay local-first."],
    )

    monkeypatch.setattr(
        chat,
        "memory_exists",
        lambda config, text: text == "User wants Mind to stay local-first.",
    )

    def fake_add_memory(config, text):
        stored.append(text)

    monkeypatch.setattr(chat, "add_memory", fake_add_memory)

    chat.maybe_extract_and_store_memories(
        test_config,
        "My project is Mind and I want it local-first.",
        "Got it.",
    )

    assert stored == []
