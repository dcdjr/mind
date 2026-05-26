from __future__ import annotations

from pathlib import Path

from mind.core.config import Config


MAX_WORKSPACE_WRITE_CHARS = 100_000


def ensure_workspace(workspace: Path) -> Path:
    """Create Mind's controlled workspace if it does not already exist."""
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _resolve_workspace_target(
    config: Config,
    relative_path: Path,
) -> tuple[Path | None, str | None]:
    """
    Resolve a workspace-relative path safely.

    This is the shared safety boundary for workspace reads and writes.
    It rejects absolute paths, parent-directory escapes, and symlink escapes.
    """
    if str(relative_path).strip() in {"", "."}:
        return None, "Error: Workspace path cannot be empty."

    if relative_path.is_absolute():
        return (
            None,
            f"Error: Access denied. Absolute paths are not allowed: '{relative_path}'.",
        )

    workspace = ensure_workspace(config.paths.workspace).resolve()
    target = (workspace / relative_path).resolve()

    if not target.is_relative_to(workspace):
        return (
            None,
            f"Error: Access denied. '{relative_path}' is outside the workspace.",
        )

    return target, None


def list_workspace_files(config: Config) -> list[Path]:
    """Return all files inside the workspace as workspace-relative paths."""
    workspace = ensure_workspace(config.paths.workspace)

    # rglob("*") walks recursively.
    # Filtering with is_file() avoids returning directories.
    # sorted() keeps CLI/test output deterministic.
    files = sorted(
        file.relative_to(workspace)
        for file in workspace.rglob("*")
        if file.is_file()
    )

    return files if files else []


def read_workspace_file(config: Config, relative_path: Path) -> str:
    """Safely read a file from Mind's controlled workspace."""
    target, error = _resolve_workspace_target(config, relative_path)

    if error is not None:
        return error

    assert target is not None

    if not target.exists():
        return f"Error: File '{relative_path}' not found."

    if not target.is_file():
        return f"Error: '{relative_path}' is a directory, not a file."

    try:
        # utf-8-sig handles Windows BOMs.
        # errors="replace" prevents crashes on odd file bytes.
        return target.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as error:
        return f"Error reading file: {error}"


def write_workspace_file(
    config: Config,
    relative_path: Path,
    content: str,
    overwrite: bool = False,
) -> str:
    """
    Safely write text to a workspace-relative file.

    This function is intentionally conservative because it is the boundary that
    turns Mind from a read-only assistant into a local-action assistant.
    """
    if len(content) > MAX_WORKSPACE_WRITE_CHARS:
        return (
            "Error: Content is too large. "
            f"Maximum allowed size is {MAX_WORKSPACE_WRITE_CHARS} characters."
        )

    target, error = _resolve_workspace_target(config, relative_path)

    if error is not None:
        return error

    assert target is not None

    raw_target = config.paths.workspace / relative_path

    if raw_target.is_symlink():
        return f"Error: Refusing to write through symlink '{relative_path}'."

    if target.exists() and target.is_dir():
        return f"Error: '{relative_path}' is a directory, not a file."

    if target.exists() and not overwrite:
        return (
            f"Error: File '{relative_path}' already exists. "
            "Set overwrite=true to replace it."
        )

    parent = target.parent

    if parent.exists() and not parent.is_dir():
        return f"Error: Parent path for '{relative_path}' is not a directory."

    try:
        parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as error:
        return f"Error writing file: {error}"

    action = "Overwrote" if overwrite else "Wrote"
    return f"{action} workspace file: {relative_path}"


def append_workspace_file(
    config: Config,
    relative_path: Path,
    content: str,
    create: bool = True,
) -> str:
    """
    Safely append text to a workspace-relative file.

    This uses the same workspace boundary as read/write operations. It can create
    the file by default because local-write permission and confirmation still
    control whether the tool is allowed to run.
    """
    if len(content) > MAX_WORKSPACE_WRITE_CHARS:
        return (
            "Error: Content is too large. "
            f"Maximum allowed size is {MAX_WORKSPACE_WRITE_CHARS} characters."
        )

    target, error = _resolve_workspace_target(config, relative_path)

    if error is not None:
        return error

    assert target is not None

    raw_target = config.paths.workspace / relative_path

    if raw_target.is_symlink():
        return f"Error: Refusing to append through symlink '{relative_path}'."

    if target.exists() and target.is_dir():
        return f"Error: '{relative_path}' is a directory, not a file."

    if not target.exists() and not create:
        return (
            f"Error: File '{relative_path}' not found. "
            "Set create=true to create it."
        )

    parent = target.parent

    if parent.exists() and not parent.is_dir():
        return f"Error: Parent path for '{relative_path}' is not a directory."

    try:
        parent.mkdir(parents=True, exist_ok=True)

        with target.open("a", encoding="utf-8") as file:
            file.write(content)
    except Exception as error:
        return f"Error appending file: {error}"

    return f"Appended to workspace file: {relative_path}"
