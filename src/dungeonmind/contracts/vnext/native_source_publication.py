"""Source-fenced atomic facts/aliases; separate from immutable extension V1."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .common import NonBlankId, Sha256Hex
from .contribution import ContributionDisposition
from .native_source import (
    MAX_NATIVE_TEXT_SPANS,
    NativeTextEvidenceSpanRequestV1,
    NativeTextSourceAdmissionBindingV1,
    NativeUtf8SpanProofV1,
)
from .prospective import ProspectiveKnowledgeContribution, ProspectiveResultBinding
from .prospective_aliases import ProspectiveCreateAliasV1
from .publication import KnowledgePublicationReceipt


class NativeSourcePublicationSupportRefV1(DungeonMindModel):
    evidence_ref_id: NonBlankId
    span_id: NonBlankId
    proof: NativeUtf8SpanProofV1
    introducing_kind: Literal["admission", "extension", "publication"]
    introducing_operation_id: NonBlankId
    introducing_receipt_sha256: Sha256Hex
    proof_authority_epoch: int = Field(ge=1)

    @model_validator(mode="after")
    def _identity(self) -> Self:
        if (self.evidence_ref_id, self.span_id) != (self.proof.evidence_ref_id, self.proof.span_id):
            raise ValueError("SUPPORT proof identity mismatch")
        return self


class NativeSourcePublicationNewIntervalsV1(DungeonMindModel):
    mode: Literal["new_intervals"] = "new_intervals"
    spans: list[NativeTextEvidenceSpanRequestV1] = Field(
        min_length=1, max_length=MAX_NATIVE_TEXT_SPANS
    )

    @model_validator(mode="after")
    def _support(self) -> Self:
        if any(s.evidence_role != "support" for s in self.spans):
            raise ValueError("new evidence must be SUPPORT")
        if len({s.client_ref for s in self.spans}) != len(self.spans) or len(
            {(s.start_byte, s.end_byte) for s in self.spans}
        ) != len(self.spans):
            raise ValueError("duplicate span")
        return self


class NativeSourcePublicationExistingSupportV1(DungeonMindModel):
    mode: Literal["existing_support"] = "existing_support"
    support: list[NativeSourcePublicationSupportRefV1] = Field(
        min_length=1, max_length=MAX_NATIVE_TEXT_SPANS
    )

    @model_validator(mode="after")
    def _unique(self) -> Self:
        if len({r.evidence_ref_id for r in self.support}) != len(self.support) or len(
            {r.span_id for r in self.support}
        ) != len(self.support):
            raise ValueError("duplicate SUPPORT reference")
        return self


NativeSourcePublicationEvidenceV1 = Annotated[
    NativeSourcePublicationNewIntervalsV1 | NativeSourcePublicationExistingSupportV1,
    Field(discriminator="mode"),
]


class NativeSourcePublicationBasisV1(DungeonMindModel):
    schema_version: Literal["dm_native_source_publication_basis_v1"] = (
        "dm_native_source_publication_basis_v1"
    )
    space_id: NonBlankId
    publication_id: NonBlankId
    original_admission_id: NonBlankId
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId
    expected_body_sha256: Sha256Hex
    expected_parent_revision_id: NonBlankId
    expected_source_authority_epoch: int = Field(ge=1)
    created_at: datetime
    evidence: NativeSourcePublicationEvidenceV1

    @model_validator(mode="after")
    def _time(self) -> Self:
        if self.evidence.mode == "existing_support" and any(
            ref.proof.source_revision_id != self.source_revision_id for ref in self.evidence.support
        ):
            raise ValueError("SUPPORT proof source revision mismatch")
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class GovernedNativeSourcePublicationV1(NativeSourcePublicationBasisV1):
    schema_version: Literal["dm_governed_native_source_publication_v1"] = (
        "dm_governed_native_source_publication_v1"
    )
    contribution: ProspectiveKnowledgeContribution
    aliases: list[ProspectiveCreateAliasV1] = Field(default_factory=list)
    dispositions: list[ContributionDisposition] = Field(min_length=1)

    @model_validator(mode="after")
    def _governance(self) -> Self:
        ids = [i.item_id for i in self.contribution.items] + [a.item_id for a in self.aliases]
        decisions = [d.item_id for d in self.dispositions]
        if (
            len(set(ids)) != len(ids)
            or len(set(decisions)) != len(decisions)
            or set(ids) != set(decisions)
        ):
            raise ValueError("complete unique disposition inventory required")
        if any(d.disposition == "unresolved" for d in self.dispositions):
            raise ValueError("unresolved disposition")
        if len({a.alias_id for a in self.aliases}) != len(self.aliases):
            raise ValueError("duplicate alias identity")
        accepted = {d.item_id for d in self.dispositions if d.disposition == "accepted"}
        if any(
            item.item_id in accepted
            and item.kind
            in {"retract_assertion", "supersede_assertion", "propose_identity_decision"}
            for item in self.contribution.items
        ):
            raise ValueError("source publication is create-only; destructive governance refused")
        if self.contribution.space_id != self.space_id:
            raise ValueError("contribution space mismatch")
        return self


class GovernedNativeSourcePublicationReceiptV1(DungeonMindModel):
    schema_version: Literal["dm_governed_native_source_publication_receipt_v1"] = (
        "dm_governed_native_source_publication_receipt_v1"
    )
    space_id: NonBlankId
    publication_id: NonBlankId
    original_admission_id: NonBlankId
    original_admission_sha256: Sha256Hex
    source_artifact_id: NonBlankId
    source_revision_id: NonBlankId
    intent_sha256: Sha256Hex
    mode: Literal["new_intervals", "existing_support"]
    source_authority_epoch_before: int = Field(ge=1)
    source_authority_epoch_after: int = Field(ge=1)
    bindings: list[NativeTextSourceAdmissionBindingV1] = Field(default_factory=list)
    proofs: list[NativeUtf8SpanProofV1] = Field(default_factory=list)
    reused_support: list[NativeSourcePublicationSupportRefV1] = Field(default_factory=list)
    publication_receipt: KnowledgePublicationReceipt
    result_bindings: list[ProspectiveResultBinding]

    @model_validator(mode="after")
    def _shape(self) -> Self:
        delta = int(self.mode == "new_intervals")
        if self.source_authority_epoch_after != self.source_authority_epoch_before + delta:
            raise ValueError("source epoch delta mismatch")
        if (self.space_id, self.publication_id) != (
            self.publication_receipt.space_id,
            self.publication_receipt.publication_id,
        ):
            raise ValueError("publication identity mismatch")
        if self.mode == "new_intervals":
            if not self.proofs or self.reused_support or len(self.bindings) != len(self.proofs):
                raise ValueError("introduced proof inventory mismatch")
        elif self.proofs or self.bindings or not self.reused_support:
            raise ValueError("reuse cannot introduce evidence")
        if len({p.span_id for p in self.proofs}) != len(self.proofs) or len(
            {p.evidence_ref_id for p in self.proofs}
        ) != len(self.proofs):
            raise ValueError("duplicate introduced proof")
        for b, p in zip(self.bindings, self.proofs, strict=True):
            if (b.span_id, b.evidence_ref_id, self.source_revision_id) != (
                p.span_id,
                p.evidence_ref_id,
                p.source_revision_id,
            ):
                raise ValueError("proof binding mismatch")
        ids = [b.client_op_id for b in self.result_bindings]
        if ids != sorted(set(ids)):
            raise ValueError("result inventory must be unique ordered")
        return self
