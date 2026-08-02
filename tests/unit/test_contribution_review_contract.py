"""Generic B.2e review contract invariants."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import AcceptanceState
from dungeonmind.contracts.contribution_review import (
    ContributionReviewIntent,
    ContributionReviewState,
    derive_review_intent_sha256,
)

from .test_contribution_review_service import _intent, _submission

STATE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contribution_reviews"
    / "tripod-null-calf-finalized-review-state-v1.json"
)


def test_intent_digest_binds_complete_content() -> None:
    intent = _intent()
    payload = intent.model_dump(mode="json")
    payload["candidate_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


def test_intent_rejects_candidate_assertion_verdict() -> None:
    intent = _intent()
    payload = intent.model_dump(mode="json")
    payload["assertion_verdicts"][0]["acceptance_state"] = AcceptanceState.CANDIDATE.value
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


def test_submission_receipt_binds_operation_digest_scope_and_time() -> None:
    submission = _submission()
    payload = submission.model_dump(mode="json")
    payload["confirmation"]["review_intent_sha256"] = "f" * 64
    with pytest.raises(ValidationError):
        type(submission).model_validate(payload)


def test_review_state_rejects_assertion_content_drift() -> None:
    from dungeonmind.application.contribution_review import _build_review_state

    state = _build_review_state(_submission())
    payload = copy.deepcopy(state.model_dump(mode="json"))
    payload["reviewed_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


def test_finalized_state_fixture_is_contract_valid() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    state = ContributionReviewState.model_validate(payload)
    assert state.record.status == "finalized"
    assert state.reviewed_contribution.contribution_id == state.record.reviewed_contribution_id


def test_generic_intent_accepts_non_dnd_source_plan_schema() -> None:
    intent = _intent()
    plan_ref = intent.plan_ref.model_copy(
        update={"source_plan_schema": "synthetic_profile_plan_v1"}
    )
    digest = derive_review_intent_sha256(
        operation_id=intent.operation_id,
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        plan_ref=plan_ref,
        candidate_contribution=intent.candidate_contribution,
        identity_proposals=intent.identity_proposals,
        identity_verdicts=intent.identity_verdicts,
        assertion_verdicts=intent.assertion_verdicts,
        reviewer_id=intent.reviewer_id,
        reviewed_at=intent.reviewed_at,
    )
    payload = intent.model_dump(mode="json")
    payload["plan_ref"] = plan_ref.model_dump(mode="json")
    payload["review_intent_sha256"] = digest
    generic = ContributionReviewIntent.model_validate(payload)
    assert generic.plan_ref.source_plan_schema == "synthetic_profile_plan_v1"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("record", "identity_verdicts", 0, "target_object_id"), "obj:other"),
        (("record", "identity_verdicts", 0, "verdict"), "confirm_existing"),
        (("record", "confirmation_id"), "confirm:" + "f" * 32),
        (("record", "review_intent_sha256"), "f" * 64),
        (("record", "reviewer_id"), "operator:other"),
        (("record", "reviewed_at"), "2026-08-02T00:00:00Z"),
        (("record", "assertion_verdicts", 0, "acceptance_state"), "rejected"),
    ],
)
def test_finalized_state_rejects_authority_fact_mutations(
    path: tuple[object, ...], value: object
) -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    current = payload
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)
