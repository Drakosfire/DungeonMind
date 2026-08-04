"""HTTP status and sanitization contract for publication failures."""

from __future__ import annotations

import pytest

from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    ContributionMaterializationError,
    ContributionReviewNotFoundError,
    FinalizedReviewPublicationOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from dungeonmind.service.error_mapping import (
    http_status_for,
    publication_error_envelope,
)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (CapabilityDeniedError("secret"), 403, "capability_denied"),
        (ContributionReviewNotFoundError("review:missing"), 404, "contribution_review_not_found"),
        (RevisionNotFoundError("rev:missing"), 404, "revision_not_found"),
        (
            StaleParentRevisionError(
                world_id="world:test",
                expected_parent_revision_id="rev:parent",
                actual_head_revision_id="rev:other",
            ),
            409,
            "stale_parent_revision",
        ),
        (IdempotencyConflictError("conflict"), 409, "idempotency_conflict"),
        (
            ContributionMaterializationError(
                "source-sentinel",
                details={"summary": "campaign-prose-sentinel"},
            ),
            409,
            "contribution_materialization_error",
        ),
        (
            FinalizedReviewPublicationOutcomeUnknownError(
                world_id="world:test",
                review_id="review:test",
                operation_id="reviewop:test",
                expected_published_revision_id="rev:expected",
                reason="publication_attempt_or_recovery_probe_failed",
            ),
            503,
            "finalized_review_publication_outcome_unknown",
        ),
        (PersistenceUnavailableError("dsn-sentinel"), 503, "persistence_unavailable"),
        (PersistenceIntegrityError("sql-sentinel"), 500, "persistence_integrity_error"),
    ],
)
def test_publication_error_status_and_code_mapping(error, status: int, code: str) -> None:
    envelope = publication_error_envelope(error)
    assert http_status_for(error) == status
    assert envelope["error"]["code"] == code


def test_outcome_unknown_has_exact_retry_safe_public_contract() -> None:
    error = FinalizedReviewPublicationOutcomeUnknownError(
        world_id="world:test",
        review_id="review:test",
        operation_id="reviewop:test",
        expected_published_revision_id="rev:expected",
        reason="publication_attempt_or_recovery_probe_failed",
    )
    assert publication_error_envelope(error) == {
        "error": {
            "code": "finalized_review_publication_outcome_unknown",
            "message": "Publication outcome is unknown. Retrying the same request is safe.",
            "details": {
                "world_id": "world:test",
                "review_id": "review:test",
                "operation_id": "reviewop:test",
                "expected_published_revision_id": "rev:expected",
                "reason": "publication_attempt_or_recovery_probe_failed",
                "retry_safe": True,
            },
        }
    }


def test_materialization_and_persistence_errors_do_not_leak_sentinels() -> None:
    materialization = publication_error_envelope(
        ContributionMaterializationError(
            "source-locator-sentinel",
            details={
                "summary": "campaign-prose-sentinel",
                "graph_payload": "graph-sentinel",
            },
        )
    )
    persistence = publication_error_envelope(
        PersistenceIntegrityError(
            "sql-sentinel connection-string-sentinel",
            details={"sql": "sql-sentinel", "path": "filesystem-sentinel"},
        )
    )
    rendered = str(materialization) + str(persistence)
    assert "source-locator-sentinel" not in rendered
    assert "campaign-prose-sentinel" not in rendered
    assert "graph-sentinel" not in rendered
    assert "sql-sentinel" not in rendered
    assert "connection-string-sentinel" not in rendered
    assert "filesystem-sentinel" not in rendered


def test_unexpected_error_is_empty_and_sanitized() -> None:
    envelope = publication_error_envelope(RuntimeError("unexpected-secret-sentinel"))
    assert envelope == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
