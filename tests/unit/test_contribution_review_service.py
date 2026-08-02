"""Authority and finalized-review service proof."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dungeonmind.application.contribution_review import finalize_contribution_review
from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.contracts.contribution import AcceptanceState
from dungeonmind.contracts.contribution_review import (
    CommitConfirmationReceipt,
    ContributionReviewSubmission,
    derive_confirmation_id,
)
from dungeonmind.contracts.graph import WorldGraphHead
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    ContributionReviewAlreadyFinalizedError,
    ContributionReviewValidationError,
    IdempotencyConflictError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
)
from dungeonmind_dnd.application.contribution_review import (
    build_threat_contribution_review_intent,
)

from .test_dnd_threat_contribution_planning import _stored_revision
from .test_dnd_threat_contribution_review_adapter import (
    OPERATION_ID,
    REVIEWED_AT,
    REVIEWER_ID,
    _intent,
    _plan,
    _verdicts,
)


class _GraphRepository:
    def __init__(self, *, head_revision_id: str | None = None) -> None:
        self.revision = _stored_revision()
        self.head_revision_id = head_revision_id or self.revision.revision.revision_id

    def get_head(self, world_id: str) -> WorldGraphHead:
        return WorldGraphHead(
            world_id=world_id,
            head_revision_id=self.head_revision_id,
            updated_at=REVIEWED_AT,
        )

    def get_revision(self, world_id: str, revision_id: str):
        return self.revision if revision_id == self.revision.revision.revision_id else None


def _submission(intent=None) -> ContributionReviewSubmission:
    intent = intent or _intent()
    confirmation_id = derive_confirmation_id(
        operation_id=intent.operation_id,
        review_intent_sha256=intent.review_intent_sha256,
        actor=intent.reviewer_id,
        confirmed_at=intent.reviewed_at,
    )
    return ContributionReviewSubmission(
        intent=intent,
        confirmation=CommitConfirmationReceipt(
            confirmation_id=confirmation_id,
            operation_id=intent.operation_id,
            review_intent_sha256=intent.review_intent_sha256,
            actor=intent.reviewer_id,
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            expected_parent_revision_id=intent.plan_ref.expected_parent_revision_id,
            confirmed_at=intent.reviewed_at,
        ),
    )


def _policy(intent, *, revision_pin: str | None = None) -> CapabilityPolicy:
    return CapabilityPolicy(
        policy_id="pol:synthetic-review",
        graph_scope=GraphScope(
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            admissibility=Admissibility.GM,
            revision_pin=(
                revision_pin
                if revision_pin is not None
                else intent.plan_ref.expected_parent_revision_id
            ),
        ),
        enabled_tools=["dungeonmind.finalize_contribution_review"],
        tool_rules=[
            ToolCapabilityRule(
                tool_name="dungeonmind.finalize_contribution_review",
                category=CapabilityCategory.CONFIRM_COMMIT,
                allowed_effects=[CapabilityEffect.COMMIT],
            )
        ],
    )


def _repositories() -> tuple[InMemoryContributionReviewRepository, InMemoryContributionRepository]:
    contributions = InMemoryContributionRepository()
    return InMemoryContributionReviewRepository(contributions), contributions


def test_finalize_review_persists_candidate_and_reviewed_successor() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    state = finalize_contribution_review(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    assert state.record.status == "finalized"
    assert state.candidate_contribution.status.value == "superseded"
    assert state.reviewed_contribution.status.value == "active"
    assert state.reviewed_contribution.source_kind.value == "graph_review"
    assert sum(
        item.acceptance_state is AcceptanceState.ACCEPTED
        for item in state.reviewed_contribution.assertions
    ) == 8
    assert sum(
        item.acceptance_state is AcceptanceState.REJECTED
        for item in state.reviewed_contribution.assertions
    ) == 2
    assert len(contributions.list_for_world(intent.world_id)) == 2
    assert reviews.get(intent.world_id, state.record.review_id) == state


def test_exact_replay_returns_same_state_without_duplicates() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    first = finalize_contribution_review(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    second = finalize_contribution_review(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    assert second == first
    assert len(contributions.list_for_world(intent.world_id)) == 2


def test_same_operation_with_changed_review_is_idempotency_conflict() -> None:
    plan = _plan()
    contribution = plan.proposed_contribution
    assert contribution is not None
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    changed = dict(assertion_verdicts)
    relationship_id = next(
        assertion.assertion_id
        for assertion in contribution.assertions
        if assertion.assertion_kind == "relationship"
    )
    changed[relationship_id] = AcceptanceState.REJECTED
    original = _intent()
    changed_intent = build_threat_contribution_review_intent(
        plan,
        operation_id=OPERATION_ID,
        assertion_verdicts=changed,
        identity_verdicts=identity_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )
    reviews, _ = _repositories()
    finalize_contribution_review(
        _submission(original),
        capability_policy=_policy(original),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    with pytest.raises(IdempotencyConflictError):
        finalize_contribution_review(
            _submission(changed_intent),
            capability_policy=_policy(changed_intent),
            world_graph_repository=_GraphRepository(),
            review_repository=reviews,
        )


def test_same_source_plan_with_new_operation_is_already_finalized() -> None:
    first = _intent()
    plan = _plan()
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    second = build_threat_contribution_review_intent(
        plan,
        operation_id="reviewop:" + "2" * 32,
        assertion_verdicts=assertion_verdicts,
        identity_verdicts=identity_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )
    reviews, _ = _repositories()
    finalize_contribution_review(
        _submission(first),
        capability_policy=_policy(first),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    with pytest.raises(ContributionReviewAlreadyFinalizedError):
        finalize_contribution_review(
            _submission(second),
            capability_policy=_policy(second),
            world_graph_repository=_GraphRepository(),
            review_repository=reviews,
        )


def test_stale_head_is_rejected_before_persistence() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    with pytest.raises(StaleParentRevisionError):
        finalize_contribution_review(
            _submission(intent),
            capability_policy=_policy(intent),
            world_graph_repository=_GraphRepository(head_revision_id="rev:stale"),
            review_repository=reviews,
        )
    assert contributions.list_for_world(intent.world_id) == []


def test_missing_revision_pin_is_denied() -> None:
    intent = _intent()
    reviews, _ = _repositories()
    policy = _policy(intent, revision_pin="rev:other")
    with pytest.raises(CapabilityDeniedError):
        finalize_contribution_review(
            _submission(intent),
            capability_policy=policy,
            world_graph_repository=_GraphRepository(),
            review_repository=reviews,
        )


def test_rejected_candidate_must_close_dependent_assertions() -> None:
    plan = _plan()
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    identity_verdicts["cand:tripod-null-calf"] = "reject_candidate"
    intent = build_threat_contribution_review_intent(
        plan,
        operation_id="reviewop:" + "3" * 32,
        assertion_verdicts=assertion_verdicts,
        identity_verdicts=identity_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )
    reviews, _ = _repositories()
    with pytest.raises(ContributionReviewValidationError):
        finalize_contribution_review(
            _submission(intent),
            capability_policy=_policy(intent),
            world_graph_repository=_GraphRepository(),
            review_repository=reviews,
        )


def test_receipt_mutation_is_rejected() -> None:
    intent = _intent()
    submission = _submission(intent).model_dump(mode="json")
    submission["confirmation"]["actor"] = "operator:other"
    with pytest.raises(ValidationError):
        ContributionReviewSubmission.model_validate(submission)
