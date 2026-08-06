"""Map domain errors to sanitized HTTP envelopes."""

from __future__ import annotations

from typing import Any

from ..domain.errors import (
    CapabilityDeniedError,
    ContributionMaterializationError,
    ContributionReviewNotFoundError,
    DocumentNotFoundError,
    DungeonMindError,
    FictionalTimeIntegrityError,
    FinalizedReviewPublicationOutcomeUnknownError,
    HeadNotFoundError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
    ScopeResolutionError,
    StaleParentRevisionError,
    ThreadContextMismatchError,
)

_STATUS_BY_TYPE: dict[type[BaseException], int] = {
    CapabilityDeniedError: 403,
    ContributionReviewNotFoundError: 404,
    HeadNotFoundError: 404,
    RevisionNotFoundError: 404,
    DocumentNotFoundError: 404,
    ScopeResolutionError: 409,
    ThreadContextMismatchError: 409,
    StaleParentRevisionError: 409,
    IdempotencyConflictError: 409,
    InvalidLifecycleTransitionError: 409,
    ContributionMaterializationError: 409,
    FictionalTimeIntegrityError: 409,
    FinalizedReviewPublicationOutcomeUnknownError: 503,
    PersistenceUnavailableError: 503,
    PersistenceIntegrityError: 500,
}

_PUBLIC_MESSAGES: dict[type[BaseException], str] = {
    PersistenceUnavailableError: "Persistence backend is temporarily unavailable.",
    PersistenceIntegrityError: "Stored data failed an integrity check.",
}

_PUBLICATION_MESSAGES: dict[type[BaseException], str] = {
    CapabilityDeniedError: "Publication access denied.",
    ContributionReviewNotFoundError: "Finalized contribution review was not found.",
    RevisionNotFoundError: "Pinned graph revision was not found.",
    StaleParentRevisionError: "Publication lost the expected-parent race.",
    IdempotencyConflictError: "Publication identity conflicts with requested content.",
    ContributionMaterializationError: "Finalized review could not be materialized.",
    FinalizedReviewPublicationOutcomeUnknownError: (
        "Publication outcome is unknown. Retrying the same request is safe."
    ),
}

_FICTIONAL_TIME_MESSAGES: dict[type[BaseException], str] = {
    CapabilityDeniedError: "Fictional-time query access denied.",
    RevisionNotFoundError: "Pinned graph revision was not found.",
    FictionalTimeIntegrityError: "Fictional-time query integrity validation failed.",
}

_DETAIL_ALLOWLIST = frozenset(
    {
        "reason",
        "world_id",
        "revision_id",
        "object_id",
        "thread_id",
        "request_id",
        "expected",
        "actual",
        "embedding_run_id",
        "record_type",
        "record_id",
        "current_status",
        "requested_status",
        "review_id",
        "operation_id",
        "expected_parent_revision_id",
        "actual_head_revision_id",
        "expected_published_revision_id",
        "retry_safe",
    }
)

_SAFE_MATERIALIZATION_REASONS = frozenset(
    {
        "accepted_assertion_missing_graph_evidence",
        "accepted_evidence_conflict",
        "duplicate_relationship_triple",
        "orphan_accepted_assertion",
        "output_graph_validation",
        "parent_assertion_id_collision",
        "parent_binding_mismatch",
        "parent_evidence_id_collision",
        "parent_reload_validation",
        "preexisting_relationship_triple",
        "relationship_id_collision",
        "state_reload_validation",
        "unsupported_graph_schema",
        "unsupported_field_shape",
    }
)


def http_status_for(error: BaseException) -> int:
    for cls, status in _STATUS_BY_TYPE.items():
        if isinstance(error, cls):
            return status
    if isinstance(error, DungeonMindError):
        return 400
    return 500


def _public_details(error: DungeonMindError, *, host: str) -> dict[str, Any]:
    if host == "publication" and isinstance(error, ContributionMaterializationError):
        reason = error.details.get("reason")
        return (
            {"reason": reason}
            if isinstance(reason, str) and reason in _SAFE_MATERIALIZATION_REASONS
            else {}
        )
    if host == "fictional_time" and isinstance(error, FictionalTimeIntegrityError):
        details = error.details or {}
        out: dict[str, Any] = {}
        reason = details.get("reason")
        if isinstance(reason, str):
            out["reason"] = reason
        object_id = details.get("object_id")
        if isinstance(object_id, str):
            out["object_id"] = object_id
        return out
    if isinstance(error, (PersistenceUnavailableError, PersistenceIntegrityError)):
        details = error.details or {}
        return {
            key: details[key]
            for key in _DETAIL_ALLOWLIST
            if key in details and isinstance(details[key], (str, int, float, bool, type(None)))
        }
    if host == "fictional_time" and isinstance(error, RevisionNotFoundError):
        details = error.details or {}
        return {
            key: details[key]
            for key in ("world_id", "revision_id")
            if key in details and isinstance(details[key], str)
        }
    return dict(error.details or {})


def _error_envelope(error: BaseException, *, host: str) -> dict[str, Any]:
    if isinstance(error, DungeonMindError):
        if host == "publication":
            messages = _PUBLICATION_MESSAGES
        elif host == "fictional_time":
            messages = _FICTIONAL_TIME_MESSAGES
        else:
            messages = {}
        message = messages.get(type(error))
        if message is None:
            for cls, public in _PUBLIC_MESSAGES.items():
                if isinstance(error, cls):
                    message = public
                    break
        return {
            "error": {
                "code": error.code,
                "message": message if message is not None else str(error),
                "details": _public_details(error, host=host),
            }
        }
    return {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }


def error_envelope(error: BaseException) -> dict[str, Any]:
    """Map errors for the existing hosts without publication-specific wording."""

    return _error_envelope(error, host="default")


def publication_error_envelope(error: BaseException) -> dict[str, Any]:
    """Map errors for the finalized-review publication host."""

    return _error_envelope(error, host="publication")


def fictional_time_error_envelope(error: BaseException) -> dict[str, Any]:
    """Map errors for the fictional-time shadow query host."""

    return _error_envelope(error, host="fictional_time")
