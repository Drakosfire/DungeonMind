"""Typed failure model.

Adapters and services raise these; transport layers (API, CLI) map
``code`` to their own status vocabulary. Following the statblocks_v1
discipline: stable machine-readable codes, no stringly-typed branching.
"""

from typing import Any


class DungeonMindError(Exception):
    """Base for all DungeonMind failures. ``code`` is stable wire vocabulary."""

    code = "dungeonmind_error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message or self.code)
        self.details = details or {}


class RevisionNotFoundError(DungeonMindError):
    code = "revision_not_found"


class HeadNotFoundError(DungeonMindError):
    code = "head_not_found"


class StaleParentRevisionError(DungeonMindError):
    """CAS failure: the expected parent no longer equals the current head."""

    code = "stale_parent_revision"

    def __init__(
        self,
        message: str | None = None,
        *,
        world_id: str,
        expected_parent_revision_id: str | None,
        actual_head_revision_id: str | None,
    ) -> None:
        super().__init__(
            message
            or f"stale parent for world {world_id!r}: expected "
            f"{expected_parent_revision_id!r}, current head is {actual_head_revision_id!r}",
            details={
                "world_id": world_id,
                "expected_parent_revision_id": expected_parent_revision_id,
                "actual_head_revision_id": actual_head_revision_id,
            },
        )
        self.world_id = world_id
        self.expected_parent_revision_id = expected_parent_revision_id
        self.actual_head_revision_id = actual_head_revision_id


class ImmutableRevisionConflictError(DungeonMindError):
    """A revision with this content address already exists with different bytes."""

    code = "immutable_revision_conflict"


class IdempotencyConflictError(DungeonMindError):
    """Same operation key, different payload."""

    code = "idempotency_conflict"


class CapabilityDeniedError(DungeonMindError):
    """Fail-closed capability evaluation."""

    code = "capability_denied"


class ScopeResolutionError(DungeonMindError):
    """A read could not resolve one explicit world/revision scope."""

    code = "scope_resolution_error"


class DocumentNotFoundError(DungeonMindError):
    code = "document_not_found"


class ThreadContextMismatchError(DungeonMindError):
    """Thread binding or turn correlation violated (world/campaign/tenant/ids)."""

    code = "thread_context_mismatch"
