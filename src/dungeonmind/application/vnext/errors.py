"""Application-layer structural integrity errors for vNext knowledge parsing."""

from __future__ import annotations

from typing import Any

from dungeonmind.domain.errors import DungeonMindError, PersistenceIntegrityError


class RevisionStructuralIntegrityError(PersistenceIntegrityError):
    """Raised when a revision's decoded content violates structural integrity constraints.

    Conditions include:
    - duplicate entity, assertion, alias, or evidence IDs;
    - missing assertion subject entity;
    - missing entity-ref target entity;
    - missing assertion evidence ref;
    - missing alias entity;
    - missing alias evidence ref;
    - payload hash or schema disagreement with the KnowledgeRevision header.
    """

    code = "revision_structural_integrity_error"


class LegacyCompatibilityIntegrityError(RevisionStructuralIntegrityError):
    """Raised when a legacy stored revision fails compatibility verification or decoding."""

    code = "legacy_compatibility_integrity_error"


class KnowledgeReadContextIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when read context identity or pinning checks fail."""

    code = "knowledge_read_context_integrity_error"


class CandidateAdmissionIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when candidate admission preconditions are violated."""

    code = "candidate_admission_integrity_error"


class EntityReadIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when exact/complete entity assembly cannot complete safely."""

    code = "entity_read_integrity_error"


class NeighborhoodReadIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when bounded neighborhood traversal cannot complete safely."""

    code = "neighborhood_read_integrity_error"


class EvidenceReadIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when exact evidence/support assembly cannot complete safely."""

    code = "evidence_read_integrity_error"


class SearchReadIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when deterministic indexed search cannot complete safely."""

    code = "search_read_integrity_error"


class GovernedMaterializationIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when generic governed materialization cannot complete safely."""

    code = "governed_materialization_integrity_error"

    def __init__(self, reason: str, *, details: dict[str, Any] | None = None) -> None:
        materialization_details: dict[str, Any] = {"reason": reason}
        if details:
            materialization_details.update(details)
        super().__init__(
            "generic governed materialization failed",
            details=materialization_details,
        )
        self.reason = reason


class KnowledgePublicationIntegrityError(PersistenceIntegrityError):
    """Fail-closed error when a governed materialization cannot be bound for publication."""

    code = "knowledge_publication_integrity_error"

    def __init__(self, reason: str, *, details: dict[str, Any] | None = None) -> None:
        publication_details: dict[str, Any] = {"reason": reason}
        if details:
            publication_details.update(details)
        super().__init__(
            "native knowledge publication failed",
            details=publication_details,
        )
        self.reason = reason


class KnowledgeStaleParentRevisionError(DungeonMindError):
    """CAS failure: expected parent is not the current native knowledge head."""

    code = "knowledge_stale_parent_revision"

    def __init__(
        self,
        message: str | None = None,
        *,
        space_id: str,
        expected_parent_revision_id: str | None,
        actual_head_revision_id: str | None,
    ) -> None:
        super().__init__(
            message
            or (
                f"stale parent for space {space_id!r}: expected "
                f"{expected_parent_revision_id!r}, current head is {actual_head_revision_id!r}"
            ),
            details={
                "space_id": space_id,
                "expected_parent_revision_id": expected_parent_revision_id,
                "actual_head_revision_id": actual_head_revision_id,
            },
        )
        self.space_id = space_id
        self.expected_parent_revision_id = expected_parent_revision_id
        self.actual_head_revision_id = actual_head_revision_id


class KnowledgePublicationIdempotencyConflictError(DungeonMindError):
    code = "knowledge_publication_idempotency_conflict"

    def __init__(self, *, space_id: str, publication_id: str) -> None:
        super().__init__(
            "publication identity is already bound to a different command",
            details={"space_id": space_id, "publication_id": publication_id},
        )
        self.space_id = space_id
        self.publication_id = publication_id


class KnowledgePublicationOutcomeUnknownError(DungeonMindError):
    code = "knowledge_publication_outcome_unknown"

    def __init__(
        self, *, space_id: str, publication_id: str,
        expected_published_revision_id: str, reason: str,
    ) -> None:
        super().__init__(
            "knowledge publication outcome is unknown",
            details={
                "space_id": space_id,
                "publication_id": publication_id,
                "expected_published_revision_id": expected_published_revision_id,
                "retry_safe": True,
                "reason": reason,
            },
        )
        self.space_id = space_id
        self.publication_id = publication_id
        self.expected_published_revision_id = expected_published_revision_id
        self.retry_safe = True
