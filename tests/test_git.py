import subprocess
from pathlib import Path

import mind.tools.git as git_tools
from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    EmbeddingConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ProjectConfig,
    ToolConfig,
)
from mind.tools.git import tool_git_status


def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for Git tool tests."""
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
        project=ProjectConfig(
            root=tmp_path / "project",
        ),
    )


def completed_process(
    args: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a typed CompletedProcess for fake subprocess calls."""
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_git_status_rejects_arguments(tmp_path: Path):
    """git.status should not accept model-supplied arguments."""
    config = make_test_config(tmp_path)

    result = tool_git_status(config, {"path": "."})

    assert result == "Error: git.status does not accept arguments."


def test_git_status_rejects_non_git_project_root(monkeypatch, tmp_path: Path):
    """git.status should fail clearly outside a Git work tree."""
    config = make_test_config(tmp_path)

    def fake_run(args, cwd, capture_output, text, timeout):
        assert cwd == config.project.root
        return completed_process(args, returncode=128, stdout="false\n")

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert result == "Error: Project root is not inside a Git repository."


def test_git_status_formats_clean_work_tree(monkeypatch, tmp_path: Path):
    """git.status should show the branch and a clean-tree message."""
    config = make_test_config(tmp_path)
    calls = []

    def fake_run(args, cwd, capture_output, text, timeout):
        calls.append(args)

        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return completed_process(args, stdout="true\n")

        if args == ["git", "status", "--short", "--branch"]:
            return completed_process(args, stdout="## main\n")

        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert calls == [
        ["git", "rev-parse", "--is-inside-work-tree"],
        ["git", "status", "--short", "--branch"],
    ]
    assert result == (
        "Git status:\n\n"
        "Branch:\n## main\n\n"
        "Changes:\nWorking tree clean."
    )


def test_git_status_formats_changed_work_tree(monkeypatch, tmp_path: Path):
    """git.status should include short-status change lines."""
    config = make_test_config(tmp_path)

    def fake_run(args, cwd, capture_output, text, timeout):
        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return completed_process(args, stdout="true\n")

        if args == ["git", "status", "--short", "--branch"]:
            return completed_process(
                args,
                stdout="## main...origin/main [ahead 1]\n M README.md\n?? notes.txt\n",
            )

        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert result == (
        "Git status:\n\n"
        "Branch:\n## main...origin/main [ahead 1]\n\n"
        "Changes:\n M README.md\n?? notes.txt"
    )


def test_git_status_truncates_long_output(monkeypatch, tmp_path: Path):
    """git.status should cap very long successful status output."""
    config = make_test_config(tmp_path)
    changed_files = "\n".join(f" M file-{index}.txt" for index in range(3_000))

    def fake_run(args, cwd, capture_output, text, timeout):
        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return completed_process(args, stdout="true\n")

        if args == ["git", "status", "--short", "--branch"]:
            return completed_process(args, stdout=f"## main\n{changed_files}\n")

        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert len(result) <= git_tools.MAX_GIT_STATUS_CHARS
    assert result.endswith(git_tools.GIT_STATUS_TRUNCATION_MARKER)


def test_git_status_reports_status_command_failure(monkeypatch, tmp_path: Path):
    """git.status should report stderr from a failed status command."""
    config = make_test_config(tmp_path)

    def fake_run(args, cwd, capture_output, text, timeout):
        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return completed_process(args, stdout="true\n")

        if args == ["git", "status", "--short", "--branch"]:
            return completed_process(args, returncode=1, stderr="fatal: bad repo")

        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert result == "Error: git status failed: fatal: bad repo"


def test_git_status_reports_missing_git(monkeypatch, tmp_path: Path):
    """git.status should fail clearly when git is unavailable."""
    config = make_test_config(tmp_path)

    def fake_run(args, cwd, capture_output, text, timeout):
        raise FileNotFoundError

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert result == "Error: git executable was not found."


def test_git_status_reports_timeout(monkeypatch, tmp_path: Path):
    """git.status should fail clearly when a Git command times out."""
    config = make_test_config(tmp_path)

    def fake_run(args, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = tool_git_status(config, {})

    assert result == "Error: git status timed out."
