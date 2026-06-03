from pathlib import Path

import mind.cli.commands as commands
import mind.cli.parser as cli
from mind.agent.runs import save_agent_run
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


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for CLI tests."""
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
        )
    )


def test_mind_home_routes_to_home_command(monkeypatch, tmp_path: Path):
    """The bare `mind` command should route to the home command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_home_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_home_command", fake_run_home_command)

    exit_code = cli.main([])

    assert exit_code == 0
    assert called is True


def test_mind_doctor_routes_to_doctor_command(monkeypatch, tmp_path: Path):
    """The `mind doctor` command should route to the doctor command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_doctor_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_doctor_command", fake_run_doctor_command)

    exit_code = cli.main(["doctor"])

    assert exit_code == 0
    assert called is True


def test_mind_ask_routes_to_ask_command(monkeypatch, tmp_path: Path):
    """The `mind ask` command should route the prompt to the ask command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_ask_command(config, prompt, files, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "hello"
        assert files is None
        assert tools is False
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_ask_command", fake_run_ask_command)

    exit_code = cli.main(["ask", "hello"])

    assert exit_code == 0
    assert called is True


def test_mind_ask_with_files_routes_file_arguments(monkeypatch, tmp_path: Path):
    """The `mind ask --files` command should pass file arguments to the ask command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_ask_command(config, prompt, files, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "summarize these"
        assert files == ["notes.txt", "plan.md"]
        assert tools is False
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_ask_command", fake_run_ask_command)

    exit_code = cli.main(
        ["ask", "summarize these", "--files", "notes.txt", "plan.md"]
    )

    assert exit_code == 0
    assert called is True


def test_mind_ask_tools_routes_tools_flag(monkeypatch, tmp_path: Path):
    """The `mind ask --tools` command should enable tool use for ask mode."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_ask_command(config, prompt, files, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert files is None
        assert tools is True
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_ask_command", fake_run_ask_command)

    exit_code = cli.main(["ask", "--tools", "what files are in my workspace?"])

    assert exit_code == 0
    assert called is True


def test_mind_ask_tools_trace_routes_trace_flag(monkeypatch, tmp_path: Path):
    """The `mind ask --tools --trace` command should enable tool tracing."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_ask_command(config, prompt, files, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert files is None
        assert tools is True
        assert trace is True
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_ask_command", fake_run_ask_command)

    exit_code = cli.main(
        ["ask", "--tools", "--trace", "what files are in my workspace?"]
    )

    assert exit_code == 0
    assert called is True


def test_run_ask_command_uses_ask_once_by_default(monkeypatch, tmp_path: Path, capsys):
    """run_ask_command should use the normal ask runtime unless tools are enabled."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_ask_once(config, prompt, file_paths=None):
        nonlocal called
        assert config == test_config
        assert prompt == "hello"
        assert file_paths is None
        called = True
        return "normal answer"

    monkeypatch.setattr(commands, "ask_once", fake_ask_once)

    exit_code = commands.run_ask_command(test_config, "hello", None)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert called is True
    assert "normal answer" in captured.out


def test_run_ask_command_uses_agent_when_tools_enabled(monkeypatch, tmp_path: Path, capsys):
    """run_ask_command should use the agent runtime when tools are enabled."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_agent(config, prompt, trace=False, confirm=None):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert trace is True
        assert confirm is commands.confirm_tool_run
        called = True
        return "agent answer"

    monkeypatch.setattr(commands, "run_agent", fake_run_agent)

    exit_code = commands.run_ask_command(
        test_config,
        "what files are in my workspace?",
        None,
        tools=True,
        trace=True,
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert called is True
    assert "agent answer" in captured.out


def test_run_ask_command_rejects_files_with_tools(tmp_path: Path, capsys):
    """Tool-enabled ask mode should reject --files until agent file context is supported."""
    test_config = make_test_config(tmp_path)

    exit_code = commands.run_ask_command(
        test_config,
        "summarize notes",
        ["notes.txt"],
        tools=True,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--files cannot be used with --tools yet" in captured.out


def test_run_ask_command_rejects_trace_without_tools(tmp_path: Path, capsys):
    """Trace mode should only be accepted when tool use is enabled."""
    test_config = make_test_config(tmp_path)

    exit_code = commands.run_ask_command(
        test_config,
        "hello",
        None,
        tools=False,
        trace=True,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--trace can only be used with --tools" in captured.out


def test_mind_files_routes_to_files_command(monkeypatch, tmp_path: Path):
    """The `mind files` command should route to the files command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_files_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_files_command", fake_run_files_command)

    exit_code = cli.main(["files"])

    assert exit_code == 0
    assert called is True


def test_mind_chat_routes_to_chat_command(monkeypatch, tmp_path: Path):
    """The `mind chat` command should route to the chat command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_chat_command(config, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert tools is False
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_chat_command", fake_run_chat_command)

    exit_code = cli.main(["chat"])

    assert exit_code == 0
    assert called is True


def test_mind_remember_routes_to_remember_command(monkeypatch, tmp_path: Path):
    """The `mind remember` command should route memory text to the remember command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_remember_command(config, text):
        nonlocal called
        assert config == test_config
        assert text == "The project is named Mind."
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_remember_command", fake_run_remember_command)

    exit_code = cli.main(["remember", "The project is named Mind."])

    assert exit_code == 0
    assert called is True


def test_mind_forget_routes_to_forget_command(monkeypatch, tmp_path: Path):
    """The `mind forget` command should route the memory ID to the forget command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_forget_command(config, memory_id):
        nonlocal called
        assert config == test_config
        assert memory_id == 3
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_forget_command", fake_run_forget_command)

    exit_code = cli.main(["forget", "3"])

    assert exit_code == 0
    assert called is True


def test_mind_agent_routes_to_agent_command(monkeypatch, tmp_path: Path):
    """The `mind agent` command should route the prompt to the agent command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_agent_command(config, prompt, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_agent_command", fake_run_agent_command)

    exit_code = cli.main(["agent", "what files are in my workspace?"])

    assert exit_code == 0
    assert called is True


def test_mind_tools_routes_to_tools_command(monkeypatch, tmp_path: Path):
    """The `mind tools` command should route to the tools command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_tools_command(config):
        nonlocal called
        called = True
        assert config == test_config
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_tools_command", fake_run_tools_command)

    exit_code = cli.main(["tools"])

    assert exit_code == 0
    assert called is True


def test_mind_runs_routes_to_runs_command(monkeypatch, tmp_path: Path):
    """The `mind runs` command should route to the saved-runs listing."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_runs_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_runs_command", fake_run_runs_command)

    exit_code = cli.main(["runs"])

    assert exit_code == 0
    assert called is True


def test_mind_run_show_routes_to_run_show_command(monkeypatch, tmp_path: Path):
    """The `mind run show` command should route the run ID."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_run_show_command(config, run_id):
        nonlocal called
        assert config == test_config
        assert run_id == "20260603-120000-deadbeef"
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_run_show_command", fake_run_run_show_command)

    exit_code = cli.main(["run", "show", "20260603-120000-deadbeef"])

    assert exit_code == 0
    assert called is True


def test_mind_agent_trace_routes_trace_flag(monkeypatch, tmp_path: Path):
    """The `mind agent --trace` command should enable trace mode."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_agent_command(config, prompt, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert trace is True
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_agent_command", fake_run_agent_command)

    exit_code = cli.main(["agent", "--trace", "what files are in my workspace?"])

    assert exit_code == 0
    assert called is True


def test_mind_chat_tools_routes_tools_flag(monkeypatch, tmp_path: Path):
    """The `mind chat --tools` command should enable tool use for chat mode."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_chat_command(config, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert tools is True
        assert trace is False
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_chat_command", fake_run_chat_command)

    exit_code = cli.main(["chat", "--tools"])

    assert exit_code == 0
    assert called is True


def test_mind_chat_tools_trace_routes_trace_flag(monkeypatch, tmp_path: Path):
    """The `mind chat --tools --trace` command should enable tool tracing."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_chat_command(config, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert tools is True
        assert trace is True
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_chat_command", fake_run_chat_command)

    exit_code = cli.main(["chat", "--tools", "--trace"])

    assert exit_code == 0
    assert called is True


def test_run_chat_command_rejects_trace_without_tools(tmp_path: Path, capsys):
    """Trace mode should only be accepted when chat tools are enabled."""
    test_config = make_test_config(tmp_path)

    exit_code = commands.run_chat_command(
        test_config,
        tools=False,
        trace=True,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--trace can only be used with --tools" in captured.out


def test_run_agent_command_delegates_to_tool_enabled_ask(monkeypatch, tmp_path: Path):
    """run_agent_command should behave as a compatibility alias for ask --tools."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_ask_command(config, prompt, files, tools=False, trace=False):
        nonlocal called
        assert config == test_config
        assert prompt == "what files are in my workspace?"
        assert files is None
        assert tools is True
        assert trace is True
        called = True
        return 0

    monkeypatch.setattr(commands, "run_ask_command", fake_run_ask_command)

    exit_code = commands.run_agent_command(
        test_config,
        "what files are in my workspace?",
        trace=True,
    )

    assert exit_code == 0
    assert called is True


def test_mind_memories_routes_status_filter(monkeypatch, tmp_path: Path):
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memories_command(config, status=None):
        nonlocal called
        assert config == test_config
        assert status == "auto_extracted"
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_memories_command", fake_run_memories_command)

    exit_code = cli.main(["memories", "--status", "auto_extracted"])

    assert exit_code == 0
    assert called is True


def test_mind_memory_confirm_routes_to_confirm_command(monkeypatch, tmp_path: Path):
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memory_confirm_command(config, memory_id):
        nonlocal called
        assert config == test_config
        assert memory_id == 7
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_memory_confirm_command", fake_run_memory_confirm_command)

    exit_code = cli.main(["memory", "confirm", "7"])

    assert exit_code == 0
    assert called is True


def test_mind_memory_reject_routes_to_reject_command(monkeypatch, tmp_path: Path):
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memory_reject_command(config, memory_id):
        nonlocal called
        assert config == test_config
        assert memory_id == 8
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_memory_reject_command", fake_run_memory_reject_command)

    exit_code = cli.main(["memory", "reject", "8"])

    assert exit_code == 0
    assert called is True


def test_mind_memory_delete_routes_to_delete_command(monkeypatch, tmp_path: Path):
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memory_delete_command(config, memory_id):
        nonlocal called
        assert config == test_config
        assert memory_id == 9
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_memory_delete_command", fake_run_memory_delete_command)

    exit_code = cli.main(["memory", "delete", "9"])

    assert exit_code == 0
    assert called is True


def test_mind_memory_backfill_routes_to_backfill_command(monkeypatch, tmp_path: Path):
    """The `mind memory backfill` command should route to the backfill command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memory_backfill_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(
        cli,
        "run_memory_backfill_command",
        fake_run_memory_backfill_command,
    )

    exit_code = cli.main(["memory", "backfill"])

    assert exit_code == 0
    assert called is True


def test_run_memory_backfill_command_prints_summary(monkeypatch, tmp_path: Path, capsys):
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(
        commands,
        "backfill_embeddings",
        lambda config: commands.BackfillResult(
            model="nomic-embed-text",
            total_missing=2,
            succeeded=1,
            failed=1,
            errors=[
                commands.BackfillError(
                    memory_id=2,
                    message="RuntimeError: embedding failed",
                )
            ],
        ),
    )

    exit_code = commands.run_memory_backfill_command(test_config)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Memory embedding backfill" in captured.out
    assert "Model: nomic-embed-text" in captured.out
    assert "Missing embeddings: 2" in captured.out
    assert "Failed memory 2: RuntimeError: embedding failed" in captured.out
    assert "Succeeded: 1" in captured.out
    assert "Failed: 1" in captured.out


def test_run_runs_command_lists_saved_agent_runs(tmp_path: Path, capsys):
    """run_runs_command should print saved run IDs and metadata."""
    test_config = make_test_config(tmp_path)
    saved_run = save_agent_run(
        config=test_config,
        user_prompt="hello",
        final_answer="answer",
        trace_output=None,
        status="completed",
    )

    exit_code = commands.run_runs_command(test_config)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert saved_run.run_id in captured.out
    assert "Status: completed" in captured.out
    assert "Model: ollama / gemma4:e4b" in captured.out


def test_run_run_show_command_prints_saved_agent_run(tmp_path: Path, capsys):
    """run_run_show_command should print metadata, prompt, answer, and trace."""
    test_config = make_test_config(tmp_path)
    saved_run = save_agent_run(
        config=test_config,
        user_prompt="hello",
        final_answer="answer",
        trace_output="trace details\n",
        status="completed",
    )

    exit_code = commands.run_run_show_command(test_config, saved_run.run_id)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Agent run: {saved_run.run_id}" in captured.out
    assert "Prompt:\nhello" in captured.out
    assert "Final answer:\nanswer" in captured.out
    assert "Trace:\ntrace details" in captured.out


def test_mind_memory_archive_routes_to_archive_command(monkeypatch, tmp_path: Path):
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memory_archive_command(config, memory_id):
        nonlocal called
        assert config == test_config
        assert memory_id == 10
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(
        cli,
        "run_memory_archive_command",
        fake_run_memory_archive_command,
    )

    exit_code = cli.main(["memory", "archive", "10"])

    assert exit_code == 0
    assert called is True


def test_run_memory_archive_command_prints_archived_message(monkeypatch, tmp_path: Path, capsys):
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(commands, "archive_memory", lambda config, memory_id: True)

    exit_code = commands.run_memory_archive_command(test_config, 1)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Memory archived." in captured.out


def test_run_memory_archive_command_prints_missing_memory(monkeypatch, tmp_path: Path, capsys):
    test_config = make_test_config(tmp_path)

    monkeypatch.setattr(commands, "archive_memory", lambda config, memory_id: False)

    exit_code = commands.run_memory_archive_command(test_config, 99)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No memory found with ID 99." in captured.out
