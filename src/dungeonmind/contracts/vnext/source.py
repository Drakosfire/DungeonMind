from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from .common import (
    DomainMetadataEntry,
    NonBlankId,
    QualifiedTerm,
    Sha256Hex,
    VisibilityRequirement,
    _unique,
)


class SourceArtifactV3(DungeonMindModel):
    schema_version: Literal["dm_source_artifact_v3"] = "dm_source_artifact_v3"
    source_artifact_id: NonBlankId
    source_classification: QualifiedTerm
    current_revision_id: NonBlankId | None = None
    authority: Literal["primary", "derived", "reference"]
    visibility: VisibilityRequirement = Field(discriminator="kind")
    status: Literal["active", "superseded", "retracted"]
    uri: str | None = None
    foreign_refs: list[NonBlankId] = Field(default_factory=list)
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    _refs = field_validator("foreign_refs")(_unique)


class SourceRevisionV2(DungeonMindModel):
    schema_version: Literal["dm_source_revision_v2"] = "dm_source_revision_v2"
    source_revision_id: NonBlankId
    source_artifact_id: NonBlankId
    content_sha256: Sha256Hex
    body_storage: NonBlankId
    locator: str | None = None
    created_at: datetime


class EvidenceRefV3(DungeonMindModel):
    schema_version: Literal["dm_evidence_ref_v3"] = "dm_evidence_ref_v3"
    evidence_ref_id: NonBlankId
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId | None = None
    evidence_role: Literal["support", "contradiction", "context"]
    can_open_source: bool
    can_highlight_span: bool
    locator: str | None = None
    uri: str | None = None
    source_locator: str | None = None
    line_ref: str | None = None
    source_span_ref_id: NonBlankId | None = None
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)
