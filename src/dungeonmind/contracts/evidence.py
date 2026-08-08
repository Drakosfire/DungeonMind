"""Evidence and source contracts.

Historical (immutable) schemas:

* ``dm_evidence_ref_v1``
* ``dm_source_artifact_v1``
* ``dm_source_revision_v1``

Additive provenance v2 (ADR-0015):

* ``dm_evidence_ref_v2``
* ``dm_source_artifact_v2``
* ``dm_workspace_document_ref_v1``

Source artifacts are the evidentiary authority; the graph is durable
materialized knowledge derived from them. Source *identity* (hashes, revision
metadata, locators, anchors) is always durable even when the source *body*
lives in object storage (see Docs/Decisions/ADR-0001).

Body content hashes live on ``SourceRevision`` only. ``SourceArtifact`` /
``SourceArtifactV2`` are stable identity records; optional
``current_revision_id`` is a CAS-controlled pointer updated by typed lifecycle
operations, not a body hash.

V2 separates axes that v1 overloaded:

* ``source_domain_key`` (exact opaque producer classification)
  ≠ ``source_domain`` (optional generic DungeonMind provenance family)
* ``review_state`` (source-document standing)
  ≠ ``authority`` (evidentiary role)
  ≠ graph assertion ``canon_state``
* ``source_visibility_state`` (producer classification)
  ≠ ``visibility`` (DungeonMind access policy)
* evidence ``session_id`` ≠ fictional time
* ``workspace_document_ref`` ≠ ``source_artifact_id``
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .vocabulary import Visibility

EVIDENCE_REF_SCHEMA = "dm_evidence_ref_v1"
EVIDENCE_REF_V2_SCHEMA = "dm_evidence_ref_v2"
SOURCE_ARTIFACT_SCHEMA = "dm_source_artifact_v1"
SOURCE_ARTIFACT_V2_SCHEMA = "dm_source_artifact_v2"
SOURCE_REVISION_SCHEMA = "dm_source_revision_v1"
WORKSPACE_DOCUMENT_REF_SCHEMA = "dm_workspace_document_ref_v1"


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


class SourceAuthority(StrEnum):
    """Evidentiary / origin role of a source. Not source-document review state."""

    PRIMARY = "primary"
    DERIVED = "derived"
    REFERENCE = "reference"


class SourceReviewState(StrEnum):
    """Standing of the source *document*. Not evidentiary authority or graph canon."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    CANONICAL = "canonical"


def _reject_blank(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")


def _reject_blank_optional(value: str | None, label: str) -> None:
    if value is not None:
        _reject_blank(value, label)


def _validate_json_value(value: Any, *, path: str) -> None:
    """Reject anything a canonical JSON payload cannot round-trip."""
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be a finite JSON number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(f"{path} is not JSON-compatible")


class EvidenceRef(DungeonMindModel):
    """A durable pointer from graph knowledge to its evidentiary basis (v1)."""

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
    """A registered source of evidentiary authority (v1).

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


class WorkspaceDocumentRefV1(DungeonMindModel):
    """Foreign provenance link to a producer workspace document.

    Distinct from ``source_artifact_id``. Neither field is derived from the other.
    """

    schema_version: Literal["dm_workspace_document_ref_v1"] = (
        WORKSPACE_DOCUMENT_REF_SCHEMA
    )
    document_id: str
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_workspace_ref(self) -> Self:
        _reject_blank(self.document_id, "document_id")
        return self


class SourceArtifactV2(DungeonMindModel):
    """Lossless source-artifact provenance (v2).

    Every axis whose producer value may be unknown is required-but-nullable —
    there are no silent v1 migration defaults for authority or visibility.
    """

    schema_version: Literal["dm_source_artifact_v2"] = SOURCE_ARTIFACT_V2_SCHEMA
    source_artifact_id: str
    # Exact opaque producer classification. Never interpreted by the kernel.
    source_domain_key: str
    # Optional generic DungeonMind provenance family. Never inferred from key.
    source_domain: SourceDomain | None
    world_id: str
    campaign_id: str | None
    session_id: str | None
    uri: str | None
    current_revision_id: str | None
    authority: SourceAuthority | None
    visibility: Visibility | None
    artifact_kind: str | None
    document_class: str | None
    review_state: SourceReviewState | None
    # Opaque producer visibility classification. Not access policy.
    source_visibility_state: str | None
    workspace_document_ref: WorkspaceDocumentRefV1 | None
    lineage: dict[str, Any] = Field(default_factory=dict)
    status: SourceStatus
    created_at: datetime | None
    updated_at: datetime | None

    @model_validator(mode="after")
    def _validate_artifact_v2(self) -> Self:
        _reject_blank(self.source_artifact_id, "source_artifact_id")
        _reject_blank(self.source_domain_key, "source_domain_key")
        _reject_blank(self.world_id, "world_id")
        _reject_blank_optional(self.campaign_id, "campaign_id")
        _reject_blank_optional(self.session_id, "session_id")
        _reject_blank_optional(self.uri, "uri")
        _reject_blank_optional(self.current_revision_id, "current_revision_id")
        _reject_blank_optional(self.artifact_kind, "artifact_kind")
        _reject_blank_optional(self.document_class, "document_class")
        _reject_blank_optional(self.source_visibility_state, "source_visibility_state")
        _validate_json_value(self.lineage, path="lineage")
        if self.source_domain is SourceDomain.SESSION_RECAP:
            if not self.campaign_id:
                raise ValueError("session_recap sources require campaign_id")
            if not self.session_id:
                raise ValueError("session_recap sources require session_id")
        return self


class EvidenceRefV2(DungeonMindModel):
    """Lossless evidence pointer (v2). Locator forms remain independent."""

    schema_version: Literal["dm_evidence_ref_v2"] = EVIDENCE_REF_V2_SCHEMA
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None
    source_domain_key: str
    source_domain: SourceDomain | None
    evidence_role: EvidenceRole
    can_open_source: bool
    can_highlight_span: bool
    # Real-world session association. Never fictional time.
    session_id: str | None
    source_span_ref_id: str | None
    locator: str | None
    uri: str | None
    source_locator: str | None
    line_ref: str | None

    @model_validator(mode="after")
    def _validate_evidence_v2(self) -> Self:
        _reject_blank(self.evidence_ref_id, "evidence_ref_id")
        _reject_blank(self.source_artifact_id, "source_artifact_id")
        _reject_blank(self.source_domain_key, "source_domain_key")
        _reject_blank_optional(self.source_revision_id, "source_revision_id")
        _reject_blank_optional(self.session_id, "session_id")
        _reject_blank_optional(self.source_span_ref_id, "source_span_ref_id")
        _reject_blank_optional(self.locator, "locator")
        _reject_blank_optional(self.uri, "uri")
        _reject_blank_optional(self.source_locator, "source_locator")
        _reject_blank_optional(self.line_ref, "line_ref")
        return self


SourceArtifactRecord = SourceArtifact | SourceArtifactV2
EvidenceRefRecord = EvidenceRef | EvidenceRefV2
