from pathlib import Path

from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ToolConfig,
)
from mind.memory import add_memory
from mind.tools import (
    TOOL_REGISTRY,
    ToolResult,
    ToolSpec,
    format_available_tools,
    run_tool,
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
        tools=ToolConfig(
            allow_external_read=True,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        )
    )


def test_run_tool_rejects_unknown_tool(tmp_path: Path):
    config = make_test_config(tmp_path)

    result = run_tool(config, "unknown.tool", {})

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "Error:" in result.output
    assert "Unknown tool" in result.output


def test_workspace_list_files_tool_lists_relative_files(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.list_files", {})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "Workspace files:" in result.output
    assert "- notes.txt" in result.output


def test_workspace_read_file_tool_reads_workspace_file(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "notes.txt"})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "FILE: notes.txt" in result.output
    assert "hello" in result.output


def test_workspace_read_file_tool_rejects_escape_path(tmp_path: Path):
    config = make_test_config(tmp_path)

    config.paths.workspace.mkdir(parents=True)

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secretsauce", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "../secret.txt"})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "Access denied" in result.output
    assert "secretsauce" not in result.output


def test_memory_list_tool_lists_memories(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    result = run_tool(config, "memory.list", {})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "Saved memories:" in result.output
    assert "- The project is named Mind." in result.output


def test_run_tool_wraps_tool_exceptions(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    def broken_tool(config, args):
        raise RuntimeError("boom")

    broken_spec = ToolSpec(
        name="test.broken",
        description="Broken test tool.",
        args_description="{}",
        permission="read_only",
        function=broken_tool,
    )

    monkeypatch.setitem(TOOL_REGISTRY, "test.broken", broken_spec)

    result = run_tool(config, "test.broken", {})

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "RuntimeError" in result.output
    assert "boom" in result.output


def test_tool_registry_values_are_tool_specs():
    """Every registered tool should be described by a ToolSpec."""
    for spec in TOOL_REGISTRY.values():
        assert isinstance(spec, ToolSpec)


def test_tool_registry_keys_match_tool_spec_names():
    """Registry keys should match the ToolSpec name field."""
    for tool_name, spec in TOOL_REGISTRY.items():
        assert tool_name == spec.name


def test_registered_tools_have_required_metadata():
    """Every tool should include the metadata needed for prompts and future permissions."""
    for spec in TOOL_REGISTRY.values():
        assert spec.name
        assert spec.description
        assert spec.args_description
        assert spec.permission in {
            "read_only",
            "external_read",
            "local_write",
            "external_write",
            "dangerous",
        }
        assert callable(spec.function)


def test_format_available_tools_uses_tool_spec_metadata():
    """Available tool formatting should be generated from ToolSpec metadata."""
    formatted_tools = format_available_tools()

    assert "workspace.list_files" in formatted_tools
    assert "List files in the workspace." in formatted_tools
    assert "workspace.read_file" in formatted_tools
    assert '{"path": "notes.txt"}' in formatted_tools
    assert "internet.github_zen" in formatted_tools
    assert "Fetch a short random phrase from GitHub's public Zen API." in formatted_tools


def test_read_only_tools_run_even_when_restricted_permissions_are_disabled(tmp_path: Path):
    """Read-only tools should still run when non-read permissions are disabled."""
    base_config = make_test_config(tmp_path)

    config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=base_config.memory,
        context=base_config.context,
        tools=ToolConfig(
            allow_external_read=False,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        ),
    )

    result = run_tool(config, "workspace.list_files", {})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "Workspace is empty." in result.output


def test_external_read_tool_is_blocked_when_external_read_is_disabled(tmp_path: Path):
    """External-read tools should not run when external read permission is disabled."""
    base_config = make_test_config(tmp_path)

    config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=base_config.memory,
        context=base_config.context,
        tools=ToolConfig(
            allow_external_read=False,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        ),
    )

    result = run_tool(config, "internet.github_zen", {})

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "Error:" in result.output
    assert (
        "permitted" in result.output.lower()
        or "permission" in result.output.lower()
    )


def test_external_read_tool_runs_when_external_read_is_enabled(
    monkeypatch,
    tmp_path: Path,
):
    """External-read tools should run when external read permission is enabled."""
    config = make_test_config(tmp_path)

    def fake_external_read_tool(config, args):
        return "external read worked"

    external_read_spec = ToolSpec(
        name="test.external_read",
        description="Fake external-read tool.",
        args_description="{}",
        permission="external_read",
        function=fake_external_read_tool,
    )

    monkeypatch.setitem(TOOL_REGISTRY, "test.external_read", external_read_spec)

    result = run_tool(config, "test.external_read", {})

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output == "external read worked"


def test_local_write_tool_is_blocked_when_local_write_is_disabled(
    monkeypatch,
    tmp_path: Path,
):
    """Local-write tools should not run when local write permission is disabled."""
    config = make_test_config(tmp_path)
    called = False

    def fake_local_write_tool(config, args):
        nonlocal called
        called = True
        return "should not run"

    local_write_spec = ToolSpec(
        name="test.local_write",
        description="Fake local-write tool.",
        args_description="{}",
        permission="local_write",
        function=fake_local_write_tool,
    )

    monkeypatch.setitem(TOOL_REGISTRY, "test.local_write", local_write_spec)

    result = run_tool(config, "test.local_write", {})

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert called is False
    assert "Error:" in result.output
    assert (
        "permitted" in result.output.lower()
        or "permission" in result.output.lower()
    )
