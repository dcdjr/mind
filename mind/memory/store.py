from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import re

from mind.core.config import Config


def _normalize_memory_text(text: str) -> str:
    """Normalize memory text for deduplication."""
    normalized = text.strip().casefold()
    # Regex to replace one or more consecutive spaces with one space
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.rstrip(".!?")

    return normalized


def format_memories_for_prompt(memories: list[tuple[int, str]]) -> str | None:
    """Format saved memories for inclusion in the system prompt"""
    if not memories:
        return None

    lines = ["Saved memories about the user and project:"]

    for _, memory_text in memories:
        lines.append(f"- {memory_text}")

    return "\n".join(lines)


def init_db(config: Config) -> None:
    """Create Mind's SQLite database and required tables if they do not exist."""
    db_path = config.paths.database
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                use_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def add_memory(
    config: Config,
    text: str,
    kind: str = "general",
    source: str = "manual",
    status: str = "confirmed",
    confidence: float = 1.0,
) -> bool:
    """Store a single memory in Mind's SQLite database."""
    init_db(config)

    clean_text = text.strip()

    if not clean_text:
        return False

    normalized_text = _normalize_memory_text(clean_text)
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(config.paths.database) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO memories (
                text, 
                normalized_text,
                kind,
                source,
                status,
                confidence,
                created_at,
                updated_at,
                last_used_at,
                use_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_text,
                normalized_text,
                kind,
                source,
                status,
                confidence,
                now,
                now,
                None,
                0,
            ),
        )

    return cursor.rowcount > 0


def list_memories(config: Config) -> list[tuple[int, str]]:
    """Return active memories in insertion order."""
    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT id, text
            FROM memories
            WHERE status IN ('confirmed', 'auto_extracted')
            ORDER BY id ASC
            """
        ).fetchall()

    return [(row[0], row[1]) for row in rows]


def delete_memory(config: Config, memory_id: int) -> bool:
    """
    Delete a memory by database ID.

    Returns True if a memory was deleted, otherwise False.
    """
    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        cursor = conn.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        )

        return cursor.rowcount > 0


def memory_exists(config: Config, text: str) -> bool:
    """Returns True if a memory with the same text already exists."""
    init_db(config)

    normalized_text = _normalize_memory_text(text)

    with sqlite3.connect(config.paths.database) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM memories
            WHERE normalized_text = ?
            LIMIT 1
            """,
            (normalized_text,),
        ).fetchone()

    return row is not None
