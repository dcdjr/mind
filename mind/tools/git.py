from __future__ import annotations

import subprocess
from typing import Any

from mind.core.config import Config


MAX_GIT_STATUS_CHARS = 20_000
GIT_STATUS_TRUNCATION_MARKER = "\n[Git status truncated]"


def _truncate_git_status(output: str) -> str:
    """Limit long Git status output while preserving a visible truncation marker."""
    if len(output) <= MAX_GIT_STATUS_CHARS:
        return output

    available_chars = MAX_GIT_STATUS_CHARS - len(GIT_STATUS_TRUNCATION_MARKER)

    if available_chars <= 0:
        return GIT_STATUS_TRUNCATION_MARKER.strip()

    return output[:available_chars].rstrip() + GIT_STATUS_TRUNCATION_MARKER


def tool_git_status(config: Config, args: dict[str, Any]) -> str:
    """Show read-only Git status for the configured project root."""
    if args:
        return "Error: git.status does not accept arguments."

    try:
        in_git_repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=config.project.root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return "Error: git executable was not found."
    except subprocess.TimeoutExpired:
        return "Error: git status timed out."

    if in_git_repo.returncode != 0 or in_git_repo.stdout.strip() != "true":
        return "Error: Project root is not inside a Git repository."

    try:
        git_status_result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=config.project.root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return "Error: git executable was not found."
    except subprocess.TimeoutExpired:
        return "Error: git status timed out."

    if git_status_result.returncode != 0:
        error = git_status_result.stderr.strip() or "unknown git error"
        return f"Error: git status failed: {error}"

    status_lines = git_status_result.stdout.strip().splitlines()

    if not status_lines:
        return _truncate_git_status("Git status:\n\nWorking tree clean.")

    branch_line = status_lines[0]
    change_lines = status_lines[1:]

    if not change_lines:
        return _truncate_git_status(
            f"Git status:\n\nBranch:\n{branch_line}\n\nChanges:\nWorking tree clean."
        )

    changes = "\n".join(change_lines)

    return _truncate_git_status(
        f"Git status:\n\nBranch:\n{branch_line}\n\nChanges:\n{changes}"
    )
