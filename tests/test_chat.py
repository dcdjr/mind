from pathlib import Path

import mind.runtime.chat as chat
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
from mind.core.context import ContextBundle


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for chat tests."""
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


def test_run_chat_exits_on_quit(capsys, monkeypatch, tmp_path: Path):
    """The chat loop should exit cleanly when the user enters /quit."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
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
        lambda config, **kwargs: ContextBundle(
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

    monkeypatch.setattr(
        chat,
        "build_initial_chat_messages",
        fake_build_initial_chat_messages,
    )
    monkeypatch.setattr(chat, "complete", fake_complete)
    monkeypatch.setattr(
        chat,
        "maybe_extract_and_store_memories",
        fake_maybe_extract_and_store_memories,
    )

    inputs = iter(["hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config)
    captured = capsys.readouterr()

    assert "fake assistant response" in captured.out
    assert extracted_turns == [("hello", "fake assistant response")]


def test_maybe_extract_and_store_memories_saves_extracted_memories(
    monkeypatch,
    tmp_path: Path,
):
    """Automatic memory extraction should save each extracted memory."""
    test_config = make_test_config(tmp_path)
    stored = []

    monkeypatch.setattr(
        chat,
        "extract_memories",
        lambda config, user_input, response: ["User wants Mind to stay local-first."],
    )

    def fake_add_memory(config, text, **kwargs):
        stored.append((text, kwargs))

    monkeypatch.setattr(chat, "add_memory", fake_add_memory)

    chat.maybe_extract_and_store_memories(
        test_config,
        "My project is Mind and I want it local-first.",
        "Got it.",
    )

    assert stored == [
        (
            "User wants Mind to stay local-first.",
            {
                "kind": "general",
                "source": "chat_auto",
                "status": "auto_extracted",
                "confidence": 0.6,
            },
        )
    ]


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
            auto_extract=False,
            inject_context=True,
            max_relevant_memories=8,
        ),
        embeddings=base_config.embeddings,
        context=base_config.context,
        tools=base_config.tools,
        project=base_config.project,
    )

    called = False

    def fake_extract_memories(config, user_input, response):
        nonlocal called
        called = True
        return ["Should not be stored."]

    monkeypatch.setattr(chat, "extract_memories", fake_extract_memories)

    chat.maybe_extract_and_store_memories(test_config, "hello", "hi")

    assert called is False


def test_maybe_extract_and_store_memories_skips_duplicate_memories(
    monkeypatch,
    tmp_path: Path,
):
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


def test_run_chat_uses_agent_when_tools_enabled(capsys, monkeypatch, tmp_path: Path):
    """Tool-enabled chat should run each user turn through the agent loop."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
            memory_context=None,
            workspace_context=None,
        ),
    )

    agent_calls = []

    def fake_run_agent(config, prompt, trace=False, prior_messages=None, confirm=None):
        agent_calls.append((prompt, trace, list(prior_messages or [])))
        return "agent response"

    extracted_turns = []

    def fake_maybe_extract_and_store_memories(config, user_input, response):
        extracted_turns.append((user_input, response))

    monkeypatch.setattr(chat, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        chat,
        "maybe_extract_and_store_memories",
        fake_maybe_extract_and_store_memories,
    )

    inputs = iter(["what files are in my workspace?", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config, tools=True, trace=True)
    captured = capsys.readouterr()

    assert "Mind chat with tools." in captured.out
    assert "agent response" in captured.out
    assert agent_calls == [("what files are in my workspace?", True, [])]
    assert extracted_turns == [("what files are in my workspace?", "agent response")]


def test_run_chat_with_tools_preserves_agent_history(
    capsys,
    monkeypatch,
    tmp_path: Path,
):
    """Tool-enabled chat should pass previous turns back into later agent calls."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
            memory_context=None,
            workspace_context=None,
        ),
    )

    agent_calls = []

    def fake_run_agent(config, prompt, trace=False, prior_messages=None, confirm=None):
        agent_calls.append((prompt, list(prior_messages or [])))

        if prompt == "first":
            return "first response"

        return "second response"

    monkeypatch.setattr(chat, "run_agent", fake_run_agent)
    monkeypatch.setattr(chat, "maybe_extract_and_store_memories", lambda *args: None)

    inputs = iter(["first", "second", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config, tools=True, trace=False)
    captured = capsys.readouterr()

    assert "first response" in captured.out
    assert "second response" in captured.out

    assert agent_calls[0] == ("first", [])
    assert agent_calls[1] == (
        "second",
        [
            {
                "role": "user",
                "content": "first",
            },
            {
                "role": "assistant",
                "content": "first response",
            },
        ],
    )


def test_strip_trace_for_history_keeps_only_final_answer():
    """Trace output should not be stored as normal chat history."""
    response = (
        "Agent trace:\n\n"
        "Step 1\n"
        "Action: final\n"
        "Answer: Clean answer.\n\n"
        "Final answer:\n"
        "Clean answer."
    )

    assert chat._strip_trace_for_history(response) == "Clean answer."


def test_run_chat_without_tools_uses_normal_model_path(capsys, monkeypatch, tmp_path: Path):
    """Normal chat should still use the regular chat message loop."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
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

    complete_calls = []

    def fake_complete(config, messages):
        complete_calls.append(messages[-1])
        return "normal response"

    monkeypatch.setattr(chat, "complete", fake_complete)
    monkeypatch.setattr(chat, "maybe_extract_and_store_memories", lambda *args: None)

    inputs = iter(["hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config, tools=False)
    captured = capsys.readouterr()

    assert "Mind chat. Type /exit or /quit to quit." in captured.out
    assert "normal response" in captured.out
    assert complete_calls == [{"role": "user", "content": "hello"}]


def test_run_chat_uses_selected_model(capsys, monkeypatch, tmp_path: Path):
    """Chat should pass an explicit model selection to each model call."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
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

    models = []

    def fake_complete(config, messages, model=None):
        models.append(model)
        return "uncensored response"

    monkeypatch.setattr(chat, "complete", fake_complete)
    monkeypatch.setattr(chat, "maybe_extract_and_store_memories", lambda *args: None)

    inputs = iter(["hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config, model="dolphin3:8b")
    captured = capsys.readouterr()

    assert "uncensored response" in captured.out
    assert models == ["dolphin3:8b"]


def test_run_chat_with_tools_uses_selected_model(capsys, monkeypatch, tmp_path: Path):
    """Tool-enabled chat should pass an explicit model selection to the agent."""
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        chat,
        "build_context",
        lambda config, **kwargs: ContextBundle(
            memory_context=None,
            workspace_context=None,
        ),
    )

    models = []

    def fake_run_agent(config, prompt, **kwargs):
        models.append(kwargs.get("model"))
        return "uncensored agent response"

    monkeypatch.setattr(chat, "run_agent", fake_run_agent)
    monkeypatch.setattr(chat, "maybe_extract_and_store_memories", lambda *args: None)

    inputs = iter(["hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    chat.run_chat(test_config, tools=True, model="dolphin3:8b")
    captured = capsys.readouterr()

    assert "uncensored agent response" in captured.out
    assert models == ["dolphin3:8b"]
