"""Operator-attested source-span proof, additive to native V1 admission."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .common import NonBlankId, Sha256Hex
from .source import SourceArtifactV3


class OperatorSourceSelectionV1(DungeonMindModel):
    """Prepare input. Actor and approval are deliberately absent."""

    schema_version: Literal["dm_operator_source_selection_v1"] = "dm_operator_source_selection_v1"
    space_id: NonBlankId
    legacy_world_id: NonBlankId
    operation_id: NonBlankId
    expected_head_revision_id: NonBlankId
    claim_kind: Literal["assertion", "alias"]
    claim_id: NonBlankId
    evidence_ref_id: NonBlankId
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId
    source_span_ref_id: NonBlankId
    expected_body_sha256: Sha256Hex
    body_text: str
    passage_text: str
    occurrence_index: int | None = Field(default=None, ge=0)
    native_policy: SourceArtifactV3
    source_vocabulary: list[NonBlankId] = Field(min_length=1)
    gm_label: NonBlankId

    @model_validator(mode="after")
    def _bounded(self) -> OperatorSourceSelectionV1:
        body = self.body_text.encode("utf-8", "strict")
        passage = self.passage_text.encode("utf-8", "strict")
        if not 1 <= len(body) <= 1_048_576:
            raise ValueError("body size is outside native text bound")
        if not 1 <= len(passage) <= 4096:
            raise ValueError("passage size is outside review bound")
        if len(self.source_vocabulary) != len(set(self.source_vocabulary)):
            raise ValueError("source vocabulary terms must be unique")
        if self.native_policy.source_artifact_id != self.source_artifact_id:
            raise ValueError("native policy artifact mismatch")
        if self.native_policy.current_revision_id != self.source_revision_id:
            raise ValueError("native policy revision mismatch")
        return self


class OperatorSourceCommandV1(DungeonMindModel):
    """Durably prepared command, without body bytes or an actor field."""

    schema_version: Literal["dm_operator_source_command_v1"] = "dm_operator_source_command_v1"
    space_id: NonBlankId
    legacy_world_id: NonBlankId
    operation_id: NonBlankId
    expected_head_revision_id: NonBlankId
    claim_kind: Literal["assertion", "alias"]
    claim_id: NonBlankId
    evidence_ref_id: NonBlankId
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId
    source_span_ref_id: NonBlankId
    body_sha256: Sha256Hex
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    slice_sha256: Sha256Hex
    claim_sha256: Sha256Hex
    native_policy: SourceArtifactV3
    domain_descriptor_sha256: Sha256Hex
    source_vocabulary_sha256: Sha256Hex
    gm_label: NonBlankId
    legacy_metadata_sha256: Sha256Hex
    expected_source_epoch: int = Field(ge=0)

    @model_validator(mode="after")
    def _span(self) -> OperatorSourceCommandV1:
        if self.start_byte >= self.end_byte:
            raise ValueError("span must be nonempty")
        return self


class PreparedOperatorSourceV1(DungeonMindModel):
    schema_version: Literal["dm_prepared_operator_source_v1"] = "dm_prepared_operator_source_v1"
    command: OperatorSourceCommandV1
    review_claim_summary: str
    review_excerpt: str
    review_display_sha256: Sha256Hex
    prepared_at: datetime
    expires_at: datetime
    preparation_sha256: Sha256Hex

    @model_validator(mode="after")
    def _expiry(self) -> PreparedOperatorSourceV1:
        if self.prepared_at.utcoffset() is None or self.expires_at.utcoffset() is None:
            raise ValueError("preparation times must be aware")
        if not 0 < (self.expires_at - self.prepared_at).total_seconds() <= 900:
            raise ValueError("preparation must expire within 15 minutes")
        return self


class OperatorSourceAttestationReceiptV1(DungeonMindModel):
    schema_version: Literal["dm_native_operator_span_attestation_v1"] = (
        "dm_native_operator_span_attestation_v1"
    )
    provenance_kind: Literal["operator_attestation"] = "operator_attestation"
    command: OperatorSourceCommandV1
    preparation_sha256: Sha256Hex
    review_display_sha256: Sha256Hex
    actor: NonBlankId
    role: Literal["owner", "gm"]
    auth_method: NonBlankId
    approved_at: datetime
    source_authority_epoch: int = Field(ge=1)
    record_fingerprint: Sha256Hex

    @model_validator(mode="after")
    def _aware(self) -> OperatorSourceAttestationReceiptV1:
        if self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must be aware")
        return self
