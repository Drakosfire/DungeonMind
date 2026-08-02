"""Finalized contribution-review contracts.

This module is the generic kernel seam between a candidate contribution and a
durable, explicitly confirmed review.  It stores governance facts only:
assertion verdicts, candidate identity verdicts, source-plan provenance, and
the two contribution lifecycle records.  It never materializes graph truth,
publishes a revision, or appends an identity-decision operation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel
from .contribution import (
    AcceptanceState,
    ContributionSourceKind,
    ContributionStatus,
    GraphContribution,
    GraphContributionAssertion,
)
from .identity import IdentityOutcome
from .semantic_profile import SemanticProfileRef

CONTRIBUTION_PLAN_REF_SCHEMA = "dm_contribution_plan_ref_v1"
CONTRIBUTION_IDENTITY_PROPOSAL_SCHEMA = "dm_contribution_identity_proposal_v1"
CONTRIBUTION_IDENTITY_VERDICT_SCHEMA = "dm_contribution_identity_verdict_v1"
CONTRIBUTION_ASSERTION_VERDICT_SCHEMA = "dm_contribution_assertion_verdict_v1"
CONTRIBUTION_REVIEW_INTENT_SCHEMA = "dm_contribution_review_intent_v1"
COMMIT_CONFIRMATION_RECEIPT_SCHEMA = "dm_commit_confirmation_receipt_v1"
CONTRIBUTION_REVIEW_SUBMISSION_SCHEMA = "dm_contribution_review_submission_v1"
CONTRIBUTION_REVIEW_RECORD_SCHEMA = "dm_contribution_review_record_v1"
CONTRIBUTION_REVIEW_STATE_SCHEMA = "dm_contribution_review_state_v1"

FINALIZE_REVIEW_TOOL = "dungeonmind.finalize_contribution_review"
FINALIZE_REVIEW_EFFECT = "commit"

_REVIEW_INTENT_DIGEST_SCHEMA = CONTRIBUTION_REVIEW_INTENT_SCHEMA
_CONFIRMATION_ID_SCHEMA = "dm_confirmation_id_v1"
_REVIEW_ID_SCHEMA = "dm_contribution_review_id_v1"
_REVIEWED_CONTRIBUTION_ID_SCHEMA = "dm_reviewed_contribution_id_v1"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_ID = re.compile(r"^reviewop:[0-9a-f]{32}$")
_REVIEW_ID = re.compile(r"^review:[0-9a-f]{32}$")
_CONFIRMATION_ID = re.compile(r"^confirm:[0-9a-f]{32}$")
_CONTRIBUTION_ID = re.compile(r"^contrib:[0-9a-f]{32}$")
_REVIEWABLE_ASSERTION_KINDS = frozenset({"label", "alias", "summary", "relationship"})


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_unique_sorted(values: list[str], *, field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")
    if values != sorted(values):
        raise ValueError(f"{field_name} must be sorted deterministically")


def _require_digest(value: str, *, field_name: str) -> str:
    if not _SHA256_HEX.fullmatch(value):
        raise ValueError(f"{field_name} must be exactly 64 lowercase hex")
    return value


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-blank")
    return value


def contribution_payload_sha256(contribution: GraphContribution) -> str:
    """Digest the complete serialized contribution payload."""
    return _canonical_sha256(contribution.model_dump(mode="json"))


def _validate_reviewable_assertions(
    assertions: list[GraphContributionAssertion],
) -> None:
    assertion_ids = [assertion.assertion_id for assertion in assertions]
    if len(assertion_ids) != len(set(assertion_ids)):
        raise ValueError("candidate assertion IDs must be unique")
    for assertion in assertions:
        kind = assertion.assertion_kind
        if kind not in _REVIEWABLE_ASSERTION_KINDS:
            raise ValueError("unsupported assertion kind for finalized review")
        if kind == "label":
            _require_assertion_text(assertion.subject_object_id, "label subject")
            _require_assertion_text(assertion.label, "label")
            _require_absent_assertion_field(assertion.object_object_id, "label object")
            _require_absent_assertion_field(assertion.predicate, "label predicate")
            _require_absent_assertion_field(assertion.value, "label value")
        elif kind in {"alias", "summary"}:
            _require_assertion_text(assertion.subject_object_id, f"{kind} subject")
            _require_assertion_text(assertion.value, f"{kind} value")
            _require_absent_assertion_field(assertion.object_object_id, f"{kind} object")
            _require_absent_assertion_field(assertion.predicate, f"{kind} predicate")
            _require_absent_assertion_field(assertion.label, f"{kind} label")
        else:
            _require_assertion_text(assertion.subject_object_id, "relationship subject")
            _require_assertion_text(assertion.object_object_id, "relationship object")
            _require_assertion_text(assertion.predicate, "relationship predicate")
            _require_absent_assertion_field(assertion.label, "relationship label")
            _require_absent_assertion_field(assertion.value, "relationship value")


def _require_assertion_text(value: str | None, field_name: str) -> None:
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must be non-blank")


def _require_absent_assertion_field(value: str | None, field_name: str) -> None:
    if value is not None:
        raise ValueError(f"{field_name} must be absent")


def derive_review_intent_sha256(
    *,
    operation_id: str,
    world_id: str,
    campaign_id: str | None,
    plan_ref: ContributionPlanRef,
    candidate_contribution: GraphContribution,
    identity_proposals: list[ContributionIdentityProposal],
    identity_verdicts: list[ContributionIdentityVerdict],
    assertion_verdicts: list[ContributionAssertionVerdict],
    reviewer_id: str,
    reviewed_at: datetime,
) -> str:
    """Derive the intent digest from every field except the digest itself."""
    material = {
        "schema": _REVIEW_INTENT_DIGEST_SCHEMA,
        "operation_id": operation_id,
        "world_id": world_id,
        "campaign_id": campaign_id,
        "plan_ref": plan_ref.model_dump(mode="json"),
        "candidate_contribution": candidate_contribution.model_dump(mode="json"),
        "identity_proposals": [
            item.model_dump(mode="json") for item in identity_proposals
        ],
        "identity_verdicts": [
            item.model_dump(mode="json") for item in identity_verdicts
        ],
        "assertion_verdicts": [
            item.model_dump(mode="json") for item in assertion_verdicts
        ],
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at.isoformat(),
    }
    return _canonical_sha256(material)


def derive_confirmation_id(
    *,
    operation_id: str,
    review_intent_sha256: str,
    actor: str,
    confirmed_at: datetime,
) -> str:
    material = {
        "schema": _CONFIRMATION_ID_SCHEMA,
        "operation_id": operation_id,
        "review_intent_sha256": review_intent_sha256,
        "actor": actor,
        "confirmed_at": confirmed_at.isoformat(),
    }
    return f"confirm:{_canonical_sha256(material)[:32]}"


def derive_review_id(
    *,
    operation_id: str,
    review_intent_sha256: str,
    world_id: str,
) -> str:
    material = {
        "schema": _REVIEW_ID_SCHEMA,
        "operation_id": operation_id,
        "review_intent_sha256": review_intent_sha256,
        "world_id": world_id,
    }
    return f"review:{_canonical_sha256(material)[:32]}"


def derive_reviewed_contribution_id(
    *,
    review_id: str,
    candidate_contribution_id: str,
) -> str:
    material = {
        "schema": _REVIEWED_CONTRIBUTION_ID_SCHEMA,
        "review_id": review_id,
        "candidate_contribution_id": candidate_contribution_id,
    }
    return f"contrib:{_canonical_sha256(material)[:32]}"


class ContributionIdentityVerdictKind(StrEnum):
    """One-shot reviewer disposition of a planned candidate identity."""

    CONFIRM_EXISTING = "confirm_existing"
    CREATE_NEW = "create_new"
    REJECT_CANDIDATE = "reject_candidate"


def _validate_identity_decisions(
    proposals: list[ContributionIdentityProposal],
    verdicts: list[ContributionIdentityVerdict],
) -> None:
    proposal_ids = [item.candidate_id for item in proposals]
    _require_unique_sorted(proposal_ids, field_name="identity_proposals")
    targets = [item.target_object_id for item in proposals]
    if len(targets) != len(set(targets)):
        raise ValueError("identity proposal target IDs must be unique")
    verdict_ids = [item.candidate_id for item in verdicts]
    _require_unique_sorted(verdict_ids, field_name="identity_verdicts")
    if verdict_ids != proposal_ids:
        raise ValueError("identity verdicts must cover every identity proposal exactly once")
    proposals_by_id = {item.candidate_id: item for item in proposals}
    for verdict in verdicts:
        proposal = proposals_by_id[verdict.candidate_id]
        if verdict.target_object_id != proposal.target_object_id:
            raise ValueError("identity verdicts may not override proposal targets")
        if (
            verdict.verdict is ContributionIdentityVerdictKind.CONFIRM_EXISTING
            and proposal.planned_outcome is not IdentityOutcome.RESOLVED_EXISTING
        ):
            raise ValueError("confirm_existing requires resolved_existing")
        if (
            verdict.verdict is ContributionIdentityVerdictKind.CREATE_NEW
            and proposal.planned_outcome is not IdentityOutcome.PROVISIONAL_NEW
        ):
            raise ValueError("create_new requires provisional_new")


class ContributionPlanRef(DungeonMindModel):
    """Opaque provenance pin for the exact plan being reviewed."""

    schema_version: Literal["dm_contribution_plan_ref_v1"] = CONTRIBUTION_PLAN_REF_SCHEMA
    source_plan_schema: str = Field(min_length=1)
    source_plan_id: str = Field(min_length=1)
    source_plan_sha256: str
    source_input_sha256: str
    preview_content_sha256: str
    candidate_contribution_sha256: str
    expected_parent_revision_id: str = Field(min_length=1)
    base_graph_schema: str = Field(min_length=1)
    base_graph_payload_sha256: str
    semantic_profile: SemanticProfileRef

    @field_validator(
        "source_plan_sha256",
        "source_input_sha256",
        "preview_content_sha256",
        "candidate_contribution_sha256",
        "base_graph_payload_sha256",
    )
    @classmethod
    def _validate_digest(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "digest")
        return _require_digest(value, field_name=field_name)


class ContributionIdentityProposal(DungeonMindModel):
    """Generic, non-authoritative identity proposal copied from a ready plan."""

    schema_version: Literal[
        "dm_contribution_identity_proposal_v1"
    ] = CONTRIBUTION_IDENTITY_PROPOSAL_SCHEMA
    candidate_id: str = Field(min_length=1)
    candidate_kind: str = Field(min_length=1)
    planned_outcome: IdentityOutcome
    target_object_id: str = Field(min_length=1)
    matched_object_ids: list[str] = []

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.planned_outcome not in (
            IdentityOutcome.RESOLVED_EXISTING,
            IdentityOutcome.PROVISIONAL_NEW,
        ):
            raise ValueError("identity proposals may only represent ready outcomes")
        _require_unique_sorted(self.matched_object_ids, field_name="matched_object_ids")
        if self.planned_outcome is IdentityOutcome.RESOLVED_EXISTING:
            if self.matched_object_ids != [self.target_object_id]:
                raise ValueError(
                    "resolved_existing proposal requires the target as its sole match"
                )
        elif self.matched_object_ids:
            raise ValueError("provisional_new proposal requires no matched objects")
        return self


class ContributionIdentityVerdict(DungeonMindModel):
    """One reviewer verdict for one identity proposal; target overrides are forbidden."""

    schema_version: Literal[
        "dm_contribution_identity_verdict_v1"
    ] = CONTRIBUTION_IDENTITY_VERDICT_SCHEMA
    candidate_id: str = Field(min_length=1)
    verdict: ContributionIdentityVerdictKind
    target_object_id: str = Field(min_length=1)


class ContributionAssertionVerdict(DungeonMindModel):
    """Final accepted/rejected state for one candidate assertion."""

    schema_version: Literal[
        "dm_contribution_assertion_verdict_v1"
    ] = CONTRIBUTION_ASSERTION_VERDICT_SCHEMA
    assertion_id: str = Field(min_length=1)
    acceptance_state: AcceptanceState

    @field_validator("acceptance_state")
    @classmethod
    def _final_only(cls, value: AcceptanceState) -> AcceptanceState:
        if value is AcceptanceState.CANDIDATE:
            raise ValueError("review verdicts must be accepted or rejected")
        return value


class ContributionReviewIntent(DungeonMindModel):
    """Complete, content-bound one-shot review input before commit authority."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal[
        "dm_contribution_review_intent_v1"
    ] = CONTRIBUTION_REVIEW_INTENT_SCHEMA
    operation_id: str
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    plan_ref: ContributionPlanRef
    candidate_contribution: GraphContribution
    identity_proposals: list[ContributionIdentityProposal] = Field(min_length=1)
    identity_verdicts: list[ContributionIdentityVerdict] = Field(min_length=1)
    assertion_verdicts: list[ContributionAssertionVerdict] = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    review_intent_sha256: str

    @field_validator("operation_id")
    @classmethod
    def _validate_operation_id(cls, value: str) -> str:
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operation_id must be reviewop:<32 lowercase hex>")
        return value

    @field_validator("reviewer_id")
    @classmethod
    def _validate_reviewer(cls, value: str) -> str:
        return _require_nonblank(value, field_name="reviewer_id")

    @field_validator("review_intent_sha256")
    @classmethod
    def _validate_intent_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="review_intent_sha256")

    @model_validator(mode="after")
    def _validate_complete_intent(self) -> Self:
        if self.plan_ref.candidate_contribution_sha256 != contribution_payload_sha256(
            self.candidate_contribution
        ):
            raise ValueError("candidate contribution digest does not match plan ref")
        contribution = self.candidate_contribution
        if contribution.world_id != self.world_id:
            raise ValueError("candidate contribution world differs from review intent")
        if contribution.campaign_scope != self.campaign_id:
            raise ValueError("candidate contribution campaign differs from review intent")
        if contribution.source_kind is not ContributionSourceKind.EXTRACTION:
            raise ValueError("review intents require extraction candidate contributions")
        if contribution.status is not ContributionStatus.ACTIVE:
            raise ValueError("review intents require an active candidate contribution")
        if contribution.supersedes_contribution_id is not None:
            raise ValueError("candidate contribution must not supersede another contribution")
        if contribution.identity_decision_ids:
            raise ValueError("review intents contain no identity decision IDs")
        if contribution.unresolved_mentions:
            raise ValueError("review intents contain no unresolved mentions")
        if contribution.diagnostics:
            raise ValueError("review intents contain no diagnostics")
        _validate_reviewable_assertions(contribution.assertions)
        for assertion in contribution.assertions:
            if (
                assertion.acceptance_state is not AcceptanceState.CANDIDATE
                or assertion.evidence_refs == []
                or assertion.visibility.value != "gm"
                or assertion.epistemic_kind.value != "asserted"
            ):
                raise ValueError("candidate contribution assertions are not reviewable")

        proposals = self.identity_proposals
        _validate_identity_decisions(proposals, self.identity_verdicts)

        assertion_ids = [item.assertion_id for item in contribution.assertions]
        _require_unique_sorted(
            [item.assertion_id for item in self.assertion_verdicts],
            field_name="assertion_verdicts",
        )
        if set(assertion_ids) != {
            item.assertion_id for item in self.assertion_verdicts
        }:
            raise ValueError("assertion verdicts must cover every candidate assertion exactly once")
        target_to_proposal = {item.target_object_id: item for item in proposals}
        for assertion in contribution.assertions:
            if (
                assertion.assertion_kind in {"label", "alias", "summary"}
                and assertion.subject_object_id not in target_to_proposal
            ):
                raise ValueError("node assertion target lacks an identity proposal")

        expected_digest = derive_review_intent_sha256(
            operation_id=self.operation_id,
            world_id=self.world_id,
            campaign_id=self.campaign_id,
            plan_ref=self.plan_ref,
            candidate_contribution=self.candidate_contribution,
            identity_proposals=self.identity_proposals,
            identity_verdicts=self.identity_verdicts,
            assertion_verdicts=self.assertion_verdicts,
            reviewer_id=self.reviewer_id,
            reviewed_at=self.reviewed_at,
        )
        if self.review_intent_sha256 != expected_digest:
            raise ValueError("review_intent_sha256 does not match intent content")
        return self


class CommitConfirmationReceipt(DungeonMindModel):
    """Explicit caller confirmation bound to one exact review intent."""

    schema_version: Literal[
        "dm_commit_confirmation_receipt_v1"
    ] = COMMIT_CONFIRMATION_RECEIPT_SCHEMA
    confirmation_id: str
    operation_id: str
    review_intent_sha256: str
    actor: str = Field(min_length=1)
    tool_name: Literal["dungeonmind.finalize_contribution_review"] = FINALIZE_REVIEW_TOOL
    effect: Literal["commit"] = FINALIZE_REVIEW_EFFECT
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    expected_parent_revision_id: str = Field(min_length=1)
    confirmed_at: datetime

    @field_validator("confirmation_id")
    @classmethod
    def _validate_confirmation_id(cls, value: str) -> str:
        if not _CONFIRMATION_ID.fullmatch(value):
            raise ValueError("confirmation_id must be confirm:<32 lowercase hex")
        return value

    @field_validator("operation_id")
    @classmethod
    def _validate_operation_id(cls, value: str) -> str:
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operation_id must be reviewop:<32 lowercase hex")
        return value

    @field_validator("review_intent_sha256")
    @classmethod
    def _validate_intent_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="review_intent_sha256")

    @model_validator(mode="after")
    def _deterministic_id(self) -> Self:
        expected = derive_confirmation_id(
            operation_id=self.operation_id,
            review_intent_sha256=self.review_intent_sha256,
            actor=self.actor,
            confirmed_at=self.confirmed_at,
        )
        if self.confirmation_id != expected:
            raise ValueError("confirmation_id does not match receipt content")
        return self


class ContributionReviewSubmission(DungeonMindModel):
    """Intent plus the exact confirmation required for a durable commit."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal[
        "dm_contribution_review_submission_v1"
    ] = CONTRIBUTION_REVIEW_SUBMISSION_SCHEMA
    intent: ContributionReviewIntent
    confirmation: CommitConfirmationReceipt

    @model_validator(mode="after")
    def _receipt_binds_intent(self) -> Self:
        receipt = self.confirmation
        intent = self.intent
        if receipt.operation_id != intent.operation_id:
            raise ValueError("confirmation operation does not match intent")
        if receipt.review_intent_sha256 != intent.review_intent_sha256:
            raise ValueError("confirmation digest does not match intent")
        if receipt.actor != intent.reviewer_id:
            raise ValueError("confirmation actor does not match reviewer")
        if receipt.world_id != intent.world_id:
            raise ValueError("confirmation world does not match intent")
        if receipt.campaign_id != intent.campaign_id:
            raise ValueError("confirmation campaign does not match intent")
        if (
            receipt.expected_parent_revision_id
            != intent.plan_ref.expected_parent_revision_id
        ):
            raise ValueError("confirmation parent does not match plan ref")
        if receipt.confirmed_at != intent.reviewed_at:
            raise ValueError("confirmation time must equal reviewed_at")
        return self


class ContributionReviewRecord(DungeonMindModel):
    """Durable finalized review metadata; contribution payloads live beside it."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal[
        "dm_contribution_review_record_v1"
    ] = CONTRIBUTION_REVIEW_RECORD_SCHEMA
    review_id: str
    operation_id: str
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    plan_ref: ContributionPlanRef
    review_intent_sha256: str
    candidate_preview_sha256: str
    stored_candidate_contribution_id: str
    stored_candidate_sha256: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    identity_proposals: list[ContributionIdentityProposal] = Field(min_length=1)
    identity_verdicts: list[ContributionIdentityVerdict] = Field(min_length=1)
    assertion_verdicts: list[ContributionAssertionVerdict] = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    confirmation_id: str
    status: Literal["finalized"] = "finalized"

    @field_validator("review_id")
    @classmethod
    def _validate_review_id(cls, value: str) -> str:
        if not _REVIEW_ID.fullmatch(value):
            raise ValueError("review_id must be review:<32 lowercase hex")
        return value

    @field_validator("operation_id")
    @classmethod
    def _validate_operation_id(cls, value: str) -> str:
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operation_id must be reviewop:<32 lowercase hex")
        return value

    @field_validator(
        "review_intent_sha256",
        "candidate_preview_sha256",
        "stored_candidate_sha256",
        "reviewed_contribution_sha256",
    )
    @classmethod
    def _validate_digests(cls, value: str, info: object) -> str:
        return _require_digest(value, field_name=getattr(info, "field_name", "digest"))

    @field_validator("confirmation_id")
    @classmethod
    def _validate_confirmation_id(cls, value: str) -> str:
        if not _CONFIRMATION_ID.fullmatch(value):
            raise ValueError("confirmation_id must be confirm:<32 lowercase hex")
        return value

    @model_validator(mode="after")
    def _deterministic_and_sorted(self) -> Self:
        expected = derive_review_id(
            operation_id=self.operation_id,
            review_intent_sha256=self.review_intent_sha256,
            world_id=self.world_id,
        )
        if self.review_id != expected:
            raise ValueError("review_id does not match review identity")
        _validate_identity_decisions(self.identity_proposals, self.identity_verdicts)
        _require_unique_sorted(
            [item.assertion_id for item in self.assertion_verdicts],
            field_name="assertion_verdicts",
        )
        expected_reviewed_id = derive_reviewed_contribution_id(
            review_id=self.review_id,
            candidate_contribution_id=self.stored_candidate_contribution_id,
        )
        if self.reviewed_contribution_id != expected_reviewed_id:
            raise ValueError("reviewed contribution ID does not match review identity")
        proposal_ids = [item.candidate_id for item in self.identity_proposals]
        if [item.candidate_id for item in self.identity_verdicts] != proposal_ids:
            raise ValueError("review record identity verdict coverage is incomplete")
        if self.stored_candidate_contribution_id == self.reviewed_contribution_id:
            raise ValueError("candidate and reviewed contribution IDs must differ")
        if self.candidate_preview_sha256 != self.plan_ref.candidate_contribution_sha256:
            raise ValueError("candidate preview digest differs from plan ref")
        if self.confirmation_id != derive_confirmation_id(
            operation_id=self.operation_id,
            review_intent_sha256=self.review_intent_sha256,
            actor=self.reviewer_id,
            confirmed_at=self.reviewed_at,
        ):
            raise ValueError("confirmation_id does not match review authority")
        return self


class ContributionReviewState(DungeonMindModel):
    """Reloadable atomic bundle of record, superseded candidate, and successor."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal[
        "dm_contribution_review_state_v1"
    ] = CONTRIBUTION_REVIEW_STATE_SCHEMA
    record: ContributionReviewRecord
    candidate_contribution: GraphContribution
    reviewed_contribution: GraphContribution

    @model_validator(mode="after")
    def _cross_record_integrity(self) -> Self:
        record = self.record
        candidate = self.candidate_contribution
        reviewed = self.reviewed_contribution
        if candidate.contribution_id != record.stored_candidate_contribution_id:
            raise ValueError("candidate contribution ID disagrees with review record")
        if reviewed.contribution_id != record.reviewed_contribution_id:
            raise ValueError("reviewed contribution ID disagrees with review record")
        if candidate.world_id != record.world_id or reviewed.world_id != record.world_id:
            raise ValueError("contribution world disagrees with review record")
        if candidate.campaign_scope != record.campaign_id:
            raise ValueError("candidate campaign disagrees with review record")
        if reviewed.campaign_scope != record.campaign_id:
            raise ValueError("reviewed campaign disagrees with review record")
        if candidate.status is not ContributionStatus.SUPERSEDED:
            raise ValueError("stored candidate contribution must be superseded")
        if candidate.source_kind is not ContributionSourceKind.EXTRACTION:
            raise ValueError("stored candidate contribution source kind drifted")
        if reviewed.status is not ContributionStatus.ACTIVE:
            raise ValueError("reviewed contribution must be active")
        if reviewed.source_kind is not ContributionSourceKind.GRAPH_REVIEW:
            raise ValueError("reviewed contribution must be graph_review sourced")
        if reviewed.supersedes_contribution_id != candidate.contribution_id:
            raise ValueError("reviewed contribution must supersede candidate")
        if reviewed.authored_by != record.reviewer_id or reviewed.produced_at != record.reviewed_at:
            raise ValueError("reviewed author/time disagrees with review record")
        if candidate.identity_decision_ids or reviewed.identity_decision_ids:
            raise ValueError("review state cannot append identity decisions")
        if candidate.unresolved_mentions or reviewed.unresolved_mentions:
            raise ValueError("review state cannot retain unresolved mentions")
        if candidate.diagnostics or reviewed.diagnostics:
            raise ValueError("review state cannot retain diagnostics")
        _validate_reviewable_assertions(candidate.assertions)
        _validate_reviewable_assertions(reviewed.assertions)
        for assertion in candidate.assertions:
            if assertion.acceptance_state is not AcceptanceState.CANDIDATE:
                raise ValueError("stored candidate assertions must remain candidate")
            if assertion.assertion_kind == "relationship" and (
                assertion.identity_resolution_outcome is not None
            ):
                raise ValueError("candidate relationship identity outcomes must remain null")
        candidate_preview = candidate.model_copy(
            deep=True, update={"status": ContributionStatus.ACTIVE}
        )
        if (
            contribution_payload_sha256(candidate_preview)
            != record.plan_ref.candidate_contribution_sha256
        ):
            raise ValueError("stored candidate no longer matches the reviewed preview")
        expected_intent_digest = derive_review_intent_sha256(
            operation_id=record.operation_id,
            world_id=record.world_id,
            campaign_id=record.campaign_id,
            plan_ref=record.plan_ref,
            candidate_contribution=candidate_preview,
            identity_proposals=record.identity_proposals,
            identity_verdicts=record.identity_verdicts,
            assertion_verdicts=record.assertion_verdicts,
            reviewer_id=record.reviewer_id,
            reviewed_at=record.reviewed_at,
        )
        if record.review_intent_sha256 != expected_intent_digest:
            raise ValueError("review record intent digest does not match durable content")
        if candidate.world_id != reviewed.world_id:
            raise ValueError("candidate/reviewed world drifted")
        for field_name in (
            "source_artifact_id",
            "source_revision_id",
            "extraction_profile",
            "campaign_scope",
        ):
            if getattr(candidate, field_name) != getattr(reviewed, field_name):
                raise ValueError(f"candidate/reviewed {field_name} drifted")
        if len(candidate.assertions) != len(reviewed.assertions):
            raise ValueError("reviewed contribution must preserve assertion count")
        if [item.assertion_id for item in candidate.assertions] != [
            item.assertion_id for item in reviewed.assertions
        ]:
            raise ValueError("reviewed contribution must preserve assertion IDs and order")

        proposals = {item.candidate_id: item for item in record.identity_proposals}
        verdicts = {item.candidate_id: item for item in record.identity_verdicts}
        assertion_verdicts = {
            item.assertion_id: item for item in record.assertion_verdicts
        }
        if set(assertion_verdicts) != {
            item.assertion_id for item in candidate.assertions
        }:
            raise ValueError("review record assertion verdict coverage is incomplete")
        if set(proposals) != set(verdicts):
            raise ValueError("review record identity verdict coverage is incomplete")
        target_to_candidate = {
            item.target_object_id: item.candidate_id for item in record.identity_proposals
        }
        candidate_assertions_by_target: dict[str, list[int]] = {}
        for index, (before, after) in enumerate(
            zip(candidate.assertions, reviewed.assertions, strict=True)
        ):
            before_dump = before.model_dump(mode="json")
            after_dump = after.model_dump(mode="json")
            before_dump.pop("acceptance_state", None)
            after_dump.pop("acceptance_state", None)
            before_dump.pop("identity_resolution_outcome", None)
            after_dump.pop("identity_resolution_outcome", None)
            if before_dump != after_dump:
                raise ValueError("reviewed assertion content/evidence drifted")
            verdict = assertion_verdicts.get(after.assertion_id)
            if verdict is None or after.acceptance_state is not verdict.acceptance_state:
                raise ValueError("reviewed assertion state disagrees with verdict")
            if after.assertion_kind == "relationship":
                if before.identity_resolution_outcome is not None or (
                    after.identity_resolution_outcome is not None
                ):
                    raise ValueError("relationship identity outcomes must remain null")
            elif after.assertion_kind in {"label", "alias", "summary"}:
                target = after.subject_object_id
                if target is None or target not in target_to_candidate:
                    raise ValueError("reviewed node target lacks an identity proposal")
                candidate_id = target_to_candidate[target]
                candidate_assertions_by_target.setdefault(target, []).append(index)
                proposal = proposals[candidate_id]
                identity_verdict = verdicts[candidate_id]
                expected_outcome = {
                    ContributionIdentityVerdictKind.CONFIRM_EXISTING: (
                        IdentityOutcome.RESOLVED_EXISTING
                    ),
                    ContributionIdentityVerdictKind.CREATE_NEW: IdentityOutcome.CREATED_NEW,
                    ContributionIdentityVerdictKind.REJECT_CANDIDATE: IdentityOutcome.REJECTED,
                }[identity_verdict.verdict]
                if after.identity_resolution_outcome is not expected_outcome:
                    raise ValueError("reviewed node identity outcome disagrees with verdict")
                if (
                    identity_verdict.verdict
                    is ContributionIdentityVerdictKind.CREATE_NEW
                    and after.assertion_kind == "label"
                    and after.acceptance_state is not AcceptanceState.ACCEPTED
                ):
                    raise ValueError("create_new requires an accepted label assertion")
                if (
                    identity_verdict.verdict
                    is ContributionIdentityVerdictKind.REJECT_CANDIDATE
                    and after.acceptance_state is not AcceptanceState.REJECTED
                ):
                    raise ValueError(
                        "reject_candidate requires every node assertion to be rejected"
                    )
                if proposal.target_object_id != target:
                    raise ValueError("reviewed node target disagrees with proposal")

        for target, candidate_id in target_to_candidate.items():
            identity_verdict = verdicts[candidate_id]
            if identity_verdict.verdict is not ContributionIdentityVerdictKind.CREATE_NEW:
                continue
            label_assertions = [
                assertion
                for assertion in reviewed.assertions
                if assertion.assertion_kind == "label"
                and assertion.subject_object_id == target
            ]
            if len(label_assertions) != 1:
                raise ValueError("create_new requires exactly one label assertion")
            if label_assertions[0].acceptance_state is not AcceptanceState.ACCEPTED:
                raise ValueError("create_new requires an accepted label assertion")

        for target, candidate_id in target_to_candidate.items():
            identity_verdict = verdicts[candidate_id]
            if identity_verdict.verdict is ContributionIdentityVerdictKind.REJECT_CANDIDATE:
                for assertion in reviewed.assertions:
                    if (
                        assertion.subject_object_id == target
                        or assertion.object_object_id == target
                    ) and assertion.acceptance_state is not AcceptanceState.REJECTED:
                        raise ValueError(
                            "rejected candidate must close every dependent assertion"
                        )

        for assertion in reviewed.assertions:
            if assertion.assertion_kind != "relationship":
                continue
            if assertion.acceptance_state is not AcceptanceState.ACCEPTED:
                continue
            for endpoint in (assertion.subject_object_id, assertion.object_object_id):
                candidate_id = target_to_candidate.get(endpoint or "")
                if candidate_id is not None and (
                    verdicts[candidate_id].verdict
                    is ContributionIdentityVerdictKind.REJECT_CANDIDATE
                ):
                    raise ValueError(
                        "accepted relationship references a rejected candidate"
                    )

        if contribution_payload_sha256(candidate) != record.stored_candidate_sha256:
            raise ValueError("stored candidate contribution digest drifted")
        if contribution_payload_sha256(reviewed) != record.reviewed_contribution_sha256:
            raise ValueError("reviewed contribution digest drifted")
        return self
