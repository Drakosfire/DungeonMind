"""Authority and orchestration for one-shot finalized v2 contribution review.

This is the ``dm_graph_contribution_v2`` counterpart of
``contribution_review.finalize_contribution_review``.  It enforces the same
governance invariants — explicit ``confirm_commit`` capability, exact
confirmation receipt, pinned-parent preflight, atomic bundle write — while
preserving the candidate's source kind, provenance, corrections, unresolved
mentions, and diagnostics verbatim into the reviewed successor.
"""

from __future__ import annotations

from typing import NoReturn

from pydantic import ValidationError

from ..contracts.capability import CapabilityEffect, CapabilityPolicy
from ..contracts.contribution import (
    ContributionStatus,
    GraphContributionV2,
)
from ..contracts.contribution_review import (
    derive_review_id,
    derive_reviewed_contribution_id,
)
from ..contracts.contribution_review_v2 import (
    FINALIZE_REVIEW_V2_TOOL,
    ContributionReviewRecordV2,
    ContributionReviewStateV2,
    ContributionReviewSubmissionV2,
    contribution_v2_payload_sha256,
    reviewed_v2_identity_outcome,
)
from ..contracts.projection import Admissibility
from ..domain.canonical import canonical_sha256
from ..domain.capability import evaluate_capability
from ..domain.errors import (
    CapabilityDeniedError,
    ContributionReviewValidationError,
    HeadNotFoundError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from .repositories import ContributionReviewRepository, WorldGraphRepository


def _validation_error(reason: str) -> NoReturn:
    raise ContributionReviewValidationError(
        "contribution review submission is not valid",
        details={"reason": reason},
    ) from None


def _require_policy_scope(
    policy: CapabilityPolicy,
    submission: ContributionReviewSubmissionV2,
) -> None:
    scope = policy.graph_scope
    intent = submission.intent
    if scope is None:
        raise CapabilityDeniedError(
            "finalized contribution review requires a graph scope",
            details={"reason": "missing_graph_scope"},
        )
    if scope.admissibility is not Admissibility.GM:
        raise CapabilityDeniedError(
            "finalized contribution review requires GM admissibility",
            details={"reason": "non_gm_admissibility"},
        )
    if scope.world_id != intent.world_id:
        raise CapabilityDeniedError(
            "capability world scope does not match review intent",
            details={"reason": "world_scope_mismatch"},
        )
    if scope.campaign_id != intent.campaign_id:
        raise CapabilityDeniedError(
            "capability campaign scope does not match review intent",
            details={"reason": "campaign_scope_mismatch"},
        )
    if scope.revision_pin != intent.plan_ref.expected_parent_revision_id:
        raise CapabilityDeniedError(
            "capability revision pin does not match review parent",
            details={"reason": "revision_pin_mismatch"},
        )


def _build_review_state(
    submission: ContributionReviewSubmissionV2,
) -> ContributionReviewStateV2:
    intent = submission.intent
    candidate = intent.candidate_contribution.model_copy(deep=True)
    candidate.status = ContributionStatus.SUPERSEDED
    try:
        candidate = GraphContributionV2.model_validate(candidate.model_dump(mode="json"))
    except ValidationError:
        _validation_error("candidate_lifecycle_transition")

    proposals_by_target = {
        proposal.target_object_id: proposal for proposal in intent.identity_proposals
    }
    identity_verdicts = {verdict.candidate_id: verdict for verdict in intent.identity_verdicts}
    assertion_verdicts = {verdict.assertion_id: verdict for verdict in intent.assertion_verdicts}
    assertions: list[dict[str, object]] = []
    for assertion in intent.candidate_contribution.assertions:
        verdict = assertion_verdicts[assertion.assertion_id]
        payload = assertion.model_dump(mode="json")
        payload["acceptance_state"] = verdict.acceptance_state.value
        if assertion.assertion_kind in {"node", "alias"}:
            proposal = proposals_by_target.get(assertion.subject_object_id or "")
            if proposal is None:
                _validation_error("node_target_missing_identity_proposal")
            identity_verdict = identity_verdicts[proposal.candidate_id]
            payload["identity_resolution_outcome"] = reviewed_v2_identity_outcome(
                identity_verdict.verdict
            ).value
        assertions.append(payload)

    review_id = derive_review_id(
        operation_id=intent.operation_id,
        review_intent_sha256=intent.review_intent_sha256,
        world_id=intent.world_id,
    )
    reviewed_contribution_id = derive_reviewed_contribution_id(
        review_id=review_id,
        candidate_contribution_id=candidate.contribution_id,
    )
    reviewed_payload = candidate.model_dump(mode="json")
    reviewed_payload.update(
        {
            "contribution_id": reviewed_contribution_id,
            "status": ContributionStatus.ACTIVE.value,
            "supersedes_contribution_id": candidate.contribution_id,
            "produced_at": intent.reviewed_at.isoformat(),
            "authored_by": intent.reviewer_id,
            "assertions": assertions,
        }
    )
    try:
        reviewed = GraphContributionV2.model_validate(reviewed_payload)
        record = ContributionReviewRecordV2(
            review_id=review_id,
            operation_id=intent.operation_id,
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            plan_ref=intent.plan_ref,
            review_intent_sha256=intent.review_intent_sha256,
            candidate_preview_sha256=intent.plan_ref.candidate_contribution_sha256,
            stored_candidate_contribution_id=candidate.contribution_id,
            stored_candidate_sha256=contribution_v2_payload_sha256(candidate),
            reviewed_contribution_id=reviewed.contribution_id,
            reviewed_contribution_sha256=contribution_v2_payload_sha256(reviewed),
            identity_proposals=intent.identity_proposals,
            identity_verdicts=intent.identity_verdicts,
            assertion_verdicts=intent.assertion_verdicts,
            reviewer_id=intent.reviewer_id,
            reviewed_at=intent.reviewed_at,
            confirmation_id=submission.confirmation.confirmation_id,
        )
        return ContributionReviewStateV2(
            record=record,
            candidate_contribution=candidate,
            reviewed_contribution=reviewed,
        )
    except ValidationError:
        _validation_error("review_state_contract_rejected")


def finalize_contribution_review_v2(
    submission: ContributionReviewSubmissionV2,
    *,
    capability_policy: CapabilityPolicy,
    world_graph_repository: WorldGraphRepository,
    review_repository: ContributionReviewRepository,
) -> ContributionReviewStateV2:
    """Finalize one complete, explicitly confirmed v2 review atomically."""
    try:
        verified_submission = ContributionReviewSubmissionV2.model_validate(
            submission.model_dump(mode="json")
        )
    except ValidationError:
        _validation_error("submission_contract_rejected")

    evaluate_capability(
        capability_policy,
        tool_name=FINALIZE_REVIEW_V2_TOOL,
        effect=CapabilityEffect.COMMIT,
    )
    _require_policy_scope(capability_policy, verified_submission)

    intent = verified_submission.intent
    head = world_graph_repository.get_head(intent.world_id)
    if head is None:
        raise HeadNotFoundError(
            f"world head {intent.world_id!r} not found",
        )
    expected_parent = intent.plan_ref.expected_parent_revision_id
    if head.head_revision_id != expected_parent:
        raise StaleParentRevisionError(
            world_id=intent.world_id,
            expected_parent_revision_id=expected_parent,
            actual_head_revision_id=head.head_revision_id,
        )
    revision = world_graph_repository.get_revision(intent.world_id, expected_parent)
    if revision is None:
        raise RevisionNotFoundError(f"revision {expected_parent!r} not found for review parent")
    envelope = revision.revision
    plan_ref = intent.plan_ref
    if (
        envelope.world_id != intent.world_id
        or envelope.revision_id != expected_parent
        or envelope.graph_schema != plan_ref.base_graph_schema
        or envelope.graph_payload_sha256 != plan_ref.base_graph_payload_sha256
        or canonical_sha256(revision.graph_payload) != envelope.graph_payload_sha256
    ):
        _validation_error("review_parent_revision_drift")

    state = _build_review_state(verified_submission)
    return review_repository.finalize(state)


def load_contribution_review_v2(
    world_id: str,
    review_id: str,
    *,
    review_repository: ContributionReviewRepository,
) -> ContributionReviewStateV2 | None:
    """Load one exact reconstructed finalized v2 review state."""
    state = review_repository.get(world_id, review_id)
    if state is None:
        return None
    if not isinstance(state, ContributionReviewStateV2):
        raise ContributionReviewValidationError(
            "stored contribution review is not a v2 review",
            details={"reason": "review_schema_mismatch"},
        )
    return state
