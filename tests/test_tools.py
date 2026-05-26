from pathlib import Path

from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ProjectConfig,
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
        ),
        project=ProjectConfig(
            root=tmp_path / "project",
        ),
    )


def make_local_write_config(tmp_path: Path) -> Config:
    """Create a test config where local write tools are explicitly enabled."""
    base_config = make_test_config(tmp_path)

    return Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=base_config.memory,
        context=base_config.context,
        tools=ToolConfig(
            allow_external_read=True,
            allow_local_write=True,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        ),
        project=base_config.project,
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
    assert result.success is False
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


def test_codebase_list_files_tool_lists_project_files(tmp_path: Path):
    """codebase.list_files should list visible files under the configured project root."""
    config = make_test_config(tmp_path)

    root = config.project.root
    (root / "mind").mkdir(parents=True, exist_ok=True)
    (root / "mind" / "__init__.py").write_text("", encoding="utf-8")

    result = run_tool(config, "codebase.list_files", {})

    assert result.success is True
    assert "Codebase files:" in result.output
    assert "- mind/__init__.py" in result.output


def test_codebase_read_file_tool_reads_project_file(tmp_path: Path):
    """codebase.read_file should read a project-relative file."""
    config = make_test_config(tmp_path)

    root = config.project.root
    target = root / "mind" / "agent" / "loop.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def run_agent():\n    pass\n", encoding="utf-8")

    result = run_tool(
        config,
        "codebase.read_file",
        {
            "path": "mind/agent/loop.py",
        },
    )

    assert result.success is True
    assert "FILE: mind/agent/loop.py" in result.output
    assert "def run_agent" in result.output


def test_codebase_read_file_tool_rejects_escape_path(tmp_path: Path):
    """codebase.read_file should not allow paths outside the project root."""
    config = make_test_config(tmp_path)

    config.project.root.mkdir(parents=True, exist_ok=True)

    outside_file = tmp_path / "secret.py"
    outside_file.write_text("supersecret", encoding="utf-8")

    result = run_tool(
        config,
        "codebase.read_file",
        {
            "path": "../secret.py",
        },
    )

    assert result.success is False
    assert "Access denied" in result.output
    assert "FILE:" not in result.output
    assert "supersecret" not in result.output


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
        requires_confirmation=False,
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
    """Every tool should include the metadata needed for prompts and permissions."""
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


def test_format_available_tools_uses_tool_spec_metadata(tmp_path: Path):
    """Available tool formatting should be generated from ToolSpec metadata."""
    config = make_local_write_config(tmp_path)
    formatted_tools = format_available_tools(config)

    assert "workspace.list_files" in formatted_tools
    assert "List files in the workspace." in formatted_tools

    assert "workspace.read_file" in formatted_tools
    assert '{"path": "notes.txt"}' in formatted_tools

    assert "workspace.write_file" in formatted_tools
    assert "Write text to a workspace-relative file." in formatted_tools

    assert "workspace.append_file" in formatted_tools
    assert "Append text to a workspace-relative file." in formatted_tools

    assert "memory.list" in formatted_tools
    assert "List saved memories." in formatted_tools

    assert "codebase.list_files" in formatted_tools
    assert "List source files in the configured project codebase." in formatted_tools

    assert "codebase.read_file" in formatted_tools
    assert '{"path": "mind/agent/loop.py"}' in formatted_tools

    assert "internet.github_zen" in formatted_tools
    assert "Fetch a short random phrase from GitHub's public Zen API." in formatted_tools

    assert "project.status" in formatted_tools
    assert "List information about the current status of the Mind project." in formatted_tools

    assert "project.devlog" in formatted_tools
    assert "Append a dated project devlog entry to workspace/devlog.md." in formatted_tools

    assert "Permission:" in formatted_tools
    assert "Requires confirmation:" in formatted_tools


def test_format_available_tools_hides_disabled_local_write_tools(tmp_path: Path):
    """Disabled local-write tools should not be advertised to the agent."""
    config = make_test_config(tmp_path)

    formatted_tools = format_available_tools(config)

    assert "workspace.list_files" in formatted_tools
    assert "workspace.read_file" in formatted_tools
    assert "memory.list" in formatted_tools
    assert "codebase.list_files" in formatted_tools
    assert "codebase.read_file" in formatted_tools
    assert "project.status" in formatted_tools

    assert "workspace.write_file" not in formatted_tools
    assert "workspace.append_file" not in formatted_tools
    assert "project.devlog" not in formatted_tools


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
        project=base_config.project,
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
        project=base_config.project,
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
        requires_confirmation=False,
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
    assert "local_write" in result.output


def test_tool_spec_requires_confirmation_by_default():
    """New tools should require confirmation unless they explicitly opt out."""
    spec = ToolSpec(
        name="test.local_write",
        description="Fake local-write tool.",
        args_description="{}",
        permission="local_write",
        function=lambda config, args: "ok",
    )

    assert spec.requires_confirmation is True


def test_existing_read_tools_do_not_require_confirmation():
    """Current low-risk read tools should explicitly opt out of confirmation."""
    assert TOOL_REGISTRY["workspace.list_files"].requires_confirmation is False
    assert TOOL_REGISTRY["workspace.read_file"].requires_confirmation is False
    assert TOOL_REGISTRY["memory.list"].requires_confirmation is False
    assert TOOL_REGISTRY["codebase.list_files"].requires_confirmation is False
    assert TOOL_REGISTRY["codebase.read_file"].requires_confirmation is False
    assert TOOL_REGISTRY["internet.github_zen"].requires_confirmation is False
    assert TOOL_REGISTRY["project.status"].requires_confirmation is False


def test_permission_denial_message_uses_actual_permission(monkeypatch, tmp_path: Path):
    """Blocked tools should report the specific permission that caused the denial."""
    config = make_test_config(tmp_path)
    called = False

    def fake_local_write_tool(config, args):
        nonlocal called
        called = True
        return "should not run"

    local_write_spec = ToolSpec(
        name="test.local_write_message",
        description="Fake local-write tool.",
        args_description="{}",
        permission="local_write",
        function=fake_local_write_tool,
    )

    monkeypatch.setitem(TOOL_REGISTRY, "test.local_write_message", local_write_spec)

    result = run_tool(config, "test.local_write_message", {})

    assert result.success is False
    assert called is False
    assert "local_write" in result.output


def test_workspace_write_file_tool_is_registered():
    """The workspace write tool should be available in the registry."""
    spec = TOOL_REGISTRY["workspace.write_file"]

    assert spec.name == "workspace.write_file"
    assert spec.permission == "local_write"
    assert spec.requires_confirmation is True


def test_workspace_write_file_tool_is_blocked_when_local_write_disabled(tmp_path: Path):
    """workspace.write_file should fail closed when local writes are disabled."""
    config = make_test_config(tmp_path)

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "hello",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "local_write" in result.output
    assert not (config.paths.workspace / "notes.txt").exists()


def test_confirmed_tool_fails_closed_without_confirmation_handler(tmp_path: Path):
    """Confirmed tools should not run unless a confirmation callback is supplied."""
    config = make_local_write_config(tmp_path)

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "should not be written",
        },
    )

    assert result.success is False
    assert "requires confirmation" in result.output
    assert "no confirmation handler" in result.output
    assert not (config.paths.workspace / "notes.txt").exists()


def test_workspace_write_file_tool_writes_when_local_write_enabled(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.write_file should write files when local writes are enabled and confirmed."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "hello from tool",
        },
        confirm=lambda spec: True,
    )

    target = config.paths.workspace / "notes.txt"

    assert result.success is True
    assert "Wrote workspace file" in result.output
    assert target.read_text(encoding="utf-8") == "hello from tool"


def test_workspace_write_file_tool_accepts_yes_confirmation(
    monkeypatch,
    tmp_path: Path,
):
    """Confirmed tools should run when the user types yes."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "yes")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "confirmed",
        },
        confirm=lambda spec: True,
    )

    target = config.paths.workspace / "notes.txt"

    assert result.success is True
    assert "Wrote workspace file" in result.output
    assert target.read_text(encoding="utf-8") == "confirmed"


def test_workspace_write_file_tool_does_not_run_when_confirmation_is_denied(
    monkeypatch,
    tmp_path: Path,
):
    """Confirmed tools should not run when the user denies confirmation."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "should not be written",
        },
        confirm=lambda spec: False,
    )

    assert result.success is False
    assert "did not confirm" in result.output
    assert not (config.paths.workspace / "notes.txt").exists()


def test_workspace_write_file_tool_rejects_missing_path(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.write_file should validate that path is provided."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "content": "hello",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "path" in result.output


def test_workspace_write_file_tool_rejects_non_string_content(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.write_file should validate that content is a string."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": 123,
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "content" in result.output


def test_workspace_write_file_tool_rejects_non_boolean_overwrite(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.write_file should validate that overwrite is a boolean when provided."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.write_file",
        {
            "path": "notes.txt",
            "content": "hello",
            "overwrite": "yes",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "overwrite" in result.output


def test_workspace_append_file_tool_is_registered():
    """The workspace append tool should be available in the registry."""
    spec = TOOL_REGISTRY["workspace.append_file"]

    assert spec.name == "workspace.append_file"
    assert spec.permission == "local_write"
    assert spec.requires_confirmation is True


def test_workspace_append_file_tool_is_blocked_when_local_write_disabled(tmp_path: Path):
    """workspace.append_file should fail closed when local writes are disabled."""
    config = make_test_config(tmp_path)

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": "hello",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "local_write" in result.output
    assert not (config.paths.workspace / "notes.txt").exists()


def test_workspace_append_file_tool_appends_when_local_write_enabled(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.append_file should append when local writes are enabled and confirmed."""
    config = make_local_write_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    target = workspace / "notes.txt"
    target.write_text("first\n", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": "second\n",
        },
        confirm=lambda spec: True,
    )

    assert result.success is True
    assert "Appended to workspace file" in result.output
    assert target.read_text(encoding="utf-8") == "first\nsecond\n"


def test_workspace_append_file_tool_creates_missing_file_when_confirmed(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.append_file should create a missing file by default when confirmed."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "yes")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": "created\n",
        },
        confirm=lambda spec: True,
    )

    target = config.paths.workspace / "notes.txt"

    assert result.success is True
    assert "Appended to workspace file" in result.output
    assert target.read_text(encoding="utf-8") == "created\n"


def test_workspace_append_file_tool_does_not_run_when_confirmation_is_denied(
    monkeypatch,
    tmp_path: Path,
):
    """Confirmed append tools should not run when the user denies confirmation."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": "should not be written",
        },
        confirm=lambda spec: False,
    )

    assert result.success is False
    assert "did not confirm" in result.output
    assert not (config.paths.workspace / "notes.txt").exists()


def test_workspace_append_file_tool_rejects_missing_path(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.append_file should validate that path is provided."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "content": "hello",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "path" in result.output


def test_workspace_append_file_tool_rejects_non_string_content(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.append_file should validate that content is a string."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": 123,
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "content" in result.output


def test_workspace_append_file_tool_rejects_non_boolean_create(
    monkeypatch,
    tmp_path: Path,
):
    """workspace.append_file should validate that create is a boolean when provided."""
    config = make_local_write_config(tmp_path)

    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    result = run_tool(
        config,
        "workspace.append_file",
        {
            "path": "notes.txt",
            "content": "hello",
            "create": "yes",
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "create" in result.output


def test_project_status_tool_is_registered():
    """The project status tool should be read-only and confirmation-free."""
    spec = TOOL_REGISTRY["project.status"]

    assert spec.name == "project.status"
    assert spec.permission == "read_only"
    assert spec.requires_confirmation is False


def test_project_status_tool_reports_current_runtime_state(tmp_path: Path):
    """project.status should return a deterministic summary of project state."""
    config = make_test_config(tmp_path)
    config.paths.workspace.mkdir(parents=True)
    (config.paths.workspace / "notes.txt").write_text("hello", encoding="utf-8")
    add_memory(config, "Mind should keep concise project status.")

    result = run_tool(config, "project.status", {})

    assert result.success is True
    assert "PROJECT STATUS BEGIN" in result.output
    assert "Configured provider/model: ollama / gemma4:e4b" in result.output
    assert f"Workspace path: {config.paths.workspace}" in result.output
    assert f"Database path: {config.paths.database}" in result.output
    assert f"Project root: {config.project.root}" in result.output
    assert "Workspace files: 1" in result.output
    assert "Stored memories: 1" in result.output
    assert f"Registered tools: {len(TOOL_REGISTRY)}" in result.output
    assert "Available agent tools: 7" in result.output
    assert "local_write: disabled" in result.output
    assert "PROJECT STATUS END" in result.output


def test_project_status_tool_runs_when_local_write_is_disabled(tmp_path: Path):
    """project.status should remain available under read-only tool permissions."""
    config = make_test_config(tmp_path)

    result = run_tool(config, "project.status", {})

    assert result.success is True
    assert "PROJECT STATUS BEGIN" in result.output


def test_project_devlog_tool_is_registered():
    """The project devlog tool should be a confirmed local-write tool."""
    spec = TOOL_REGISTRY["project.devlog"]

    assert spec.name == "project.devlog"
    assert spec.permission == "local_write"
    assert spec.requires_confirmation is True


def test_project_devlog_tool_is_blocked_when_local_write_disabled(tmp_path: Path):
    """project.devlog should fail closed when local writes are disabled."""
    config = make_test_config(tmp_path)

    result = run_tool(
        config,
        "project.devlog",
        {
            "summary": "Added project tools.",
            "next_steps": ["Document them."],
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "local_write" in result.output
    assert not (config.paths.workspace / "devlog.md").exists()


def test_project_devlog_tool_requires_confirmation_handler(tmp_path: Path):
    """project.devlog should not run without explicit confirmation."""
    config = make_local_write_config(tmp_path)

    result = run_tool(
        config,
        "project.devlog",
        {
            "summary": "Added project tools.",
        },
    )

    assert result.success is False
    assert "requires confirmation" in result.output
    assert not (config.paths.workspace / "devlog.md").exists()


def test_project_devlog_tool_appends_dated_entry_when_confirmed(tmp_path: Path):
    """project.devlog should append a Markdown entry to workspace/devlog.md."""
    config = make_local_write_config(tmp_path)

    result = run_tool(
        config,
        "project.devlog",
        {
            "summary": "  Added project status and devlog tools.  ",
            "next_steps": [" Add docs. ", "", "Add tests."],
        },
        confirm=lambda spec: True,
    )

    target = config.paths.workspace / "devlog.md"
    content = target.read_text(encoding="utf-8")

    assert result.success is True
    assert result.output == "Appended project devlog entry to workspace/devlog.md."
    assert content.startswith("## ")
    assert "Added project status and devlog tools." in content
    assert "Next steps:" in content
    assert "- Add docs." in content
    assert "- Add tests." in content
    assert "- " not in content.replace("- Add docs.", "").replace("- Add tests.", "")


def test_project_devlog_tool_appends_to_existing_devlog(tmp_path: Path):
    """project.devlog should preserve previous devlog entries."""
    config = make_local_write_config(tmp_path)
    target = config.paths.workspace / "devlog.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing entry\n", encoding="utf-8")

    result = run_tool(
        config,
        "project.devlog",
        {
            "summary": "Added another entry.",
        },
        confirm=lambda spec: True,
    )

    content = target.read_text(encoding="utf-8")

    assert result.success is True
    assert content.startswith("existing entry\n")
    assert "Added another entry." in content


def test_project_devlog_tool_rejects_missing_summary(tmp_path: Path):
    """project.devlog should require a non-empty summary string."""
    config = make_local_write_config(tmp_path)

    result = run_tool(
        config,
        "project.devlog",
        {
            "next_steps": ["Add summary."],
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "summary" in result.output
    assert not (config.paths.workspace / "devlog.md").exists()


def test_project_devlog_tool_rejects_non_string_next_steps(tmp_path: Path):
    """project.devlog should require next_steps to be a list of strings."""
    config = make_local_write_config(tmp_path)

    result = run_tool(
        config,
        "project.devlog",
        {
            "summary": "Added project tools.",
            "next_steps": ["Document them.", 123],
        },
        confirm=lambda spec: True,
    )

    assert result.success is False
    assert "Error:" in result.output
    assert "next_steps" in result.output
    assert not (config.paths.workspace / "devlog.md").exists()
