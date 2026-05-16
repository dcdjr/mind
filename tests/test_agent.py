from pathlib import Path

import mind.agent as agent
from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)


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


def test_extract_json_object_parses_valid_json():
    raw = '{"type": "final", "answer": "Done."}'

    result = agent.extract_json_object(raw)

    assert result == {"type": "final", "answer": "Done."}


def test_extract_json_object_handles_extra_text():
    raw = 'Here is the result:\n{"type": "final", "answer": "Done."}'

    result = agent.extract_json_object(raw)

    assert result == {"type": "final", "answer": "Done."}


def test_extract_json_object_returns_none_for_invalid_json():
    raw = "not json"

    result = agent.extract_json_object(raw)

    assert result is None


def test_run_agent_returns_final_answer(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: '{"type": "final", "answer": "Final answer."}',
    )

    result = agent.run_agent(config, "hello")

    assert result == "Final answer."


def test_run_agent_runs_tool_then_returns_final_answer(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            '{"type": "tool_call", "tool": "workspace.list_files", "args": {}}',
            '{"type": "final", "answer": "Your workspace is empty."}',
        ]
    )

    tool_calls = []

    def fake_complete(config, messages):
        return next(responses)

    def fake_run_tool(config, tool_name, args):
        tool_calls.append((tool_name, args))
        return "Workspace is empty."

    monkeypatch.setattr(agent, "complete", fake_complete)
    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    result = agent.run_agent(config, "what files are in my workspace?")

    assert result == "Your workspace is empty."
    assert tool_calls == [("workspace.list_files", {})]


def test_run_agent_rejects_invalid_tool_name(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: '{"type": "tool_call", "tool": 123, "args": {}}',
    )

    result = agent.run_agent(config, "bad tool")

    assert "valid tool name" in result


def test_run_agent_rejects_invalid_tool_args(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: '{"type": "tool_call", "tool": "workspace.list_files", "args": "bad"}',
    )

    result = agent.run_agent(config, "bad args")

    assert "invalid args" in result


def test_run_agent_stops_after_max_steps(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: '{"type": "tool_call", "tool": "workspace.list_files", "args": {}}',
    )

    monkeypatch.setattr(
        agent,
        "run_tool",
        lambda config, tool_name, args: "Workspace is empty.",
    )

    result = agent.run_agent(config, "loop forever", max_steps=2)

    assert "maximum number of tool steps" in result
