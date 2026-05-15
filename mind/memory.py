from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from mind.config import Config


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
                created_at TEXT NOT NULL
            )
            """
        )


def add_memory(config: Config, text: str) -> None:
    """Store a single memory in Mind's SQLite database."""
    init_db(config)

    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(config.paths.database) as conn:
        conn.execute(
            """
            INSERT INTO memories (text, created_at)
            VALUES (?, ?)
            """,
            (text, created_at),
        )


def list_memories(config: Config) -> list[tuple[int, str]]:
    """Return all stored memories in insertion order."""
    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT id, text
            FROM memories
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

    with sqlite3.connect(config.paths.database) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM memories
            WHERE text = ?
            LIMIT 1
            """,
            (text,),
        ).fetchone()

    return row is not None
