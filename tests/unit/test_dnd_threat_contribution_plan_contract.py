"""Plan contract invariants for B.2d contribution planning records."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    ContributionStatus,
    GraphContribution,
    GraphContributionAssertion,
)
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vocabulary import EpistemicKind, Visibility
from dungeonmind_dnd.contracts.contribution_planning import (
    DndCandidateResolution,
    DndExistingObjectVerification,
    DndExistingObjectVerificationState,
    DndMatchChannel,
    DndPlanBlocker,
    DndPlanBlockerCode,
    DndRelationshipPlan,
    DndRelationshipPlanState,
    DndThreatContributionPlan,
    DndThreatPlanStatus,
    derive_plan_id,
)
from dungeonmind_dnd.contracts.vocabulary import DndVocabularyRef

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "dungeonmind_dnd"
    / "tripod-null-calf-contribution-plan-v1.json"
)

PROFILE = SemanticProfileRef(
    profile_id="dungeonmind.dnd5e",
    profile_revision="dnd5e-profile-v2",
    descriptor_sha256="57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086",
)
VOCAB = DndVocabularyRef(
    vocabulary_id="dungeonmind.dnd5e.threat",
    vocabulary_revision="threat-v1",
    catalog_sha256="0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047",
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_expected_plan_fixture_validates() -> None:
    plan = DndThreatContributionPlan.model_validate(_fixture())
    assert plan.status is DndThreatPlanStatus.READY_FOR_REVIEW
    assert plan.proposed_contribution is not None
    assert plan.confirmation_required is True
    assert plan.expected_parent_revision_id == plan.base_revision_id


def test_resolution_rejects_durable_outcomes() -> None:
    with pytest.raises(ValidationError):
        DndCandidateResolution(
            candidate_id="cand:x",
            candidate_kind="dnd5e:creature",
            outcome=IdentityOutcome.CREATED_NEW,
            target_object_id="obj:" + "a" * 32,
        )


def test_provisional_new_requires_hex_object_id() -> None:
    with pytest.raises(ValidationError):
        DndCandidateResolution(
            candidate_id="cand:x",
            candidate_kind="dnd5e:creature",
            outcome=IdentityOutcome.PROVISIONAL_NEW,
            target_object_id="obj:not-hex",
        )


def test_resolved_existing_requires_singleton_match() -> None:
    with pytest.raises(ValidationError):
        DndCandidateResolution(
            candidate_id="cand:x",
            candidate_kind="dnd5e:creature",
            outcome=IdentityOutcome.RESOLVED_EXISTING,
            target_object_id="obj:a",
            matched_object_ids=["obj:a", "obj:b"],
            match_channels=[DndMatchChannel.LABEL],
        )


def test_ready_plan_rejects_blockers() -> None:
    payload = _fixture()
    payload["blockers"] = [
        {
            "schema_version": "dmdnd_plan_blocker_v1",
            "code": "ambiguous_identity",
            "candidate_id": "cand:tripod-null-calf",
            "relationship_candidate_id": None,
            "object_id": None,
            "related_object_ids": [],
        }
    ]
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_blocked_plan_rejects_contribution() -> None:
    payload = _fixture()
    payload["status"] = "blocked"
    payload["blockers"] = [
        {
            "schema_version": "dmdnd_plan_blocker_v1",
            "code": "ambiguous_identity",
            "candidate_id": "cand:tripod-null-calf",
            "relationship_candidate_id": None,
            "object_id": None,
            "related_object_ids": [],
        }
    ]
    # Also flip the resolution so correspondence holds.
    for resolution in payload["candidate_resolutions"]:
        if resolution["candidate_id"] == "cand:tripod-null-calf":
            resolution["outcome"] = "ambiguous"
            resolution["target_object_id"] = None
            resolution["matched_object_ids"] = ["obj:a", "obj:b"]
            resolution["match_channels"] = ["label"]
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_accepted_assertion() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["assertions"][0]["acceptance_state"] = "accepted"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_player_visibility() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["assertions"][0]["visibility"] = "player"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_identity_decision_ids() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["identity_decision_ids"] = ["iddec:x"]
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_empty_evidence() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["assertions"][0]["evidence_refs"] = []
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_wrong_relationship_endpoint() -> None:
    payload = _fixture()
    for assertion in payload["proposed_contribution"]["assertions"]:
        if assertion["assertion_kind"] == "relationship":
            assertion["object_object_id"] = "obj:" + "f" * 32
            break
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_wrong_node_outcome() -> None:
    payload = _fixture()
    for assertion in payload["proposed_contribution"]["assertions"]:
        if assertion["assertion_kind"] == "label":
            assertion["identity_resolution_outcome"] = "resolved_existing"
            break
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_non_null_relationship_outcome() -> None:
    payload = _fixture()
    for assertion in payload["proposed_contribution"]["assertions"]:
        if assertion["assertion_kind"] == "relationship":
            assertion["identity_resolution_outcome"] = "provisional_new"
            break
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_actor_drift() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["authored_by"] = "operator:other"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_timestamp_drift() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["produced_at"] = "2026-08-01T19:00:00Z"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_extraction_profile_drift() -> None:
    payload = _fixture()
    payload["proposed_contribution"]["extraction_profile"] = "tampered-profile"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_existing_object_blocker_requires_expected_kind() -> None:
    with pytest.raises(ValidationError):
        DndPlanBlocker(
            code=DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH,
            object_id="obj:north-gate",
        )


def test_expected_parent_must_equal_base_revision() -> None:
    payload = _fixture()
    payload["expected_parent_revision_id"] = "rev:" + "0" * 32
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_confirmation_required_always_true() -> None:
    payload = _fixture()
    payload["confirmation_required"] = False
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_relationship_ready_rejects_existing_ids() -> None:
    with pytest.raises(ValidationError):
        DndRelationshipPlan(
            relationship_candidate_id="candrel:x",
            predicate="dnd5e:threatens",
            subject_object_id="obj:a",
            object_object_id="obj:b",
            state=DndRelationshipPlanState.READY,
            existing_relationship_ids=["rel:x"],
        )


def test_cross_kind_blocker_requires_related_objects() -> None:
    with pytest.raises(ValidationError):
        DndPlanBlocker(
            code=DndPlanBlockerCode.CROSS_KIND_COLLISION,
            candidate_id="cand:x",
            related_object_ids=[],
        )


def test_minimal_blocked_plan_validates() -> None:
    plan_id = derive_plan_id(
        packet_digest="b" * 64,
        base_revision_id="rev:" + "c" * 32,
        base_graph_payload_sha256="d" * 64,
        actor="operator:synthetic-reviewer",
        planned_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
    )
    plan = DndThreatContributionPlan(
        plan_id=plan_id,
        world_id="world:synthetic-gatewatch",
        campaign_id="campaign:synthetic-gatewatch-frontier",
        packet_id="packet:tripod-null-calf-threat-v1",
        candidate_packet_sha256="b" * 64,
        base_revision_id="rev:" + "c" * 32,
        base_graph_schema="dm_union_graph_v3",
        base_graph_payload_sha256="d" * 64,
        expected_parent_revision_id="rev:" + "c" * 32,
        semantic_profile=PROFILE,
        vocabulary=VOCAB,
        actor="operator:synthetic-reviewer",
        planned_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
        status=DndThreatPlanStatus.BLOCKED,
        candidate_resolutions=[
            DndCandidateResolution(
                candidate_id="cand:north-gate-breach",
                candidate_kind="dnd5e:encounter",
                outcome=IdentityOutcome.PROVISIONAL_NEW,
                target_object_id="obj:" + "e" * 32,
            ),
            DndCandidateResolution(
                candidate_id="cand:tripod-null-calf",
                candidate_kind="dnd5e:creature",
                outcome=IdentityOutcome.AMBIGUOUS,
                matched_object_ids=["obj:a", "obj:b"],
                match_channels=[DndMatchChannel.LABEL],
            ),
        ],
        existing_object_verifications=[
            DndExistingObjectVerification(
                existing_object_id="obj:north-gate",
                expected_kind="dnd5e:location",
                actual_kind="dnd5e:location",
                state=DndExistingObjectVerificationState.VERIFIED,
                relationship_candidate_ids=[
                    "candrel:tripod-located-at-north-gate",
                    "candrel:tripod-threatens-north-gate",
                ],
            )
        ],
        relationship_plans=[
            DndRelationshipPlan(
                relationship_candidate_id="candrel:tripod-located-at-north-gate",
                predicate="dnd5e:located_at",
                subject_object_id=None,
                object_object_id="obj:north-gate",
                state=DndRelationshipPlanState.ENDPOINT_BLOCKED,
            ),
            DndRelationshipPlan(
                relationship_candidate_id="candrel:tripod-participates-in-breach",
                predicate="dnd5e:participates_in",
                subject_object_id=None,
                object_object_id="obj:" + "e" * 32,
                state=DndRelationshipPlanState.ENDPOINT_BLOCKED,
            ),
            DndRelationshipPlan(
                relationship_candidate_id="candrel:tripod-threatens-north-gate",
                predicate="dnd5e:threatens",
                subject_object_id=None,
                object_object_id="obj:north-gate",
                state=DndRelationshipPlanState.ENDPOINT_BLOCKED,
            ),
        ],
        blockers=[
            DndPlanBlocker(
                code=DndPlanBlockerCode.AMBIGUOUS_IDENTITY,
                candidate_id="cand:tripod-null-calf",
                related_object_ids=["obj:a", "obj:b"],
            ),
            DndPlanBlocker(
                code=DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
                relationship_candidate_id="candrel:tripod-located-at-north-gate",
            ),
            DndPlanBlocker(
                code=DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
                relationship_candidate_id="candrel:tripod-participates-in-breach",
            ),
            DndPlanBlocker(
                code=DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
                relationship_candidate_id="candrel:tripod-threatens-north-gate",
            ),
        ],
        proposed_contribution=None,
    )
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert plan.proposed_contribution is None


def test_blocked_plan_rejects_arbitrary_plan_id() -> None:
    plan_id = derive_plan_id(
        packet_digest="b" * 64,
        base_revision_id="rev:" + "c" * 32,
        base_graph_payload_sha256="d" * 64,
        actor="operator:synthetic-reviewer",
        planned_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
    )
    payload = {
        "schema_version": "dmdnd_threat_contribution_plan_v1",
        "plan_id": plan_id,
        "world_id": "world:synthetic-gatewatch",
        "campaign_id": "campaign:synthetic-gatewatch-frontier",
        "packet_id": "packet:tripod-null-calf-threat-v1",
        "candidate_packet_sha256": "b" * 64,
        "base_revision_id": "rev:" + "c" * 32,
        "base_graph_schema": "dm_union_graph_v3",
        "base_graph_payload_sha256": "d" * 64,
        "expected_parent_revision_id": "rev:" + "c" * 32,
        "semantic_profile": PROFILE.model_dump(mode="json"),
        "vocabulary": VOCAB.model_dump(mode="json"),
        "actor": "operator:synthetic-reviewer",
        "planned_at": "2026-08-01T18:00:00Z",
        "status": "blocked",
        "candidate_resolutions": [
            {
                "candidate_id": "cand:x",
                "candidate_kind": "dnd5e:creature",
                "outcome": "ambiguous",
                "matched_object_ids": ["obj:a", "obj:b"],
                "match_channels": ["label"],
            }
        ],
        "existing_object_verifications": [],
        "relationship_plans": [
            {
                "relationship_candidate_id": "candrel:x",
                "predicate": "dnd5e:threatens",
                "subject_object_id": None,
                "object_object_id": None,
                "state": "endpoint_blocked",
            }
        ],
        "blockers": [
            {
                "code": "ambiguous_identity",
                "candidate_id": "cand:x",
                "related_object_ids": ["obj:a", "obj:b"],
            },
            {
                "code": "relationship_endpoint_blocked",
                "relationship_candidate_id": "candrel:x",
            },
        ],
        "confirmation_required": True,
        "proposed_contribution": None,
    }
    payload["plan_id"] = "plan:" + "a" * 32
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_requires_complete_node_assertions() -> None:
    payload = _fixture()
    tripod_target = next(
        resolution["target_object_id"]
        for resolution in payload["candidate_resolutions"]
        if resolution["candidate_id"] == "cand:tripod-null-calf"
    )
    payload["proposed_contribution"]["assertions"] = [
        assertion
        for assertion in payload["proposed_contribution"]["assertions"]
        if assertion["subject_object_id"] != tripod_target
    ]
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_duplicate_label_assertion() -> None:
    payload = _fixture()
    label = next(
        assertion
        for assertion in payload["proposed_contribution"]["assertions"]
        if assertion["assertion_kind"] == "label"
    )
    payload["proposed_contribution"]["assertions"].append(copy.deepcopy(label))
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_changed_label_text() -> None:
    payload = _fixture()
    label = next(
        assertion
        for assertion in payload["proposed_contribution"]["assertions"]
        if assertion["assertion_kind"] == "label"
    )
    label["label"] = "Tampered label"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_changed_alias_text() -> None:
    payload = _fixture()
    alias = next(
        assertion
        for assertion in payload["proposed_contribution"]["assertions"]
        if assertion["assertion_kind"] == "alias"
    )
    alias["value"] = "Tampered alias"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_changed_summary_text() -> None:
    payload = _fixture()
    summary = next(
        assertion
        for assertion in payload["proposed_contribution"]["assertions"]
        if assertion["assertion_kind"] == "summary"
    )
    summary["value"] = "Tampered summary"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_changed_evidence_locator() -> None:
    payload = _fixture()
    evidence = payload["proposed_contribution"]["assertions"][0]["evidence_refs"][0]
    evidence["locator"] = "fixture://tampered-locator"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_candidate_only_preview_rejects_changed_evidence_source() -> None:
    payload = _fixture()
    evidence = payload["proposed_contribution"]["assertions"][0]["evidence_refs"][0]
    evidence["source_artifact_id"] = "src:tampered-source"
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_ready_preview_rejects_non_empty_diagnostics() -> None:
    payload = _fixture()
    contrib = payload["proposed_contribution"]
    contrib["diagnostics"] = {"note": "nope"}
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(payload)


def test_manual_contribution_shape_for_preview_helper() -> None:
    """Sanity: GraphContribution still accepts the B.2d preview shape."""
    assertion = GraphContributionAssertion(
        assertion_id="asrt:" + "f" * 32,
        assertion_kind="label",
        subject_object_id="obj:" + "a" * 32,
        label="X",
        evidence_refs=[],
        visibility=Visibility.GM,
        epistemic_kind=EpistemicKind.ASSERTED,
        acceptance_state=AcceptanceState.CANDIDATE,
        identity_resolution_outcome=IdentityOutcome.PROVISIONAL_NEW,
    )
    contribution = GraphContribution(
        contribution_id="contrib:" + "b" * 32,
        world_id="world:synthetic-gatewatch",
        source_kind=ContributionSourceKind.EXTRACTION,
        produced_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
        status=ContributionStatus.ACTIVE,
        assertions=[assertion],
        unresolved_mentions=[],
        identity_decision_ids=[],
        diagnostics={},
    )
    assert contribution.partition_assertions(AcceptanceState.CANDIDATE) == [assertion]


def test_fixture_round_trip_is_stable() -> None:
    original = _fixture()
    plan = DndThreatContributionPlan.model_validate(original)
    assert plan.model_dump(mode="json") == original
    # Mutation of a copy must not affect re-validation of the original.
    mutated = copy.deepcopy(original)
    mutated["confirmation_required"] = False
    with pytest.raises(ValidationError):
        DndThreatContributionPlan.model_validate(mutated)
    DndThreatContributionPlan.model_validate(original)
