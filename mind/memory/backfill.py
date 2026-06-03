from __future__ import annotations

from dataclasses import dataclass

from mind.core.config import Config
from mind.core.embeddings import embed_text
from mind.memory.store import (
    list_memories_missing_embeddings,
    store_memory_embedding,
)


@dataclass(frozen=True)
class BackfillError:
    """One memory that failed during embedding backfill."""
    memory_id: int
    message: str


@dataclass(frozen=True)
class BackfillResult:
    """Summary of one memory embedding backfill run."""
    model: str
    total_missing: int
    succeeded: int
    failed: int
    errors: list[BackfillError]


def backfill_embeddings(config: Config) -> BackfillResult:
    """
    Generate and store embeddings for active memories missing them.

    This is a batch workflow: one failed memory should be recorded and skipped
    without stopping the rest of the backfill.
    """
    model = config.embeddings.model
    missing = list_memories_missing_embeddings(config, model)

    succeeded = 0
    failed = 0
    errors: list[BackfillError] = []

    for memory_id, memory_text in missing:
        try:
            embedding = embed_text(config, memory_text)
            stored = store_memory_embedding(config, memory_id, model, embedding)

            if stored:
                succeeded += 1
            else:
                failed += 1
                errors.append(
                    BackfillError(
                        memory_id=memory_id,
                        message="Memory no longer exists or embedding could not be stored.",
                    )
                )

        except Exception as error:
            failed += 1
            errors.append(
                BackfillError(
                    memory_id=memory_id,
                    message=f"{type(error).__name__}: {error}",
                )
            )

    return BackfillResult(
        model=model,
        total_missing=len(missing),
        succeeded=succeeded,
        failed=failed,
        errors=errors,
    )
