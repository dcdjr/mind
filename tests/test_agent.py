from pathlib import Path

import mind.agent.loop as agent
from mind.agent.loop import PROTOCOL_REPAIR_MESSAGE
from mind.agent.prompts import build_agent_system_prompt
from mind.agent.protocol import (
    FinalAnswer,
    InvalidAgentResponse,
    ToolCall,
    extract_json_object,
    parse_agent_action,
)
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
from mind.tools import ToolResult


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for agent tests."""
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


def test_extract_json_object_parses_valid_json():
    raw = '{"type": "final", "answer": "Done."}'

    result = extract_json_object(raw)

    assert result == {"type": "final", "answer": "Done."}


def test_extract_json_object_handles_extra_text():
    raw = 'Here is the result:\n{"type": "final", "answer": "Done."}'

    result = extract_json_object(raw)

    assert result == {"type": "final", "answer": "Done."}


def test_extract_json_object_returns_none_for_invalid_json():
    raw = "not json"

    result = extract_json_object(raw)

    assert result is None


def test_parse_agent_action_returns_final_answer():
    raw = '{"type": "final", "answer": "Done."}'

    result = parse_agent_action(raw)

    assert result == FinalAnswer(answer="Done.")


def test_parse_agent_action_returns_tool_call():
    raw = '{"type": "tool_call", "tool": "workspace.list_files", "args": {}}'

    result = parse_agent_action(raw)

    assert result == ToolCall(tool="workspace.list_files", args={})


def test_parse_agent_action_returns_invalid_for_missing_json():
    raw = "not json"

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "valid JSON object" in result.message
    assert result.raw_output == raw


def test_parse_agent_action_returns_invalid_for_missing_type():
    raw = '{"answer": "Done."}'

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "missing required field 'type'" in result.message


def test_parse_agent_action_returns_invalid_for_unknown_type():
    raw = '{"type": "nonsense", "answer": "Done."}'

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "unknown response type" in result.message


def test_parse_agent_action_rejects_empty_final_answer():
    raw = '{"type": "final", "answer": "   "}'

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "valid answer" in result.message


def test_parse_agent_action_rejects_invalid_tool_name():
    raw = '{"type": "tool_call", "tool": 123, "args": {}}'

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "valid tool name" in result.message


def test_parse_agent_action_rejects_invalid_tool_args():
    raw = '{"type": "tool_call", "tool": "workspace.list_files", "args": "bad"}'

    result = parse_agent_action(raw)

    assert isinstance(result, InvalidAgentResponse)
    assert "invalid args" in result.message


def test_run_agent_returns_final_answer(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: '{"type": "final", "answer": "Final answer."}',
    )

    result = agent.run_agent(config, "hello")

    assert result == "Final answer."


def test_run_agent_includes_relevant_memory_context(monkeypatch, tmp_path: Path):
    """run_agent should include query-relevant saved memories in its system prompt."""
    config = make_test_config(tmp_path)
    captured_messages = []

    def fake_build_context(config, file_paths=None, query=None):
        assert query == "hello"
        return ContextBundle(
            memory_context="User is building Mind.",
            workspace_context=None,
        )

    def fake_complete(config, messages):
        captured_messages.extend(messages)
        return '{"type": "final", "answer": "Final answer."}'

    monkeypatch.setattr(agent, "build_context", fake_build_context)
    monkeypatch.setattr(agent, "complete", fake_complete)

    result = agent.run_agent(config, "hello")

    assert result == "Final answer."
    assert "Relevant saved memories:" in captured_messages[0]["content"]
    assert "User is building Mind." in captured_messages[0]["content"]


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

    def fake_run_tool(config, tool_name, args, confirm=None):
        tool_calls.append((tool_name, args, confirm))
        return ToolResult.success_result(tool_name, "Workspace is empty.")

    monkeypatch.setattr(agent, "complete", fake_complete)
    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    result = agent.run_agent(config, "what files are in my workspace?")

    assert result == "Your workspace is empty."
    assert tool_calls == [("workspace.list_files", {}, None)]


def test_run_agent_retries_once_after_invalid_json(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            "not json",
            '{"type": "final", "answer": "Recovered."}',
        ]
    )
    captured_messages = []

    def fake_complete(config, messages):
        captured_messages.append([message.copy() for message in messages])
        return next(responses)

    monkeypatch.setattr(agent, "complete", fake_complete)

    result = agent.run_agent(config, "recover from bad JSON")

    assert result == "Recovered."
    assert len(captured_messages) == 2
    assert "previous response was invalid" in captured_messages[1][-1]["content"]
    assert "Continue the original user task" in captured_messages[1][-1]["content"]
    assert "Protocol error:" in captured_messages[1][-1]["content"]


def test_run_agent_returns_error_after_protocol_retry_fails(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            "not json",
            "still not json",
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    result = agent.run_agent(config, "bad model output")

    assert "valid JSON object" in result


def test_run_agent_rejects_invalid_tool_name(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            '{"type": "tool_call", "tool": 123, "args": {}}',
            '{"type": "tool_call", "tool": 123, "args": {}}',
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    result = agent.run_agent(config, "bad tool")

    assert "valid tool name" in result


def test_run_agent_rejects_invalid_tool_args(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            '{"type": "tool_call", "tool": "workspace.list_files", "args": "bad"}',
            '{"type": "tool_call", "tool": "workspace.list_files", "args": "bad"}',
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    result = agent.run_agent(config, "bad args")

    assert "invalid args" in result


def test_run_agent_stops_after_max_steps(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: (
            '{"type": "tool_call", "tool": "workspace.list_files", "args": {}}'
        ),
    )

    monkeypatch.setattr(
        agent,
        "run_tool",
        lambda config, tool_name, args, confirm=None: ToolResult.success_result(
            tool_name,
            "Workspace is empty.",
        ),
    )

    result = agent.run_agent(config, "loop forever", max_steps=2)

    assert "maximum number of tool steps" in result


def test_run_agent_trace_includes_tool_call(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            '{"type": "tool_call", "tool": "workspace.list_files", "args": {}}',
            '{"type": "final", "answer": "Your workspace is empty."}',
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    monkeypatch.setattr(
        agent,
        "run_tool",
        lambda config, tool_name, args, confirm=None: ToolResult.success_result(
            tool_name,
            "Workspace is empty.",
        ),
    )

    result = agent.run_agent(
        config,
        "what files are in my workspace?",
        trace=True,
    )

    assert "Agent trace:" in result
    assert "Step 1" in result
    assert "Action: tool_call" in result
    assert "Tool: workspace.list_files" in result
    assert "Success: yes" in result
    assert "Result preview:" in result
    assert "Workspace is empty." in result
    assert "Step 2" in result
    assert "Action: final" in result
    assert "Final answer:" in result
    assert "Your workspace is empty." in result


def test_run_agent_trace_truncates_long_tool_output(monkeypatch, tmp_path: Path):
    """Trace mode should preview long tool outputs instead of dumping everything."""
    config = make_test_config(tmp_path)
    long_output = "A" * 2_100 + "TAIL_SHOULD_NOT_APPEAR"

    responses = iter(
        [
            '{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "big.txt"}}',
            '{"type": "final", "answer": "Read the file."}',
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    monkeypatch.setattr(
        agent,
        "run_tool",
        lambda config, tool_name, args, confirm=None: ToolResult.success_result(
            tool_name,
            long_output,
        ),
    )

    result = agent.run_agent(config, "read big file", trace=True)

    assert "Result preview:" in result
    assert "[Trace output truncated:" in result
    assert "TAIL_SHOULD_NOT_APPEAR" not in result
    assert "Final answer:" in result
    assert "Read the file." in result


def test_run_agent_trace_includes_parse_failure(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            "not json",
            "still not json",
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    result = agent.run_agent(config, "bad model output", trace=True)

    assert "Agent trace:" in result
    assert result.count("Action: parse_failure") == 2
    assert "Raw model response preview:" in result
    assert "not json" in result
    assert "still not json" in result
    assert "Action: error" in result
    assert "valid JSON object" in result


def test_run_agent_trace_shows_recovery_after_parse_failure(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    responses = iter(
        [
            "not json",
            '{"type": "final", "answer": "Recovered."}',
        ]
    )

    monkeypatch.setattr(
        agent,
        "complete",
        lambda config, messages: next(responses),
    )

    result = agent.run_agent(config, "recover", trace=True)

    assert "Agent trace:" in result
    assert "Action: parse_failure" in result
    assert "not json" in result
    assert "Action: final" in result
    assert "Recovered." in result
    assert "Action: error" not in result


def test_run_agent_includes_prior_messages(monkeypatch, tmp_path: Path):
    """run_agent should include prior chat context when provided."""
    config = make_test_config(tmp_path)
    captured_messages = []

    def fake_complete(config, messages):
        captured_messages.extend(messages)
        return '{"type": "final", "answer": "I remember the previous turn."}'

    monkeypatch.setattr(agent, "complete", fake_complete)

    result = agent.run_agent(
        config,
        "What did I just ask?",
        prior_messages=[
            {
                "role": "user",
                "content": "My previous question was about Mind.",
            },
            {
                "role": "assistant",
                "content": "You asked about Mind.",
            },
        ],
    )

    assert result == "I remember the previous turn."
    assert {
        "role": "user",
        "content": "My previous question was about Mind.",
    } in captured_messages
    assert {
        "role": "assistant",
        "content": "You asked about Mind.",
    } in captured_messages
    assert captured_messages[-1] == {
        "role": "user",
        "content": "What did I just ask?",
    }


def test_run_agent_returns_model_call_errors(monkeypatch, tmp_path: Path):
    """Model call failures should become user-facing agent errors."""
    config = make_test_config(tmp_path)

    def broken_complete(config, messages):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(agent, "complete", broken_complete)

    result = agent.run_agent(config, "hello")

    assert "Agent model call failed" in result
    assert "ollama down" in result


def test_run_agent_passes_confirmation_callback_to_tool(
    monkeypatch,
    tmp_path: Path,
):
    """run_agent should pass the confirmation callback through to run_tool."""
    config = make_test_config(tmp_path)

    responses = iter(
        [
            (
                '{"type": "tool_call", "tool": "workspace.write_file", '
                '"args": {"path": "notes.txt", "content": "hello"}}'
            ),
            '{"type": "final", "answer": "Done."}',
        ]
    )

    def fake_complete(config, messages):
        return next(responses)

    seen_confirm = []

    def fake_confirm(spec):
        return True

    def fake_run_tool(config, tool_name, args, confirm=None):
        seen_confirm.append(confirm)
        return ToolResult.success_result(tool_name, "Wrote workspace file: notes.txt")

    monkeypatch.setattr(agent, "complete", fake_complete)
    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    result = agent.run_agent(
        config,
        "write a note",
        confirm=fake_confirm,
    )

    assert result == "Done."
    assert seen_confirm == [fake_confirm]


def test_run_agent_stops_when_model_repeats_same_failing_tool_call(
    monkeypatch,
    tmp_path: Path,
):
    """run_agent should stop instead of repeating the same failed tool call."""
    config = make_test_config(tmp_path)
    repeated_call = (
        '{"type": "tool_call", "tool": "workspace.read_file", '
        '"args": {"path": "missing.txt"}}'
    )
    responses = iter([repeated_call, repeated_call])
    tool_calls = []

    def fake_complete(config, messages):
        return next(responses)

    def fake_run_tool(config, tool_name, args, confirm=None):
        tool_calls.append((tool_name, args))
        return ToolResult.failure_result(
            tool_name=tool_name,
            error="Error: File not found.",
        )

    monkeypatch.setattr(agent, "complete", fake_complete)
    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    result = agent.run_agent(config, "read missing file")

    assert result == (
        "Error: Agent repeated the same failing tool call instead of recovering."
    )
    assert tool_calls == [("workspace.read_file", {"path": "missing.txt"})]


def test_protocol_repair_message_does_not_include_concrete_tool_paths():
    """Repair prompt should not bias the model toward irrelevant example files."""
    assert '"tool": "<available_tool_name>"' in PROTOCOL_REPAIR_MESSAGE
    assert '"<arg_name>": "<arg_value>"' in PROTOCOL_REPAIR_MESSAGE
    assert '"answer": "<final-answer-text>"' in PROTOCOL_REPAIR_MESSAGE
    assert "notes.txt" not in PROTOCOL_REPAIR_MESSAGE
    assert "workspace.read_file" not in PROTOCOL_REPAIR_MESSAGE


def test_agent_system_prompt_uses_placeholder_json_examples(tmp_path: Path):
    """Agent prompt JSON examples should use placeholders instead of concrete paths."""
    config = make_test_config(tmp_path)

    system_prompt = build_agent_system_prompt(config)

    assert '"tool": "<available_tool_name>"' in system_prompt
    assert '"<arg_name>": "<arg_value>"' in system_prompt
    assert '"answer": "<final-answer-text>"' in system_prompt
    assert "notes.txt" not in system_prompt
