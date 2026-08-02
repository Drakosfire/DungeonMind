"""B.2e D&D profile adapter proof."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import AcceptanceState
from dungeonmind.contracts.contribution_review import (
    CommitConfirmationReceipt,
    ContributionIdentityVerdictKind,
)
from dungeonmind_dnd.application.contribution_planning import (
    plan_threat_candidate_contribution,
)
from dungeonmind_dnd.application.contribution_review import (
    build_threat_contribution_review_intent,
)
from dungeonmind_dnd.domain.errors import DndContributionPlanningError

from .test_dnd_threat_contribution_planning import (
    ACTOR,
    PLANNED_AT,
    _dnd_reader,
    _packet,
    _stored_revision,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "dungeonmind_dnd"
    / "tripod-null-calf-review-intent-v1.json"
)
CONFIRMATION_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contribution_reviews"
    / "tripod-null-calf-confirmation-v1.json"
)
REVIEWED_AT = datetime(2026, 8, 1, 22, 0, tzinfo=UTC)
OPERATION_ID = "reviewop:" + "1" * 32
REVIEWER_ID = "operator:synthetic-gm"


def _plan():
    return plan_threat_candidate_contribution(
        _packet(),
        stored_revision=_stored_revision(),
        graph_reader=_dnd_reader(),
        actor=ACTOR,
        planned_at=PLANNED_AT,
    )


def _verdicts(plan) -> tuple[dict[str, AcceptanceState], dict[str, str]]:
    contribution = plan.proposed_contribution
    assert contribution is not None
    assertion_verdicts = {
        assertion.assertion_id: (
            AcceptanceState.REJECTED
            if assertion.assertion_kind == "alias"
            and assertion.value in {"the three-legged calf", "null-calf"}
            else AcceptanceState.ACCEPTED
        )
        for assertion in contribution.assertions
    }
    identity_verdicts = {
        resolution.candidate_id: ContributionIdentityVerdictKind.CREATE_NEW.value
        for resolution in plan.candidate_resolutions
    }
    return assertion_verdicts, identity_verdicts


def _intent():
    plan = _plan()
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    return build_threat_contribution_review_intent(
        plan,
        operation_id=OPERATION_ID,
        assertion_verdicts=assertion_verdicts,
        identity_verdicts=identity_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )


def test_review_intent_matches_fixture() -> None:
    intent = _intent()
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert intent.model_dump(mode="json") == expected
    assert len(intent.identity_proposals) == 2
    assert len(intent.assertion_verdicts) == 10


def test_confirmation_fixture_is_exactly_bound() -> None:
    receipt = CommitConfirmationReceipt.model_validate(
        json.loads(CONFIRMATION_FIXTURE_PATH.read_text(encoding="utf-8"))
    )
    intent = _intent()
    assert receipt.operation_id == intent.operation_id
    assert receipt.review_intent_sha256 == intent.review_intent_sha256
    assert receipt.actor == intent.reviewer_id
    assert receipt.confirmed_at == intent.reviewed_at


def test_blocked_plan_is_rejected() -> None:
    packet = _packet()
    packet["nodes"][0]["label"] = "Tripod Null-Calf"
    packet["nodes"][1]["surface_forms"] = ["Tripod Null-Calf", "the gate breach"]
    blocked = plan_threat_candidate_contribution(
        packet,
        stored_revision=_stored_revision(),
        graph_reader=_dnd_reader(),
        actor=ACTOR,
        planned_at=PLANNED_AT,
    )
    with pytest.raises(DndContributionPlanningError) as exc_info:
        build_threat_contribution_review_intent(
            blocked,
            operation_id=OPERATION_ID,
            assertion_verdicts={},
            identity_verdicts={},
            reviewer_id=REVIEWER_ID,
            reviewed_at=REVIEWED_AT,
        )
    assert exc_info.value.code == "dnd_contribution_planning_error"


def test_identity_verdicts_require_exact_candidate_coverage() -> None:
    plan = _plan()
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    identity_verdicts.pop("cand:tripod-null-calf")
    with pytest.raises(DndContributionPlanningError):
        build_threat_contribution_review_intent(
            plan,
            operation_id=OPERATION_ID,
            assertion_verdicts=assertion_verdicts,
            identity_verdicts=identity_verdicts,
            reviewer_id=REVIEWER_ID,
            reviewed_at=REVIEWED_AT,
        )


def test_assertion_verdicts_require_exact_coverage() -> None:
    plan = _plan()
    assertion_verdicts, identity_verdicts = _verdicts(plan)
    assertion_verdicts.pop(next(iter(assertion_verdicts)))
    with pytest.raises(DndContributionPlanningError):
        build_threat_contribution_review_intent(
            plan,
            operation_id=OPERATION_ID,
            assertion_verdicts=assertion_verdicts,
            identity_verdicts=identity_verdicts,
            reviewer_id=REVIEWER_ID,
            reviewed_at=REVIEWED_AT,
        )


def test_serialized_plan_revalidation_rejects_content_mutation() -> None:
    plan = _plan()
    payload = copy.deepcopy(plan.model_dump(mode="json"))
    payload["proposed_contribution"]["assertions"][0]["label"] = "tampered"
    from dungeonmind_dnd.contracts.contribution_planning import (
        DndThreatContributionPlan,
    )

    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)
