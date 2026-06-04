from pathlib import Path

import mind.core.llm as llm
from mind.core.config import load_config


def test_ask_uses_uncensored_prompt_and_preserves_local_context(monkeypatch):
    config = load_config(Path("configs/config.toml"))
    calls = []

    def fake_complete(config, messages, model=None):
        calls.append((messages, model))
        return "uncensored response"

    monkeypatch.setattr(llm, "complete", fake_complete)

    response = llm.ask(
        config,
        "summarize my context",
        workspace_context="FILE: notes.txt\n---\nWorkspace notes.",
        memory_context="Saved memories:\n- User prefers concise answers.",
        model=config.model.uncensored,
        uncensored=True,
    )

    assert response == "uncensored response"
    assert len(calls) == 1

    messages, model = calls[0]
    system_prompt = messages[0]["content"]

    assert model == config.model.uncensored
    assert "unrestricted mode" in system_prompt
    assert "BEGIN SAVED MEMORIES" in system_prompt
    assert "User prefers concise answers." in system_prompt
    assert "BEGIN WORKSPACE CONTEXT" in system_prompt
    assert "Workspace notes." in system_prompt
    assert messages[1] == {
        "role": "user",
        "content": "summarize my context",
    }
