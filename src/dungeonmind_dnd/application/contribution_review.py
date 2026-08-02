"""D&D Threat adapter for finalized generic contribution review.

The adapter is intentionally repository-blind.  It accepts one fully
validated, content-bound B.2d plan and translates its safe generic review
surface into a kernel ``ContributionReviewIntent``.  It never evaluates
capability, creates a receipt, or writes persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import NoReturn

from pydantic import ValidationError

from dungeonmind.contracts.contribution import AcceptanceState
from dungeonmind.contracts.contribution_review import (
    ContributionAssertionVerdict,
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionIdentityVerdictKind,
    ContributionPlanRef,
    ContributionReviewIntent,
    contribution_payload_sha256,
    derive_review_intent_sha256,
)
from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.contribution_planning import (
    DndThreatContributionPlan,
    DndThreatPlanStatus,
)
from ..domain.errors import DndContributionPlanningError


def _review_error(
    reason: str, *, details: dict[str, object] | None = None
) -> NoReturn:
    raise DndContributionPlanningError(
        "D&D contribution review intent could not be built",
        details={"reason": reason, **(details or {})},
    ) from None


def _coerce_identity_verdict(value: object) -> ContributionIdentityVerdictKind:
    try:
        return (
            value
            if isinstance(value, ContributionIdentityVerdictKind)
            else ContributionIdentityVerdictKind(str(value))
        )
    except ValueError:
        _review_error("invalid_identity_verdict")


def _coerce_acceptance_state(value: object) -> AcceptanceState:
    try:
        state = value if isinstance(value, AcceptanceState) else AcceptanceState(str(value))
    except ValueError:
        _review_error("invalid_assertion_verdict")
    if state is AcceptanceState.CANDIDATE:
        _review_error("candidate_assertion_verdict_forbidden")
    return state


def build_threat_contribution_review_intent(
    plan: DndThreatContributionPlan,
    *,
    operation_id: str,
    assertion_verdicts: Mapping[str, AcceptanceState],
    identity_verdicts: Mapping[str, ContributionIdentityVerdictKind],
    reviewer_id: str,
    reviewed_at: datetime,
) -> ContributionReviewIntent:
    """Translate one ready B.2d plan into a complete generic review intent."""
    if plan.status is not DndThreatPlanStatus.READY_FOR_REVIEW:
        _review_error("plan_not_ready")
    if plan.preview_content_sha256 is None:
        _review_error("missing_preview_content_digest")
    contribution = plan.proposed_contribution
    if contribution is None:
        _review_error("missing_candidate_contribution")

    try:
        # Re-validate the serialized form so callers cannot pass a mutated model
        # instance that bypassed the plan contract's model validator.
        verified_plan = DndThreatContributionPlan.model_validate(
            plan.model_dump(mode="json")
        )
    except ValidationError:
        _review_error("invalid_serialized_plan")

    contribution = verified_plan.proposed_contribution
    if contribution is None or verified_plan.preview_content_sha256 is None:
        _review_error("missing_candidate_contribution")

    resolutions = sorted(
        verified_plan.candidate_resolutions, key=lambda item: item.candidate_id
    )
    expected_candidate_ids = {item.candidate_id for item in resolutions}
    supplied_candidate_ids = set(identity_verdicts)
    if supplied_candidate_ids != expected_candidate_ids:
        _review_error(
            "identity_verdict_coverage",
            details={
                "missing_candidate_ids": sorted(expected_candidate_ids - supplied_candidate_ids),
                "unknown_candidate_ids": sorted(supplied_candidate_ids - expected_candidate_ids),
            },
        )

    proposals = [
        ContributionIdentityProposal(
            candidate_id=resolution.candidate_id,
            candidate_kind=resolution.candidate_kind,
            planned_outcome=resolution.outcome,
            target_object_id=resolution.target_object_id or "",
            matched_object_ids=list(resolution.matched_object_ids),
        )
        for resolution in resolutions
    ]
    generic_identity_verdicts = [
        ContributionIdentityVerdict(
            candidate_id=resolution.candidate_id,
            verdict=_coerce_identity_verdict(identity_verdicts[resolution.candidate_id]),
            target_object_id=resolution.target_object_id or "",
        )
        for resolution in resolutions
    ]

    expected_assertion_ids = {item.assertion_id for item in contribution.assertions}
    supplied_assertion_ids = set(assertion_verdicts)
    if supplied_assertion_ids != expected_assertion_ids:
        _review_error(
            "assertion_verdict_coverage",
            details={
                "missing_assertion_ids": sorted(
                    expected_assertion_ids - supplied_assertion_ids
                ),
                "unknown_assertion_ids": sorted(
                    supplied_assertion_ids - expected_assertion_ids
                ),
            },
        )
    generic_assertion_verdicts = [
        ContributionAssertionVerdict(
            assertion_id=assertion_id,
            acceptance_state=_coerce_acceptance_state(assertion_verdicts[assertion_id]),
        )
        for assertion_id in sorted(supplied_assertion_ids)
    ]

    try:
        plan_ref = ContributionPlanRef(
            source_plan_schema=verified_plan.schema_version,
            source_plan_id=verified_plan.plan_id,
            source_plan_sha256=canonical_sha256(
                verified_plan.model_dump(mode="json")
            ),
            source_input_sha256=verified_plan.candidate_packet_sha256,
            preview_content_sha256=verified_plan.preview_content_sha256,
            candidate_contribution_sha256=contribution_payload_sha256(contribution),
            expected_parent_revision_id=verified_plan.expected_parent_revision_id,
            base_graph_schema=verified_plan.base_graph_schema,
            base_graph_payload_sha256=verified_plan.base_graph_payload_sha256,
            semantic_profile=verified_plan.semantic_profile,
        )
        intent_digest = derive_review_intent_sha256(
            operation_id=operation_id,
            world_id=verified_plan.world_id,
            campaign_id=verified_plan.campaign_id,
            plan_ref=plan_ref,
            candidate_contribution=contribution,
            identity_proposals=proposals,
            identity_verdicts=generic_identity_verdicts,
            assertion_verdicts=generic_assertion_verdicts,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
        )
        return ContributionReviewIntent(
            operation_id=operation_id,
            world_id=verified_plan.world_id,
            campaign_id=verified_plan.campaign_id,
            plan_ref=plan_ref,
            candidate_contribution=contribution,
            identity_proposals=proposals,
            identity_verdicts=generic_identity_verdicts,
            assertion_verdicts=generic_assertion_verdicts,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            review_intent_sha256=intent_digest,
        )
    except ValidationError:
        _review_error("review_intent_contract_rejected")
