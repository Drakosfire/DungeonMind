"""Additive immutable native text-source and evidence admission contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..base import DungeonMindModel
from .common import (
    DomainMetadataEntry,
    NonBlankId,
    QualifiedTerm,
    Sha256Hex,
    VisibilityRequirement,
    _unique,
)
from .publication import KnowledgePublicationReceipt

MAX_NATIVE_TEXT_BYTES = 1_048_576
MAX_NATIVE_TEXT_SPANS = 64
NATIVE_TEXT_BODY_STORAGE = "dm_native_utf8_body_v1"


class NativeTextSourceOriginV1(DungeonMindModel):
    """Optional opaque link to the caller's separately owned immutable revision."""

    namespace: NonBlankId
    object_id: NonBlankId
    revision_id: NonBlankId


class NativeTextEvidenceSpanRequestV1(DungeonMindModel):
    """One caller-local byte interval requested as native evidence."""

    client_ref: NonBlankId
    evidence_role: Literal["support", "contradiction", "context"]
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    expected_slice_sha256: Sha256Hex
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _nonempty(self) -> NativeTextEvidenceSpanRequestV1:
        if self.start_byte >= self.end_byte:
            raise ValueError("span must be a nonempty half-open byte interval")
        return self


class NativeTextSourceAdmissionV1(DungeonMindModel):
    """One bounded operation creating one immutable text artifact/revision."""

    schema_version: Literal["dm_native_text_source_admission_v1"] = (
        "dm_native_text_source_admission_v1"
    )
    space_id: NonBlankId
    admission_id: NonBlankId
    expected_parent_revision_id: NonBlankId
    created_at: datetime
    body_text: str
    expected_body_sha256: Sha256Hex
    source_classification: QualifiedTerm
    authority: Literal["primary", "derived", "reference"]
    visibility: VisibilityRequirement = Field(discriminator="kind")
    foreign_refs: list[NonBlankId] = Field(default_factory=list)
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)
    origin: NativeTextSourceOriginV1 | None = None
    spans: list[NativeTextEvidenceSpanRequestV1] = Field(
        min_length=1, max_length=MAX_NATIVE_TEXT_SPANS
    )

    _foreign_refs = field_validator("foreign_refs")(_unique)

    @model_validator(mode="after")
    def _request_integrity(self) -> NativeTextSourceAdmissionV1:
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        try:
            body = self.body_text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("body_text must encode as valid UTF-8") from exc
        if not body:
            raise ValueError("body_text must not be empty")
        if len(body) > MAX_NATIVE_TEXT_BYTES:
            raise ValueError("body_text exceeds the V1 byte limit")
        refs = [span.client_ref for span in self.spans]
        if len(refs) != len(set(refs)):
            raise ValueError("span client_ref values must be unique")
        return self


class NativeUtf8SpanProofV1(DungeonMindModel):
    """Immutable typed proof binding one EvidenceRefV3 to exact UTF-8 bytes."""

    schema_version: Literal["dm_native_utf8_span_v1"] = "dm_native_utf8_span_v1"
    span_id: NonBlankId
    source_revision_id: NonBlankId
    evidence_ref_id: NonBlankId
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    slice_sha256: Sha256Hex

    @model_validator(mode="after")
    def _nonempty(self) -> NativeUtf8SpanProofV1:
        if self.start_byte >= self.end_byte:
            raise ValueError("span must be a nonempty half-open byte interval")
        return self


class NativeTextSourceAdmissionBindingV1(DungeonMindModel):
    """Durable resolution from one caller-local span reference to Kernel IDs."""

    client_ref: NonBlankId
    span_id: NonBlankId
    evidence_ref_id: NonBlankId


class NativeSourceAdmissionReceiptV1(DungeonMindModel):
    """Companion receipt for the source records committed with one native child."""

    schema_version: Literal["dm_native_source_admission_receipt_v1"] = (
        "dm_native_source_admission_receipt_v1"
    )
    space_id: NonBlankId
    admission_id: NonBlankId
    command_sha256: Sha256Hex
    source_authority_epoch: int = Field(ge=1)
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId
    origin: NativeTextSourceOriginV1 | None = None
    published_revision_id: NonBlankId
    bindings: list[NativeTextSourceAdmissionBindingV1] = Field(
        min_length=1, max_length=MAX_NATIVE_TEXT_SPANS
    )
    publication_receipt: KnowledgePublicationReceipt
    status: Literal["published"] = "published"

    @model_validator(mode="after")
    def _receipt_binding(self) -> NativeSourceAdmissionReceiptV1:
        receipt = self.publication_receipt
        if receipt.space_id != self.space_id:
            raise ValueError("publication receipt space mismatch")
        if receipt.publication_id != self.admission_id:
            raise ValueError("publication receipt identity mismatch")
        if receipt.published_revision_id != self.published_revision_id:
            raise ValueError("publication receipt revision mismatch")
        if len({item.client_ref for item in self.bindings}) != len(self.bindings):
            raise ValueError("binding client_ref values must be unique")
        if len({item.span_id for item in self.bindings}) != len(self.bindings):
            raise ValueError("binding span IDs must be unique")
        if len({item.evidence_ref_id for item in self.bindings}) != len(self.bindings):
            raise ValueError("binding evidence IDs must be unique")
        return self


class NativeTextSourceAccessV1(DungeonMindModel):
    """Authorized source preview, or a deliberately non-disclosing miss."""

    schema_version: Literal["dm_native_source_access_v1"] = "dm_native_source_access_v1"
    status: Literal["available", "unavailable"]
    evidence_ref_id: NonBlankId | None = None
    source_artifact_id: NonBlankId | None = None
    source_revision_id: NonBlankId | None = None
    body_sha256: Sha256Hex | None = None
    body_text: str | None = None
    span_start_byte: int | None = Field(default=None, ge=0)
    span_end_byte: int | None = Field(default=None, gt=0)
    span_sha256: Sha256Hex | None = None
    source_authority_epoch: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _status_shape(self) -> NativeTextSourceAccessV1:
        values = (
            self.evidence_ref_id,
            self.source_artifact_id,
            self.source_revision_id,
            self.body_sha256,
            self.body_text,
            self.span_start_byte,
            self.span_end_byte,
            self.span_sha256,
            self.source_authority_epoch,
        )
        if self.status == "unavailable" and any(value is not None for value in values):
            raise ValueError("unavailable result must not disclose source details")
        if self.status == "available":
            if any(value is None for value in values):
                raise ValueError("available result requires the complete verified source")
            if self.span_start_byte >= self.span_end_byte:  # type: ignore[operator]
                raise ValueError("available result span must be nonempty")
        return self
