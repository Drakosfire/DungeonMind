"""Finalized contribution-review contracts for ``dm_graph_contribution_v2``.

This v2 family is the governed write seam for ``dm_union_graph_v6`` worlds
(see ``Docs/Decisions/ADR-0020``).  It mirrors the v1 family's governance
shape — content-bound intent, explicit verdicts, identity disposition,
confirmation receipt, atomic record/candidate/reviewed state — but carries
the durable v2 contribution contract so real confirmed contributions (Buddy
kernel assertion vocabulary, typed correction history, per-assertion
provenance) can be reviewed and published without lossy translation.

No v1 contract is modified by this module; v1 sub-records whose semantics are
unchanged (plan ref, identity proposal/verdict, assertion verdict) are reused
directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel
from .contribution import (
    AcceptanceState,
    ContributionStatus,
    GraphContributionAssertionV2,
    GraphContributionV2,
)
from .contribution_review import (
    _CONFIRMATION_ID,
    _OPERATION_ID,
    _REVIEW_ID,
    ContributionAssertionVerdict,
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionIdentityVerdictKind,
    ContributionPlanRef,
    _canonical_sha256,
    _require_digest,
    _require_nonblank,
    _require_unique_sorted,
    _validate_identity_decisions,
    derive_confirmation_id,
    derive_review_id,
    derive_reviewed_contribution_id,
)
from .identity import IdentityOutcome

CONTRIBUTION_REVIEW_INTENT_V2_SCHEMA = "dm_contribution_review_intent_v2"
COMMIT_CONFIRMATION_RECEIPT_V2_SCHEMA = "dm_commit_confirmation_receipt_v2"
CONTRIBUTION_REVIEW_SUBMISSION_V2_SCHEMA = "dm_contribution_review_submission_v2"
CONTRIBUTION_REVIEW_RECORD_V2_SCHEMA = "dm_contribution_review_record_v2"
CONTRIBUTION_REVIEW_STATE_V2_SCHEMA = "dm_contribution_review_state_v2"

FINALIZE_REVIEW_V2_TOOL = "dungeonmind.finalize_contribution_review_v2"
FINALIZE_REVIEW_V2_EFFECT = "commit"

_REVIEW_INTENT_V2_DIGEST_SCHEMA = CONTRIBUTION_REVIEW_INTENT_V2_SCHEMA

# Layering note: contracts must not import from the application layer, so the
# v6 graph schema literal is duplicated here.  The v6 materializer re-checks
# the plan ref against the authoritative constant in application.graph_snapshot.
_UNION_GRAPH_V6 = "dm_union_graph_v6"

# The Buddy kernel assertion vocabulary this seam can review and materialize.
# Candidate assertions of any other kind must carry a rejected verdict; they
# are never materialized.
REVIEWABLE_V2_ASSERTION_KINDS = frozenset({"node", "edge", "alias", "attribute", "evidence_ref"})

# Identity-affecting kinds whose subject targets require identity disposition.
_IDENTITY_TARGETED_V2_KINDS = frozenset({"node", "alias"})

# Identity outcomes that never create graph mutations on merge/replay.  The v6
# materializer skips accepted assertions carrying one of these outcomes,
# mirroring Buddy's contribution merge semantics exactly.
NON_MUTATING_IDENTITY_OUTCOMES = frozenset(
    {
        IdentityOutcome.AMBIGUOUS,
        IdentityOutcome.BLOCKED_COLLISION,
        IdentityOutcome.REJECTED,
        IdentityOutcome.PROVISIONAL_NEW,
    }
)


def contribution_v2_payload_sha256(contribution: GraphContributionV2) -> str:
    """Digest the complete serialized v2 contribution payload."""
    return _canonical_sha256(contribution.model_dump(mode="json"))


def derive_review_intent_sha256_v2(
    *,
    operation_id: str,
    world_id: str,
    campaign_id: str | None,
    plan_ref: ContributionPlanRef,
    candidate_contribution: GraphContributionV2,
    identity_proposals: list[ContributionIdentityProposal],
    identity_verdicts: list[ContributionIdentityVerdict],
    assertion_verdicts: list[ContributionAssertionVerdict],
    reviewer_id: str,
    reviewed_at: datetime,
) -> str:
    """Derive the v2 intent digest from every field except the digest itself."""
    material = {
        "schema": _REVIEW_INTENT_V2_DIGEST_SCHEMA,
        "operation_id": operation_id,
        "world_id": world_id,
        "campaign_id": campaign_id,
        "plan_ref": plan_ref.model_dump(mode="json"),
        "candidate_contribution": candidate_contribution.model_dump(mode="json"),
        "identity_proposals": [item.model_dump(mode="json") for item in identity_proposals],
        "identity_verdicts": [item.model_dump(mode="json") for item in identity_verdicts],
        "assertion_verdicts": [item.model_dump(mode="json") for item in assertion_verdicts],
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at.isoformat(),
    }
    return _canonical_sha256(material)


def _require_assertion_text(value: str | None, field_name: str) -> None:
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must be non-blank")


def _require_absent_assertion_field(value: str | None, field_name: str) -> None:
    if value is not None:
        raise ValueError(f"{field_name} must be absent")


def _validate_v2_candidate_assertion_shape(
    assertion: GraphContributionAssertionV2,
) -> None:
    """Minimal per-kind shape for reviewable v2 candidate assertions.

    ``value`` payloads stay deliberately free-form here; the v6 materializer
    owns materialization-relevant shape enforcement and fails closed.
    """
    kind = assertion.assertion_kind
    if kind == "node":
        _require_assertion_text(assertion.subject_object_id, "node subject")
        _require_absent_assertion_field(assertion.object_object_id, "node object")
        _require_absent_assertion_field(assertion.predicate, "node predicate")
    elif kind == "edge":
        _require_assertion_text(assertion.subject_object_id, "edge subject")
        _require_assertion_text(assertion.object_object_id, "edge object")
        _require_assertion_text(assertion.predicate, "edge predicate")
    elif kind == "alias":
        _require_assertion_text(assertion.subject_object_id, "alias subject")
        _require_absent_assertion_field(assertion.object_object_id, "alias object")
        _require_absent_assertion_field(assertion.predicate, "alias predicate")
    elif kind == "attribute":
        _require_assertion_text(assertion.subject_object_id, "attribute subject")
        _require_absent_assertion_field(assertion.object_object_id, "attribute object")
        _require_absent_assertion_field(assertion.predicate, "attribute predicate")
    elif kind == "evidence_ref":
        _require_absent_assertion_field(assertion.object_object_id, "evidence_ref object")
        _require_absent_assertion_field(assertion.predicate, "evidence_ref predicate")


class ContributionReviewIntentV2(DungeonMindModel):
    """Complete, content-bound one-shot review input for a v2 contribution."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_contribution_review_intent_v2"] = (
        CONTRIBUTION_REVIEW_INTENT_V2_SCHEMA
    )
    operation_id: str
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    plan_ref: ContributionPlanRef
    candidate_contribution: GraphContributionV2
    identity_proposals: list[ContributionIdentityProposal] = []
    identity_verdicts: list[ContributionIdentityVerdict] = []
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
        if self.plan_ref.candidate_contribution_sha256 != (
            contribution_v2_payload_sha256(self.candidate_contribution)
        ):
            raise ValueError("candidate contribution digest does not match plan ref")
        if self.plan_ref.base_graph_schema != _UNION_GRAPH_V6:
            raise ValueError("v2 review intents require a dm_union_graph_v6 base")
        contribution = self.candidate_contribution
        if contribution.world_id != self.world_id:
            raise ValueError("candidate contribution world differs from review intent")
        if contribution.campaign_scope != self.campaign_id:
            raise ValueError("candidate contribution campaign differs from review intent")
        if contribution.status is not ContributionStatus.ACTIVE:
            raise ValueError("review intents require an active candidate contribution")
        if contribution.supersedes_contribution_id is not None:
            raise ValueError("candidate contribution must not supersede another contribution")
        if contribution.identity_decision_ids:
            raise ValueError("review intents contain no identity decision IDs")

        assertions = contribution.assertions
        assertion_ids = [assertion.assertion_id for assertion in assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("candidate assertion IDs must be unique")
        for assertion in assertions:
            if assertion.acceptance_state is not AcceptanceState.CANDIDATE:
                raise ValueError("candidate contribution assertions are not reviewable")
            if (
                not assertion.evidence_refs
                and not assertion.source_artifact_id
                and not assertion.source_revision_id
            ):
                raise ValueError(
                    "candidate assertions require evidence_refs or a source "
                    "artifact/revision identity"
                )
            if assertion.assertion_kind in REVIEWABLE_V2_ASSERTION_KINDS:
                _validate_v2_candidate_assertion_shape(assertion)

        _require_unique_sorted(
            [item.assertion_id for item in self.assertion_verdicts],
            field_name="assertion_verdicts",
        )
        verdicts_by_assertion = {item.assertion_id: item for item in self.assertion_verdicts}
        if set(assertion_ids) != set(verdicts_by_assertion):
            raise ValueError("assertion verdicts must cover every candidate assertion exactly once")
        for assertion in assertions:
            if (
                assertion.assertion_kind not in REVIEWABLE_V2_ASSERTION_KINDS
                and verdicts_by_assertion[assertion.assertion_id].acceptance_state
                is not AcceptanceState.REJECTED
            ):
                raise ValueError(
                    "accepted assertions must use the reviewable v2 assertion "
                    "vocabulary (node | edge | alias | attribute | evidence_ref)"
                )

        proposals = self.identity_proposals
        _validate_identity_decisions(proposals, self.identity_verdicts)
        identity_targets = {
            assertion.subject_object_id
            for assertion in assertions
            if assertion.assertion_kind in _IDENTITY_TARGETED_V2_KINDS
        }
        proposal_targets = {item.target_object_id for item in proposals}
        if proposal_targets != identity_targets:
            raise ValueError(
                "identity proposals must cover exactly the candidate node/alias subject targets"
            )

        expected_digest = derive_review_intent_sha256_v2(
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


class CommitConfirmationReceiptV2(DungeonMindModel):
    """Explicit caller confirmation bound to one exact v2 review intent."""

    schema_version: Literal["dm_commit_confirmation_receipt_v2"] = (
        COMMIT_CONFIRMATION_RECEIPT_V2_SCHEMA
    )
    confirmation_id: str
    operation_id: str
    review_intent_sha256: str
    actor: str = Field(min_length=1)
    tool_name: Literal["dungeonmind.finalize_contribution_review_v2"] = FINALIZE_REVIEW_V2_TOOL
    effect: Literal["commit"] = FINALIZE_REVIEW_V2_EFFECT
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    expected_parent_revision_id: str = Field(min_length=1)
    confirmed_at: datetime

    @field_validator("confirmation_id")
    @classmethod
    def _validate_confirmation_id(cls, value: str) -> str:
        if not _CONFIRMATION_ID.fullmatch(value):
            raise ValueError("confirmation_id must be confirm:<32 lowercase hex>")
        return value

    @field_validator("operation_id")
    @classmethod
    def _validate_operation_id(cls, value: str) -> str:
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operation_id must be reviewop:<32 lowercase hex>")
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


class ContributionReviewSubmissionV2(DungeonMindModel):
    """v2 intent plus the exact confirmation required for a durable commit."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_contribution_review_submission_v2"] = (
        CONTRIBUTION_REVIEW_SUBMISSION_V2_SCHEMA
    )
    intent: ContributionReviewIntentV2
    confirmation: CommitConfirmationReceiptV2

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
        if receipt.expected_parent_revision_id != intent.plan_ref.expected_parent_revision_id:
            raise ValueError("confirmation parent does not match plan ref")
        if receipt.confirmed_at != intent.reviewed_at:
            raise ValueError("confirmation time must equal reviewed_at")
        return self


class ContributionReviewRecordV2(DungeonMindModel):
    """Durable finalized v2 review metadata; contribution payloads live beside it."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_contribution_review_record_v2"] = (
        CONTRIBUTION_REVIEW_RECORD_V2_SCHEMA
    )
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
    identity_proposals: list[ContributionIdentityProposal] = []
    identity_verdicts: list[ContributionIdentityVerdict] = []
    assertion_verdicts: list[ContributionAssertionVerdict] = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    confirmation_id: str
    status: Literal["finalized"] = "finalized"

    @field_validator("review_id")
    @classmethod
    def _validate_review_id(cls, value: str) -> str:
        if not _REVIEW_ID.fullmatch(value):
            raise ValueError("review_id must be review:<32 lowercase hex>")
        return value

    @field_validator("operation_id")
    @classmethod
    def _validate_operation_id(cls, value: str) -> str:
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operation_id must be reviewop:<32 lowercase hex>")
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
            raise ValueError("confirmation_id must be confirm:<32 lowercase hex>")
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


def reviewed_v2_identity_outcome(
    verdict: ContributionIdentityVerdictKind,
) -> IdentityOutcome:
    if verdict is ContributionIdentityVerdictKind.CONFIRM_EXISTING:
        return IdentityOutcome.RESOLVED_EXISTING
    if verdict is ContributionIdentityVerdictKind.CREATE_NEW:
        return IdentityOutcome.CREATED_NEW
    return IdentityOutcome.REJECTED


class ContributionReviewStateV2(DungeonMindModel):
    """Reloadable atomic bundle of v2 record, superseded candidate, and successor."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_contribution_review_state_v2"] = CONTRIBUTION_REVIEW_STATE_V2_SCHEMA
    record: ContributionReviewRecordV2
    candidate_contribution: GraphContributionV2
    reviewed_contribution: GraphContributionV2

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
        if reviewed.status is not ContributionStatus.ACTIVE:
            raise ValueError("reviewed contribution must be active")
        if reviewed.source_kind is not candidate.source_kind:
            raise ValueError("reviewed contribution source kind drifted")
        if reviewed.supersedes_contribution_id != candidate.contribution_id:
            raise ValueError("reviewed contribution must supersede candidate")
        if reviewed.authored_by != record.reviewer_id or reviewed.produced_at != record.reviewed_at:
            raise ValueError("reviewed author/time disagrees with review record")
        if candidate.identity_decision_ids or reviewed.identity_decision_ids:
            raise ValueError("review state cannot append identity decisions")
        if candidate.unresolved_mentions != reviewed.unresolved_mentions:
            raise ValueError("reviewed contribution must preserve unresolved mentions")
        if candidate.diagnostics != reviewed.diagnostics:
            raise ValueError("reviewed contribution must preserve diagnostics")
        if candidate.assertion_corrections != reviewed.assertion_corrections:
            raise ValueError("reviewed contribution must preserve assertion corrections")

        candidate_preview = candidate.model_copy(
            deep=True, update={"status": ContributionStatus.ACTIVE}
        )
        if (
            contribution_v2_payload_sha256(candidate_preview)
            != record.plan_ref.candidate_contribution_sha256
        ):
            raise ValueError("stored candidate no longer matches the reviewed preview")
        expected_intent_digest = derive_review_intent_sha256_v2(
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
        assertion_verdicts = {item.assertion_id: item for item in record.assertion_verdicts}
        if set(assertion_verdicts) != {item.assertion_id for item in candidate.assertions}:
            raise ValueError("review record assertion verdict coverage is incomplete")
        if set(proposals) != set(verdicts):
            raise ValueError("review record identity verdict coverage is incomplete")
        target_to_candidate = {
            item.target_object_id: item.candidate_id for item in record.identity_proposals
        }
        for before, after in zip(candidate.assertions, reviewed.assertions, strict=True):
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
            if after.assertion_kind in _IDENTITY_TARGETED_V2_KINDS:
                target = after.subject_object_id
                if target is None or target not in target_to_candidate:
                    raise ValueError("reviewed node target lacks an identity proposal")
                candidate_id = target_to_candidate[target]
                identity_verdict = verdicts[candidate_id]
                expected_outcome = reviewed_v2_identity_outcome(identity_verdict.verdict)
                if after.identity_resolution_outcome is not expected_outcome:
                    raise ValueError("reviewed node identity outcome disagrees with verdict")
                if (
                    identity_verdict.verdict is ContributionIdentityVerdictKind.REJECT_CANDIDATE
                    and after.acceptance_state is not AcceptanceState.REJECTED
                ):
                    raise ValueError(
                        "reject_candidate requires every node assertion to be rejected"
                    )
                if proposals[candidate_id].target_object_id != target:
                    raise ValueError("reviewed node target disagrees with proposal")
            elif after.identity_resolution_outcome != before.identity_resolution_outcome:
                raise ValueError("reviewed non-identity assertion outcome drifted from candidate")

        for target, candidate_id in target_to_candidate.items():
            identity_verdict = verdicts[candidate_id]
            if identity_verdict.verdict is not ContributionIdentityVerdictKind.CREATE_NEW:
                continue
            node_assertions = [
                assertion
                for assertion in reviewed.assertions
                if assertion.assertion_kind == "node" and assertion.subject_object_id == target
            ]
            if len(node_assertions) != 1:
                raise ValueError("create_new requires exactly one node assertion")
            if node_assertions[0].acceptance_state is not AcceptanceState.ACCEPTED:
                raise ValueError("create_new requires an accepted node assertion")

        for target, candidate_id in target_to_candidate.items():
            identity_verdict = verdicts[candidate_id]
            if identity_verdict.verdict is ContributionIdentityVerdictKind.REJECT_CANDIDATE:
                for assertion in reviewed.assertions:
                    if (
                        assertion.subject_object_id == target
                        or assertion.object_object_id == target
                    ) and assertion.acceptance_state is not AcceptanceState.REJECTED:
                        raise ValueError("rejected candidate must close every dependent assertion")

        for assertion in reviewed.assertions:
            if assertion.assertion_kind != "edge":
                continue
            if assertion.acceptance_state is not AcceptanceState.ACCEPTED:
                continue
            for endpoint in (assertion.subject_object_id, assertion.object_object_id):
                candidate_id = target_to_candidate.get(endpoint or "")
                if candidate_id is not None and (
                    verdicts[candidate_id].verdict
                    is ContributionIdentityVerdictKind.REJECT_CANDIDATE
                ):
                    raise ValueError("accepted edge references a rejected candidate")

        if contribution_v2_payload_sha256(candidate) != record.stored_candidate_sha256:
            raise ValueError("stored candidate contribution digest drifted")
        if contribution_v2_payload_sha256(reviewed) != record.reviewed_contribution_sha256:
            raise ValueError("reviewed contribution digest drifted")
        return self
