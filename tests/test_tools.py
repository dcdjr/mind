from pathlib import Path

from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
)
from mind.memory import add_memory
from mind.tools import run_tool, TOOL_REGISTRY, ToolSpec, format_available_tools


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


def test_run_tool_rejects_unknown_tool(tmp_path: Path):
    config = make_test_config(tmp_path)

    result = run_tool(config, "unknown.tool", {})

    assert "Error:" in result
    assert "Unknown tool" in result


def test_workspace_list_files_tool_lists_relative_files(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.list_files", {})

    assert "Workspace files:" in result
    assert "- notes.txt" in result


def test_workspace_read_file_tool_reads_workspace_file(tmp_path: Path):
    config = make_test_config(tmp_path)

    workspace = config.paths.workspace
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "notes.txt"})

    assert "FILE: notes.txt" in result
    assert "hello" in result


def test_workspace_read_file_tool_rejects_escape_path(tmp_path: Path):
    config = make_test_config(tmp_path)

    config.paths.workspace.mkdir(parents=True)

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secretsauce", encoding="utf-8")

    result = run_tool(config, "workspace.read_file", {"path": "../secret.txt"})

    assert "Access denied" in result
    assert "secretsauce" not in result


def test_memory_list_tool_lists_memories(tmp_path: Path):
    config = make_test_config(tmp_path)

    add_memory(config, "The project is named Mind.")

    result = run_tool(config, "memory.list", {})

    assert "Saved memories:" in result
    assert "- The project is named Mind." in result


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
