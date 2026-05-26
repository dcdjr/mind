from __future__ import annotations

from pathlib import Path

from mind.core.config import Config


MAX_CODEBASE_READ_CHARS = 80_000
MAX_CODEBASE_LIST_FILES = 500

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".pyright",
    "data",
    "workspace",
    "build",
    "dist",
    ".eggs",
}

IGNORED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
}


def _project_root(config: Config) -> Path:
    """Return the configured project root as an absolute path."""
    return config.project.root.resolve()


def _is_ignored_path(relative_path: Path) -> bool:
    """Return whether a project-relative path should be hidden from codebase tools."""
    parts = set(relative_path.parts)

    if parts & IGNORED_DIR_NAMES:
        return True

    if any(part.endswith(".egg-info") for part in relative_path.parts):
        return True

    if relative_path.suffix in IGNORED_FILE_SUFFIXES:
        return True

    return False


def _resolve_codebase_target(
    config: Config,
    relative_path: Path,
) -> tuple[Path | None, str | None]:
    """
    Resolve a project-relative path safely.

    Codebase tools are read-only, but they still need a hard path boundary so the
    model cannot inspect files outside the configured project root.
    """
    if str(relative_path).strip() in {"", "."}:
        return None, "Error: Codebase path cannot be empty."

    if relative_path.is_absolute():
        return (
            None,
            f"Error: Access denied. Absolute paths are not allowed: '{relative_path}'.",
        )

    if _is_ignored_path(relative_path):
        return (
            None,
            f"Error: Access denied. '{relative_path}' is ignored by codebase tools.",
        )

    root = _project_root(config)
    target = (root / relative_path).resolve()

    if not target.is_relative_to(root):
        return (
            None,
            f"Error: Access denied. '{relative_path}' is outside the project root.",
        )

    return target, None


def list_codebase_files(config: Config) -> list[Path]:
    """Return source-like files inside the configured project root."""
    root = _project_root(config)

    if not root.exists() or not root.is_dir():
        return []

    files: list[Path] = []

    for file in root.rglob("*"):
        try:
            relative_path = file.relative_to(root)
        except ValueError:
            continue

        if _is_ignored_path(relative_path):
            continue

        if file.is_symlink():
            continue

        if not file.is_file():
            continue

        files.append(relative_path)

    return sorted(files)[:MAX_CODEBASE_LIST_FILES]


def read_codebase_file(config: Config, relative_path: Path) -> str:
    """Safely read a project-relative text file from the configured codebase."""
    target, error = _resolve_codebase_target(config, relative_path)

    if error is not None:
        return error

    assert target is not None

    if not target.exists():
        return f"Error: File '{relative_path}' not found."

    if target.is_symlink():
        return f"Error: Refusing to read symlink '{relative_path}'."

    if not target.is_file():
        return f"Error: '{relative_path}' is a directory, not a file."

    try:
        raw_bytes = target.read_bytes()
    except Exception as error:
        return f"Error reading file: {error}"

    if b"\x00" in raw_bytes[:4096]:
        return f"Error: '{relative_path}' appears to be a binary file."

    try:
        contents = raw_bytes.decode("utf-8-sig", errors="replace")
    except Exception as error:
        return f"Error decoding file: {error}"

    if len(contents) > MAX_CODEBASE_READ_CHARS:
        return (
            contents[:MAX_CODEBASE_READ_CHARS].rstrip()
            + "\n[Codebase file truncated]"
        )

    return contents
