"""Evidence and source contracts (schemas ``dm_evidence_ref_v1``,
``dm_source_artifact_v1``, ``dm_source_revision_v1``).

Source artifacts are the evidentiary authority; the graph is durable
materialized knowledge derived from them. Source *identity* (hashes, revision
metadata, locators, anchors) is always durable even when the source *body*
lives in object storage (see Docs/Decisions/ADR-0001).

Body content hashes live on ``SourceRevision`` only. ``SourceArtifact`` is a
stable identity record; its optional ``current_revision_id`` is a
CAS-controlled pointer updated by typed lifecycle operations, not a body hash.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from .base import DungeonMindModel
from .vocabulary import Visibility

EVIDENCE_REF_SCHEMA = "dm_evidence_ref_v1"
SOURCE_ARTIFACT_SCHEMA = "dm_source_artifact_v1"
SOURCE_REVISION_SCHEMA = "dm_source_revision_v1"


class SourceDomain(StrEnum):
    """Broad provenance domains. Recap sources must carry campaign+session ids."""

    SESSION_RECAP = "session_recap"
    WORLDBUILDING = "worldbuilding"
    RULEBOOK = "rulebook"
    PREP = "prep"
    MANUAL = "manual"
    OTHER = "other"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class EvidenceRole(StrEnum):
    SUPPORT = "support"
    CONTRADICTION = "contradiction"
    CONTEXT = "context"


class EvidenceRef(DungeonMindModel):
    """A durable pointer from graph knowledge to its evidentiary basis."""

    schema_version: Literal["dm_evidence_ref_v1"] = EVIDENCE_REF_SCHEMA
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None = None
    source_domain: SourceDomain
    evidence_role: EvidenceRole = EvidenceRole.SUPPORT
    can_open_source: bool = True
    can_highlight_span: bool = False
    # Opaque pointer into the source body (object-storage key, doc anchor, etc.).
    locator: str | None = None
    uri: str | None = None


class SourceArtifact(DungeonMindModel):
    """A registered source of evidentiary authority (e.g. one recap document).

    Identity fields are immutable after create. Body hashes belong on
    ``SourceRevision``. ``current_revision_id`` may be advanced by a typed
    lifecycle operation; put/create is exact-replay idempotent only.
    """

    schema_version: Literal["dm_source_artifact_v1"] = SOURCE_ARTIFACT_SCHEMA
    source_artifact_id: str
    source_domain: SourceDomain
    world_id: str
    campaign_id: str | None = None
    # Required when source_domain == session_recap.
    session_id: str | None = None
    uri: str | None = None
    # CAS-controlled pointer to the current body revision; not a body hash.
    current_revision_id: str | None = None
    authority: str = "primary"  # primary | derived | reference (v1 vocabulary)
    visibility: Visibility = Visibility.GM
    status: SourceStatus = SourceStatus.ACTIVE
    created_at: datetime

    @model_validator(mode="after")
    def _session_recap_requires_campaign_and_session(self) -> Self:
        if self.source_domain is SourceDomain.SESSION_RECAP:
            if not self.campaign_id:
                raise ValueError("session_recap sources require campaign_id")
            if not self.session_id:
                raise ValueError("session_recap sources require session_id")
        return self


class SourceRevision(DungeonMindModel):
    """An immutable revision of a source artifact's body.

    The body may live in PostgreSQL, object storage (e.g. R2), or an external
    system; this record and its hash are always durable regardless.
    """

    schema_version: Literal["dm_source_revision_v1"] = SOURCE_REVISION_SCHEMA
    source_revision_id: str
    source_artifact_id: str
    content_sha256: str
    body_storage: Literal["postgres", "object_store", "external"] = "object_store"
    # Locator into body_storage. Required unless body_storage is postgres.
    locator: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _locator_required_unless_postgres(self) -> Self:
        if self.body_storage != "postgres" and not self.locator:
            raise ValueError(
                "locator is required when body_storage is not postgres"
            )
        return self
