"""Embedding-run lifecycle state machine and exact-retry semantics."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import EmbeddingRun, EmbeddingRunStatus
from dungeonmind.domain.errors import (
    DocumentNotFoundError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
)
from dungeonmind.infrastructure.memory import InMemoryEmbeddingRunRepository

NOW = datetime(2026, 7, 29, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


def _running(**overrides: object) -> EmbeddingRun:
    base: dict[str, object] = {
        "run_id": "erun:1",
        "embedding_model": "test-model",
        "embedding_model_revision": "rev-1",
        "embedding_dimensions": 8,
        "embedding_recipe": "raw-v1",
        "created_at": NOW,
    }
    base.update(overrides)
    return EmbeddingRun(**base)  # type: ignore[arg-type]


def test_valid_begin_and_exact_retry_while_running() -> None:
    runs = InMemoryEmbeddingRunRepository()
    run = _running()
    assert runs.begin(run).status is EmbeddingRunStatus.RUNNING
    assert runs.begin(run).status is EmbeddingRunStatus.RUNNING


def test_begin_retry_after_completion() -> None:
    runs = InMemoryEmbeddingRunRepository()
    run = _running()
    runs.begin(run)
    completed = runs.complete("erun:1", completed_at=NOW)
    assert completed.status is EmbeddingRunStatus.COMPLETED
    again = runs.begin(run)
    assert again.status is EmbeddingRunStatus.COMPLETED
    assert again.completed_at == NOW


def test_begin_retry_after_failure() -> None:
    runs = InMemoryEmbeddingRunRepository()
    run = _running()
    runs.begin(run)
    failed = runs.fail("erun:1", completed_at=NOW)
    assert failed.status is EmbeddingRunStatus.FAILED
    again = runs.begin(run)
    assert again.status is EmbeddingRunStatus.FAILED


def test_conflicting_immutable_metadata_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    with pytest.raises(IdempotencyConflictError):
        runs.begin(_running(embedding_dimensions=16))


def test_begin_with_terminal_status_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    with pytest.raises((ValidationError, InvalidLifecycleTransitionError)):
        runs.begin(
            EmbeddingRun(
                run_id="erun:1",
                embedding_model="test-model",
                embedding_model_revision="rev-1",
                embedding_dimensions=8,
                embedding_recipe="raw-v1",
                status=EmbeddingRunStatus.COMPLETED,
                created_at=NOW,
                completed_at=NOW,
            )
        )


def test_running_with_terminal_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        EmbeddingRun(
            run_id="erun:1",
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            status=EmbeddingRunStatus.RUNNING,
            created_at=NOW,
            completed_at=NOW,
        )


def test_completed_without_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        EmbeddingRun(
            run_id="erun:1",
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            status=EmbeddingRunStatus.COMPLETED,
            created_at=NOW,
            completed_at=None,
        )


def test_complete_from_running_and_exact_retry() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    first = runs.complete("erun:1", completed_at=NOW)
    second = runs.complete("erun:1", completed_at=LATER)
    assert first.status is EmbeddingRunStatus.COMPLETED
    assert second.completed_at == NOW
    assert second.completed_at != LATER


def test_fail_from_running_and_exact_retry() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    first = runs.fail("erun:1", completed_at=NOW)
    second = runs.fail("erun:1", completed_at=LATER)
    assert first.status is EmbeddingRunStatus.FAILED
    assert second.completed_at == NOW


def test_complete_after_failure_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    runs.fail("erun:1", completed_at=NOW)
    with pytest.raises(InvalidLifecycleTransitionError) as exc:
        runs.complete("erun:1", completed_at=LATER)
    assert exc.value.details["current_status"] == "failed"
    assert exc.value.details["requested_status"] == "completed"


def test_fail_after_completion_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    runs.complete("erun:1", completed_at=NOW)
    with pytest.raises(InvalidLifecycleTransitionError):
        runs.fail("erun:1", completed_at=LATER)


def test_supersede_from_completed_and_failed() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    runs.complete("erun:1", completed_at=NOW)
    superseded = runs.supersede("erun:1", completed_at=LATER)
    assert superseded.status is EmbeddingRunStatus.SUPERSEDED
    assert superseded.completed_at == LATER

    runs2 = InMemoryEmbeddingRunRepository()
    runs2.begin(_running(run_id="erun:2"))
    runs2.fail("erun:2", completed_at=NOW)
    assert runs2.supersede("erun:2", completed_at=LATER).status is EmbeddingRunStatus.SUPERSEDED


def test_supersede_from_running_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    runs.begin(_running())
    with pytest.raises(InvalidLifecycleTransitionError):
        runs.supersede("erun:1", completed_at=NOW)


def test_missing_run_not_found() -> None:
    runs = InMemoryEmbeddingRunRepository()
    with pytest.raises(DocumentNotFoundError):
        runs.complete("erun:missing", completed_at=NOW)
