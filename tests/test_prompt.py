from pathlib import Path

from mind.config import load_config
from mind.prompt import build_messages, build_system_prompt


def test_build_system_prompt_includes_mind_identity():
    """The system prompt should identify the assistant as Mind and describe its local-first role."""
    config = load_config(Path("configs/config.toml"))

    system_prompt = build_system_prompt(config)

    assert "Mind" in system_prompt
    assert "local-first personal AI assistant" in system_prompt


def test_build_messages_returns_system_and_user_messages():
    """The prompt builder should return one system message followed by the exact user message."""
    config = load_config(Path("configs/config.toml"))

    messages = build_messages(config, "hello")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "hello"

def test_build_system_prompt_includes_memory_context():
    config = load_config(Path("configs/config.toml"))

    system_prompt = build_system_prompt(
        config,
        memory_context="Saved memories about the user and project:\n- User prefers concise explanations.",
    )

    assert "BEGIN SAVED MEMORIES" in system_prompt
    assert "User prefers concise explanations." in system_prompt
