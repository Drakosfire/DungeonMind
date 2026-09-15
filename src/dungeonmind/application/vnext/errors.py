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
