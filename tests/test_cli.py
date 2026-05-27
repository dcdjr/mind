from pathlib import Path

import mind.cli.commands as commands
import mind.cli.parser as cli
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


def test_mind_memories_routes_to_memories_command(monkeypatch, tmp_path: Path):
    """The `mind memories` command should route to the memories command."""
    test_config = make_test_config(tmp_path)
    called = False

    def fake_run_memories_command(config):
        nonlocal called
        assert config == test_config
        called = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: test_config)
    monkeypatch.setattr(cli, "run_memories_command", fake_run_memories_command)

    exit_code = cli.main(["memories"])

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

