"""Generic B.2e review contract invariants."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import (
    AcceptanceState,
    GraphContribution,
)
from dungeonmind.contracts.contribution_review import (
    ContributionReviewIntent,
    ContributionReviewState,
    contribution_payload_sha256,
    derive_review_intent_sha256,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef

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
    candidate_payload = intent.candidate_contribution.model_dump(mode="json")
    candidate_payload["assertions"][0]["label"] = "synthetic label"
    candidate_payload["assertions"][0]["value"] = None
    candidate = GraphContribution.model_validate(candidate_payload)
    plan_ref = intent.plan_ref.model_copy(
        update={
            "source_plan_schema": "synthetic_profile_plan_v1",
            "source_input_sha256": "c" * 64,
            "preview_content_sha256": "d" * 64,
            "candidate_contribution_sha256": contribution_payload_sha256(candidate),
            "semantic_profile": SemanticProfileRef(
                profile_id="synthetic.profile",
                profile_revision="v1",
                descriptor_sha256="a" * 64,
            ),
        }
    )
    digest = derive_review_intent_sha256(
        operation_id=intent.operation_id,
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        plan_ref=plan_ref,
        candidate_contribution=candidate,
        identity_proposals=intent.identity_proposals,
        identity_verdicts=intent.identity_verdicts,
        assertion_verdicts=intent.assertion_verdicts,
        reviewer_id=intent.reviewer_id,
        reviewed_at=intent.reviewed_at,
    )
    payload = intent.model_dump(mode="json")
    payload["plan_ref"] = plan_ref.model_dump(mode="json")
    payload["candidate_contribution"] = candidate.model_dump(mode="json")
    payload["review_intent_sha256"] = digest
    generic = ContributionReviewIntent.model_validate(payload)
    assert generic.plan_ref.source_plan_schema == "synthetic_profile_plan_v1"
    assert generic.candidate_contribution.assertions[0].label == "synthetic label"


def _intent_with_candidate_mutation(
    mutator,
    *,
    first_verdict_state: str | None = None,
) -> dict[str, object]:
    intent = _intent()
    payload = intent.model_dump(mode="json")
    candidate_payload = payload["candidate_contribution"]
    mutator(candidate_payload)
    candidate = GraphContribution.model_validate(candidate_payload)
    plan_ref = intent.plan_ref.model_copy(
        update={"candidate_contribution_sha256": contribution_payload_sha256(candidate)}
    )
    payload["candidate_contribution"] = candidate.model_dump(mode="json")
    payload["plan_ref"] = plan_ref.model_dump(mode="json")
    assertion_verdicts = intent.assertion_verdicts
    if first_verdict_state is not None:
        payload["assertion_verdicts"][0]["acceptance_state"] = first_verdict_state
        assertion_verdicts = [
            verdict.model_copy(
                update={
                    "acceptance_state": AcceptanceState(first_verdict_state)
                    if index == 0
                    else verdict.acceptance_state
                }
            )
            for index, verdict in enumerate(assertion_verdicts)
        ]
    payload["review_intent_sha256"] = derive_review_intent_sha256(
        operation_id=intent.operation_id,
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        plan_ref=plan_ref,
        candidate_contribution=candidate,
        identity_proposals=intent.identity_proposals,
        identity_verdicts=intent.identity_verdicts,
        assertion_verdicts=assertion_verdicts,
        reviewer_id=intent.reviewer_id,
        reviewed_at=intent.reviewed_at,
    )
    return payload


def test_intent_rejects_duplicate_candidate_assertion_ids() -> None:
    payload = _intent_with_candidate_mutation(
        lambda candidate: candidate["assertions"][1].update(
            assertion_id=candidate["assertions"][0]["assertion_id"]
        )
    )
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


@pytest.mark.parametrize(
    ("assertion_kind", "verdict_state"),
    [
        ("attribute", "accepted"),
        ("mystery", "accepted"),
        ("mystery", "rejected"),
    ],
)
def test_intent_rejects_unknown_assertion_kind(
    assertion_kind: str,
    verdict_state: str,
) -> None:
    def mutate(candidate: dict[str, object]) -> None:
        assertion = candidate["assertions"][0]
        assertion["assertion_kind"] = assertion_kind

    payload = _intent_with_candidate_mutation(
        mutate,
        first_verdict_state=verdict_state,
    )
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


def test_intent_rejects_create_new_label_without_label_text() -> None:
    def mutate(candidate: dict[str, object]) -> None:
        assertion = candidate["assertions"][0]
        assertion["label"] = None
        assertion["value"] = None

    payload = _intent_with_candidate_mutation(
        mutate,
        first_verdict_state="accepted",
    )
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


@pytest.mark.parametrize("assertion_kind", ["alias", "summary"])
def test_intent_rejects_alias_or_summary_without_nonblank_value(
    assertion_kind: str,
) -> None:
    def mutate(candidate: dict[str, object]) -> None:
        assertion = candidate["assertions"][0]
        assertion["assertion_kind"] = assertion_kind
        assertion["label"] = None
        assertion["value"] = " "

    payload = _intent_with_candidate_mutation(mutate)
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    ["subject_object_id", "object_object_id", "predicate"],
)
def test_intent_rejects_relationship_missing_required_field(
    missing_field: str,
) -> None:
    def mutate(candidate: dict[str, object]) -> None:
        assertion = candidate["assertions"][0]
        assertion.update(
            assertion_kind="relationship",
            subject_object_id="obj:subject",
            object_object_id="obj:object",
            predicate="threatens",
            label=None,
            value=None,
        )
        assertion[missing_field] = None

    payload = _intent_with_candidate_mutation(mutate)
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


def test_intent_rejects_relationship_with_node_only_fields() -> None:
    def mutate(candidate: dict[str, object]) -> None:
        candidate["assertions"][0].update(
            assertion_kind="relationship",
            subject_object_id="obj:subject",
            object_object_id="obj:object",
            predicate="threatens",
            label="not a relationship label",
            value=None,
        )

    payload = _intent_with_candidate_mutation(mutate)
    with pytest.raises(ValidationError):
        ContributionReviewIntent.model_validate(payload)


def test_finalized_state_rejects_supported_assertion_shape_drift() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["candidate_contribution"]["assertions"][0]["label"] = None
    payload["candidate_contribution"]["assertions"][0]["value"] = None
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


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
