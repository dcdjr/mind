from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from mind.core.config import Config


VALID_MEMORY_STATUSES = {
    "confirmed",
    "auto_extracted",
    "rejected",
    "archived",
}


@dataclass(frozen=True)
class MemoryRecord:
    """A full memory row used by review/listing commands."""

    id: int
    text: str
    kind: str
    source: str
    status: str
    confidence: float
    created_at: str
    updated_at: str
    last_used_at: str | None
    use_count: int


def _normalize_memory_text(text: str) -> str:
    """Normalize memory text for deduplication."""
    normalized = text.strip().casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    # Trailing sentence punctuation should not make otherwise identical
    # memories distinct, but punctuation inside the sentence is preserved.
    normalized = normalized.rstrip(".!?")

    return normalized


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _serialize_embedding(embedding: list[float]) -> str:
    """
    Convert an embedding vector into JSON for SQLite storage.

    Embeddings are stored as JSON first because it is simple, inspectable, and
    good enough for the current scale of Mind. This can later become a binary
    blob or a real vector index if needed.
    """
    if not embedding:
        raise ValueError("Embedding cannot be empty.")

    cleaned_embedding: list[float] = []

    for value in embedding:
        # bool is technically a subclass of int in Python, but it should not be
        # accepted as an embedding value.
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Embedding values must be numeric.")

        cleaned_embedding.append(float(value))

    return json.dumps(cleaned_embedding)


def _deserialize_embedding(embedding_json: str) -> list[float]:
    """Convert a stored embedding JSON string back into a list of floats."""
    try:
        parsed = json.loads(embedding_json)
    except json.JSONDecodeError as error:
        raise ValueError("Stored embedding JSON is invalid.") from error

    if not isinstance(parsed, list) or not parsed:
        raise ValueError("Stored embedding must be a non-empty list.")

    embedding: list[float] = []

    for value in parsed:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Stored embedding contains non-numeric values.")

        embedding.append(float(value))

    return embedding


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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (memory_id, model),
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
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

    clean_status = status.strip()

    if clean_status not in VALID_MEMORY_STATUSES:
        raise ValueError(f"Invalid memory status: {status!r}.")

    normalized_text = _normalize_memory_text(clean_text)
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(config.paths.database) as conn:
        # INSERT OR IGNORE relies on normalized_text's UNIQUE constraint. A
        # duplicate memory is a no-op instead of an error because callers use
        # the boolean return value to decide what to print.
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
                clean_status,
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

    Any stored embeddings for the memory are removed first because embeddings are
    derived data and should not outlive their source memory.
    """
    init_db(config)

    with sqlite3.connect(config.paths.database) as conn:
        conn.execute(
            """
            DELETE FROM memory_embeddings
            WHERE memory_id = ?
            """,
            (memory_id,),
        )

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


def store_memory_embedding(
    config: Config,
    memory_id: int,
    model: str,
    embedding: list[float],
) -> bool:
    """
    Store or replace an embedding for one memory/model pair.

    Returns True if the memory exists and the embedding was stored. Returns False
    if the memory ID does not exist. This keeps the function consistent with the
    rest of the memory store API, where missing records usually return False.
    """
    init_db(config)

    clean_model = model.strip()

    if not clean_model:
        raise ValueError("Embedding model name cannot be empty.")

    embedding_json = _serialize_embedding(embedding)
    now = _utc_now_iso()

    with sqlite3.connect(config.paths.database) as conn:
        memory_exists_row = conn.execute(
            """
            SELECT 1
            FROM memories
            WHERE id = ?
            LIMIT 1
            """,
            (memory_id,),
        ).fetchone()

        if memory_exists_row is None:
            return False

        # Upsert lets embedding regeneration replace stale vectors after a
        # model change or a repaired provider response without duplicating rows.
        conn.execute(
            """
            INSERT INTO memory_embeddings (
                memory_id,
                model,
                embedding_json,
                created_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(memory_id, model)
            DO UPDATE SET
                embedding_json = excluded.embedding_json,
                created_at = excluded.created_at
            """,
            (
                memory_id,
                clean_model,
                embedding_json,
                now,
            ),
        )

    return True


def get_memory_embedding(
    config: Config,
    memory_id: int,
    model: str,
) -> list[float] | None:
    """Return one stored embedding vector, or None if it does not exist."""
    init_db(config)

    clean_model = model.strip()

    if not clean_model:
        raise ValueError("Embedding model name cannot be empty.")

    with sqlite3.connect(config.paths.database) as conn:
        row = conn.execute(
            """
            SELECT embedding_json
            FROM memory_embeddings
            WHERE memory_id = ?
              AND model = ?
            """,
            (
                memory_id,
                clean_model,
            ),
        ).fetchone()

    if row is None:
        return None

    return _deserialize_embedding(row[0])


def list_memory_embeddings(
    config: Config,
    model: str,
) -> list[tuple[int, str, list[float]]]:
    """
    Return active memories with stored embeddings for the given model.

    The returned shape is:
        (memory_id, memory_text, embedding)

    Retrieval needs both the vector for ranking and the text for displaying or
    injecting the result into the prompt.
    """
    init_db(config)

    clean_model = model.strip()

    if not clean_model:
        raise ValueError("Embedding model name cannot be empty.")

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.text, e.embedding_json
            FROM memories AS m
            INNER JOIN memory_embeddings AS e
                ON e.memory_id = m.id
            WHERE e.model = ?
              AND m.status IN ('confirmed', 'auto_extracted')
            ORDER BY m.id ASC
            """,
            (clean_model,),
        ).fetchall()

    results: list[tuple[int, str, list[float]]] = []

    # Deserialize after the query so corrupt rows fail at the boundary where
    # vectors leave storage and become retrieval inputs.
    for memory_id, memory_text, embedding_json in rows:
        results.append(
            (
                memory_id,
                memory_text,
                _deserialize_embedding(embedding_json),
            )
        )

    return results


def list_memories_missing_embeddings(
    config: Config,
    model: str,
) -> list[tuple[int, str]]:
    """
    Return active memories that do not yet have an embedding for the model.

    The LEFT JOIN is intentional: it finds memories with no matching row for
    exactly this model while still allowing the same memory to have embeddings
    from other models.
    """
    init_db(config)

    clean_model = model.strip()

    if not clean_model:
        raise ValueError("Embedding model name cannot be empty.")

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.text
            FROM memories AS m
            LEFT JOIN memory_embeddings AS e
                ON e.memory_id = m.id
               AND e.model = ?
            WHERE e.memory_id IS NULL
              AND m.status IN ('confirmed', 'auto_extracted')
            ORDER BY m.id ASC
            """,
            (clean_model,),
        ).fetchall()

    return [(row[0], row[1]) for row in rows]


def list_memory_records(
    config: Config,
    status: str | None = None,
) -> list[MemoryRecord]:
    """
    Return memory records with review metadata.

    If status is provided, only memories with that exact status are returned.
    This is meant for CLI review commands, not prompt injection.
    """
    init_db(config)

    query = """
        SELECT
            id,
            text,
            kind,
            source,
            status,
            confidence,
            created_at,
            updated_at,
            last_used_at,
            use_count
        FROM memories
    """
    params: tuple[str, ...] = ()

    if status is not None:
        clean_status = status.strip()

        if clean_status not in VALID_MEMORY_STATUSES:
            raise ValueError(f"Invalid memory status: {status!r}.")

        query += " WHERE status = ?"
        params = (clean_status,)

    query += " ORDER BY id ASC"

    with sqlite3.connect(config.paths.database) as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        MemoryRecord(
            id=row[0],
            text=row[1],
            kind=row[2],
            source=row[3],
            status=row[4],
            confidence=row[5],
            created_at=row[6],
            updated_at=row[7],
            last_used_at=row[8],
            use_count=row[9],
        )
        for row in rows
    ]


def update_memory_status(
    config: Config,
    memory_id: int,
    status: str,
) -> bool:
    """Update one memory's review status."""
    init_db(config)

    clean_status = status.strip()

    if clean_status not in VALID_MEMORY_STATUSES:
        raise ValueError(f"Invalid memory status: {status!r}.")

    now = _utc_now_iso()

    with sqlite3.connect(config.paths.database) as conn:
        cursor = conn.execute(
            """
            UPDATE memories
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                clean_status,
                now,
                memory_id,
            ),
        )

    return cursor.rowcount > 0


def confirm_memory(config: Config, memory_id: int) -> bool:
    """Mark a memory as confirmed."""
    return update_memory_status(config, memory_id, "confirmed")


def reject_memory(config: Config, memory_id: int) -> bool:
    """Mark a memory as rejected without deleting it."""
    return update_memory_status(config, memory_id, "rejected")


def archive_memory(config: Config, memory_id: int) -> bool:
    """Mark a memory as archived without deleting it."""
    return update_memory_status(config, memory_id, "archived")
