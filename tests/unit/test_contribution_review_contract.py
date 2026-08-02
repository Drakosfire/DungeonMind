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
