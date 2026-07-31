"""Map domain errors to sanitized HTTP envelopes."""

from __future__ import annotations

from typing import Any

from ..domain.errors import (
    CapabilityDeniedError,
    DocumentNotFoundError,
    DungeonMindError,
    HeadNotFoundError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
    ScopeResolutionError,
    ThreadContextMismatchError,
)

_STATUS_BY_TYPE: dict[type[BaseException], int] = {
    CapabilityDeniedError: 403,
    HeadNotFoundError: 404,
    RevisionNotFoundError: 404,
    DocumentNotFoundError: 404,
    ScopeResolutionError: 409,
    ThreadContextMismatchError: 409,
    IdempotencyConflictError: 409,
    InvalidLifecycleTransitionError: 409,
    PersistenceUnavailableError: 503,
    PersistenceIntegrityError: 500,
}

_PUBLIC_MESSAGES: dict[type[BaseException], str] = {
    PersistenceUnavailableError: "Persistence backend is temporarily unavailable.",
    PersistenceIntegrityError: "Stored data failed an integrity check.",
}

_DETAIL_ALLOWLIST = frozenset(
    {
        "reason",
        "world_id",
        "revision_id",
        "thread_id",
        "request_id",
        "expected",
        "actual",
        "embedding_run_id",
        "record_type",
        "record_id",
        "current_status",
        "requested_status",
    }
)


def http_status_for(error: BaseException) -> int:
    for cls, status in _STATUS_BY_TYPE.items():
        if isinstance(error, cls):
            return status
    if isinstance(error, DungeonMindError):
        return 400
    return 500


def _public_details(error: DungeonMindError) -> dict[str, Any]:
    if isinstance(error, (PersistenceUnavailableError, PersistenceIntegrityError)):
        details = error.details or {}
        return {
            key: details[key]
            for key in _DETAIL_ALLOWLIST
            if key in details and isinstance(details[key], (str, int, float, bool, type(None)))
        }
    return dict(error.details or {})


def error_envelope(error: BaseException) -> dict[str, Any]:
    if isinstance(error, DungeonMindError):
        message = _PUBLIC_MESSAGES.get(type(error))
        if message is None:
            for cls, public in _PUBLIC_MESSAGES.items():
                if isinstance(error, cls):
                    message = public
                    break
        return {
            "error": {
                "code": error.code,
                "message": message if message is not None else str(error),
                "details": _public_details(error),
            }
        }
    return {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
