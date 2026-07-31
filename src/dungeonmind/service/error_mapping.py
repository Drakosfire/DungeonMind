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


def http_status_for(error: BaseException) -> int:
    for cls, status in _STATUS_BY_TYPE.items():
        if isinstance(error, cls):
            return status
    if isinstance(error, DungeonMindError):
        return 400
    return 500


def error_envelope(error: BaseException) -> dict[str, Any]:
    if isinstance(error, DungeonMindError):
        return {
            "error": {
                "code": error.code,
                "message": str(error),
                "details": dict(error.details or {}),
            }
        }
    return {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
