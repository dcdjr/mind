from __future__ import annotations

from pathlib import Path

from mind.core.config import Config


def ensure_workspace(workspace: Path) -> Path:
    """Create Mind's controlled workspace if it does not already exist."""
    workspace.mkdir(exist_ok=True)
    return workspace


def list_workspace_files(config: Config) -> list[Path]:
    """Returns a list of all files within the workspace, formatted for Mind's context."""
    workspace = ensure_workspace(config.paths.workspace)

    # rglob('*') finds everything recursively
    # Filter for files only so Mind doesn't try to "read" a directory
    # Nest in sorted() so output is deterministic
    files = sorted(
        f.relative_to(workspace)
        for f in workspace.rglob('*')
        if f.is_file()
    )

    return files if files else []


def read_workspace_file(config: Config, relative_path: Path) -> str:
    """Safely reads a file from the workspace for Mind."""
    # resolve() handles ".." and symlinks to prevent directory traversal
    workspace = ensure_workspace(config.paths.workspace).resolve()
    target = (workspace / relative_path).resolve()

    # Ensure the final path is still inside the workspace
    if not target.is_relative_to(workspace):
        return f"Error: Access denied. '{relative_path}' is outside the workspace."

    if not target.exists():
        return f"Error: File '{relative_path}' not found."

    if not target.is_file():
        return f"Error: '{relative_path}' is a directory, not a file."

    try:
        # 'utf-8-sig' handles files with Byte Order Marks (BOM) common in Windows.
        # errors='replace' prevents crashes if the file has unknown symbols
        content = target.read_text(encoding='utf-8-sig', errors='replace')
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"
