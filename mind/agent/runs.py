from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mind.core.config import Config


RUN_ID_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"


@dataclass(frozen=True)
class AgentRunPaths:
    """
    Files created for one persisted agent run.

    Keeping these paths grouped makes it easier for the CLI to print or inspect
    saved run artifacts later.
    """

    run_id: str
    directory: Path
    metadata: Path
    prompt: Path
    trace: Path
    final_answer: Path


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _runs_root(config: Config) -> Path:
    """
    Return the root directory for persisted agent runs.

    This uses the database parent directory so runtime state stays under the
    existing data/ area without adding a new config field yet.
    """
    return config.paths.database.parent / "runs"


def create_agent_run_paths(config: Config) -> AgentRunPaths:
    """
    Create a unique directory and file paths for one agent run.

    The timestamp keeps run folders readable. The short UUID suffix prevents
    collisions when multiple runs start in the same second.
    """
    now = _utc_now()
    run_id = f"{now.strftime(RUN_ID_TIMESTAMP_FORMAT)}-{uuid4().hex[:8]}"
    directory = _runs_root(config) / run_id
    directory.mkdir(parents=True, exist_ok=False)

    return AgentRunPaths(
        run_id=run_id,
        directory=directory,
        metadata=directory / "metadata.json",
        prompt=directory / "prompt.txt",
        trace=directory / "trace.md",
        final_answer=directory / "final.md",
    )


def save_agent_run(
    config: Config,
    user_prompt: str,
    final_answer: str,
    trace_output: str | None,
    status: str,
    error: str | None = None,
) -> AgentRunPaths:
    """
    Persist one completed agent run to disk.

    This is intentionally file-based for now. It is simple, inspectable, easy to
    debug, and does not require expanding the SQLite schema before the run model
    stabilizes.
    """
    paths = create_agent_run_paths(config)
    now = _utc_now().isoformat()

    metadata = {
        "run_id": paths.run_id,
        "status": status,
        "started_at": now,
        "finished_at": now,
        "model": config.model.default,
        "provider": config.model.provider,
        "error": error,
    }

    paths.metadata.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    paths.prompt.write_text(user_prompt, encoding="utf-8")
    paths.final_answer.write_text(final_answer, encoding="utf-8")

    if trace_output is not None:
        paths.trace.write_text(trace_output, encoding="utf-8")
    else:
        paths.trace.write_text("Trace was not enabled for this run.\n", encoding="utf-8")

    return paths


def list_agent_runs(config: Config) -> list[Path]:
    """Return saved agent run directories, newest first."""
    root = _runs_root(config)

    if not root.exists():
        return []

    runs = [path for path in root.iterdir() if path.is_dir()]
    return sorted(runs, reverse=True)


def read_agent_run_metadata(run_dir: Path) -> dict[str, object] | None:
    """Read one run's metadata file if it exists and is valid JSON."""
    metadata_path = run_dir / "metadata.json"

    if not metadata_path.exists():
        return None

    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
