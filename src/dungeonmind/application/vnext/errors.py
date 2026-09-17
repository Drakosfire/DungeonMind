"""Application-layer structural integrity errors for vNext knowledge parsing."""

from __future__ import annotations

from dungeonmind.domain.errors import PersistenceIntegrityError


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
