from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mind.core.config import Config
from mind.workspace import append_workspace_file


DEVLOG_PATH = Path("devlog.md")


def build_devlog_entry(
    summary: str,
    next_steps: list[str] | None = None,
) -> str:
    """Build one Markdown devlog entry."""
    today = datetime.now().astimezone().date().isoformat()
    clean_summary = summary.strip()

    lines = [
        f"## {today}",
        "",
        clean_summary,
    ]

    if next_steps:
        lines.extend(["", "Next steps:"])

        for step in next_steps:
            clean_step = step.strip()
            if clean_step:
                lines.append(f"- {clean_step}")

    lines.append("")

    return "\n".join(lines)


def append_project_devlog(
    config: Config,
    summary: str,
    next_steps: list[str] | None = None,
) -> str:
    """Append one project devlog entry to the controlled workspace devlog."""
    entry = build_devlog_entry(summary, next_steps)

    return append_workspace_file(
        config,
        DEVLOG_PATH,
        entry,
        create=True,
    )
