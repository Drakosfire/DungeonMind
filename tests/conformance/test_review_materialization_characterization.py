"""Executable B.2f-0 review-to-graph-effects characterization."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import (
    UnionGraphV3SnapshotReader,
)
from dungeonmind.contracts.contribution import ContributionStatus, GraphContribution
from dungeonmind.contracts.contribution_review import (
    ContributionAssertionVerdict,
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionPlanRef,
    ContributionReviewState,
    contribution_payload_sha256,
    derive_confirmation_id,
    derive_review_id,
    derive_review_intent_sha256,
    derive_reviewed_contribution_id,
)
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

from .review_materialization_characterization import (
    ReviewEffectCharacterizationError,
    characterize_finalized_review,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GRAPH_FIXTURE = FIXTURES / "dungeonmind_dnd/gatewatch-world-graph-v3.json"
PROFILE_DESCRIPTOR = (
    Path(__file__).resolve().parents[2]
    / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
)
STATE_FIXTURE = (
    FIXTURES
    / "contribution_reviews/tripod-null-calf-finalized-review-state-v1.json"
)
EFFECT_FIXTURE = (
    FIXTURES
    / "contribution_reviews/tripod-null-calf-review-effect-spec-v1.json"
)


def _parent_inputs() -> tuple[
    WorldGraphRevision, UnionGraphV3SnapshotReader, dict[str, Any]
]:
    graph = json.loads(GRAPH_FIXTURE.read_text(encoding="utf-8"))
    payload = graph["graph_payload"]
    metadata = graph["revision_metadata"]
    digest = canonical_sha256(payload)
    revision = WorldGraphRevision(
        world_id=graph["world_id"],
        revision_id=compute_revision_id(
            world_id=graph["world_id"],
            parent_revision_id=metadata["parent_revision_id"],
            operation_ids=metadata["operation_ids"],
            graph_schema=graph["graph_schema"],
            graph_payload_sha256=digest,
        ),
        parent_revision_id=metadata["parent_revision_id"],
        created_at=metadata["created_at"],
        operation_ids=metadata["operation_ids"],
        graph_schema=graph["graph_schema"],
        graph_payload_sha256=digest,
    )
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(PROFILE_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    reader = UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    return (
        revision,
        reader,
        payload,
    )


def _state() -> ContributionReviewState:
    return ContributionReviewState.model_validate(
        json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    )


def _derived_state(
    mutator: Callable[[dict[str, Any]], None],
) -> ContributionReviewState:
    """Build a valid state variant from the real finalized-review fixture."""

    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    mutator(payload)
    candidate = GraphContribution.model_validate(payload["candidate_contribution"])
    candidate_preview = candidate.model_copy(
        update={"status": ContributionStatus.ACTIVE},
    )
    plan_ref = ContributionPlanRef.model_validate(
        payload["record"]["plan_ref"]
    ).model_copy(
        update={
            "candidate_contribution_sha256": contribution_payload_sha256(
                candidate_preview
            )
        }
    )
    payload["record"]["plan_ref"] = plan_ref.model_dump(mode="json")
    identity_proposals = [
        ContributionIdentityProposal.model_validate(item)
        for item in payload["record"]["identity_proposals"]
    ]
    identity_verdicts = [
        ContributionIdentityVerdict.model_validate(item)
        for item in payload["record"]["identity_verdicts"]
    ]
    assertion_verdicts = [
        ContributionAssertionVerdict.model_validate(item)
        for item in payload["record"]["assertion_verdicts"]
    ]
    reviewed_at_dt = datetime.fromisoformat(
        payload["record"]["reviewed_at"].replace("Z", "+00:00")
    )
    review_intent_sha256 = derive_review_intent_sha256(
        operation_id=payload["record"]["operation_id"],
        world_id=payload["record"]["world_id"],
        campaign_id=payload["record"]["campaign_id"],
        plan_ref=plan_ref,
        candidate_contribution=candidate_preview,
        identity_proposals=identity_proposals,
        identity_verdicts=identity_verdicts,
        assertion_verdicts=assertion_verdicts,
        reviewer_id=payload["record"]["reviewer_id"],
        reviewed_at=reviewed_at_dt,
    )
    payload["record"]["review_intent_sha256"] = review_intent_sha256
    review_id = derive_review_id(
        operation_id=payload["record"]["operation_id"],
        review_intent_sha256=review_intent_sha256,
        world_id=payload["record"]["world_id"],
    )
    payload["record"]["review_id"] = review_id
    reviewed_payload = payload["reviewed_contribution"]
    reviewed_payload["contribution_id"] = derive_reviewed_contribution_id(
        review_id=review_id,
        candidate_contribution_id=candidate.contribution_id,
    )
    reviewed = GraphContribution.model_validate(reviewed_payload)
    payload["reviewed_contribution"] = reviewed.model_dump(mode="json")
    payload["record"]["candidate_preview_sha256"] = plan_ref.candidate_contribution_sha256
    payload["record"]["stored_candidate_sha256"] = contribution_payload_sha256(
        candidate
    )
    payload["record"]["reviewed_contribution_id"] = reviewed.contribution_id
    payload["record"]["reviewed_contribution_sha256"] = contribution_payload_sha256(
        reviewed
    )
    payload["record"]["confirmation_id"] = derive_confirmation_id(
        operation_id=payload["record"]["operation_id"],
        review_intent_sha256=review_intent_sha256,
        actor=payload["record"]["reviewer_id"],
        confirmed_at=reviewed_at_dt,
    )
    return ContributionReviewState.model_validate(payload)


def _mutate_confirm_existing(payload: dict[str, Any]) -> None:
    old_target = "obj:0ad51ac659fdcc7600be620b6645a7a0"
    new_target = "obj:gatewatch-mustering"
    for proposal in payload["record"]["identity_proposals"]:
        if proposal["candidate_id"] == "cand:north-gate-breach":
            proposal["planned_outcome"] = "resolved_existing"
            proposal["target_object_id"] = new_target
            proposal["matched_object_ids"] = [new_target]
    for verdict in payload["record"]["identity_verdicts"]:
        if verdict["candidate_id"] == "cand:north-gate-breach":
            verdict["verdict"] = "confirm_existing"
            verdict["target_object_id"] = new_target
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        for assertion in payload[contribution_key]["assertions"]:
            if assertion["subject_object_id"] == old_target:
                assertion["subject_object_id"] = new_target
                if contribution_key == "reviewed_contribution":
                    assertion["identity_resolution_outcome"] = "resolved_existing"
            if assertion["object_object_id"] == old_target:
                assertion["object_object_id"] = new_target


def _mutate_relationship_to_existing_parent(payload: dict[str, Any]) -> None:
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        relationship = next(
            assertion
            for assertion in payload[contribution_key]["assertions"]
            if assertion["assertion_kind"] == "relationship"
        )
        relationship.update(
            {
                "subject_object_id": "obj:gatewatch-mustering",
                "predicate": "dnd5e:located_at",
                "object_object_id": "obj:gatewatch-keep",
            }
        )


def _mutate_duplicate_accepted_relationship(payload: dict[str, Any]) -> None:
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        relationships = [
            assertion
            for assertion in payload[contribution_key]["assertions"]
            if assertion["assertion_kind"] == "relationship"
        ]
        relationships[1].update(
            {
                "subject_object_id": relationships[0]["subject_object_id"],
                "predicate": relationships[0]["predicate"],
                "object_object_id": relationships[0]["object_object_id"],
            }
        )


def _revision_for_payload(
    parent_revision: WorldGraphRevision,
    payload: dict[str, Any],
) -> WorldGraphRevision:
    digest = canonical_sha256(payload)
    return parent_revision.model_copy(
        update={
            "revision_id": compute_revision_id(
                world_id=parent_revision.world_id,
                parent_revision_id=parent_revision.parent_revision_id,
                operation_ids=parent_revision.operation_ids,
                graph_schema=parent_revision.graph_schema,
                graph_payload_sha256=digest,
            ),
            "graph_payload_sha256": digest,
        }
    )


def _mutate_reject_candidate(payload: dict[str, Any]) -> None:
    target = "obj:48e170969a2bb3980e437f7430b7b1c1"
    for verdict in payload["record"]["identity_verdicts"]:
        if verdict["candidate_id"] == "cand:tripod-null-calf":
            verdict["verdict"] = "reject_candidate"
    rejected_ids: set[str] = set()
    for assertion in payload["reviewed_contribution"]["assertions"]:
        if (
            assertion["subject_object_id"] == target
            or assertion["object_object_id"] == target
        ):
            assertion["acceptance_state"] = "rejected"
            rejected_ids.add(assertion["assertion_id"])
            if assertion["assertion_kind"] != "relationship":
                assertion["identity_resolution_outcome"] = "rejected"
    for verdict in payload["record"]["assertion_verdicts"]:
        if verdict["assertion_id"] in rejected_ids:
            verdict["acceptance_state"] = "rejected"


def _mutate_opaque_temporal_scope(payload: dict[str, Any]) -> None:
    opaque_scope = {"timeline_token": "opaque-winter-01", "interpret": "later"}
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        payload[contribution_key]["assertions"][0]["temporal_scope"] = opaque_scope


@pytest.mark.conformance
def test_tripod_effect_spec_matches_derived_fixture() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    expected = json.loads(EFFECT_FIXTURE.read_text(encoding="utf-8"))
    assert actual == expected
    assert len(actual["object_effects"]) == 2
    assert len(actual["relationship_effects"]) == 3
    assert len(actual["rejected_assertion_ids"]) == 2
    assert actual["durable_writes"] == []


@pytest.mark.conformance
def test_confirm_existing_variant_exercises_field_operations() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _derived_state(_mutate_confirm_existing),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    breach_identity = next(
        item
        for item in actual["identity_effects"]
        if item["candidate_id"] == "cand:north-gate-breach"
    )
    breach_object = next(
        item
        for item in actual["object_effects"]
        if item["object_id"] == "obj:gatewatch-mustering"
    )
    assert breach_identity["verdict"] == "confirm_existing"
    assert breach_identity["effect"] == "reuse_existing_object"
    assert breach_object["parent_object"] == {
        "object_id": "obj:gatewatch-mustering",
        "kind": "dnd5e:encounter",
    }
    assert breach_object["created_fields"] is None
    assert breach_object["proposed_fields"]["label"] == {
        "operation": "replace",
        "expected_parent_value": "Gatewatch Mustering",
        "result_value": "North Gate Breach",
        "assertion_ids": ["asrt:36e0d020cd3c37e8f4042f0d0bd07585"],
    }
    assert breach_object["proposed_fields"]["aliases"] == {
        "operation": "append",
        "expected_parent_values": [],
        "added_values": ["the gate breach"],
        "result_values": ["the gate breach"],
        "assertion_ids": ["asrt:a13780ad18486b89e58db463aef5809f"],
    }
    assert breach_object["proposed_fields"]["summary"] == {
        "operation": "replace",
        "expected_parent_value": None,
        "result_value": "A prepared situation in which the North Gate is forced open.",
        "assertion_ids": ["asrt:fe4045c389c3dc28a34bff749ff75cc2"],
    }


@pytest.mark.conformance
def test_reject_candidate_variant_excludes_object_and_relationships() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _derived_state(_mutate_reject_candidate),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    tripod_identity = next(
        item
        for item in actual["identity_effects"]
        if item["candidate_id"] == "cand:tripod-null-calf"
    )
    assert tripod_identity["verdict"] == "reject_candidate"
    assert tripod_identity["effect"] == "exclude_from_graph_truth"
    assert all(
        item["object_id"] != "obj:48e170969a2bb3980e437f7430b7b1c1"
        for item in actual["object_effects"]
    )
    assert actual["relationship_effects"] == []


@pytest.mark.conformance
def test_opaque_temporal_scope_is_preserved_without_interpretation() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _derived_state(_mutate_opaque_temporal_scope),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    assert any(
        scope == {"interpret": "later", "timeline_token": "opaque-winter-01"}
        for effect in actual["object_effects"]
        for scope in effect["temporal_scopes"]
    )


@pytest.mark.conformance
def test_effect_spec_is_deterministic_under_parent_mapping_order() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    reordered_payload = json.loads(json.dumps(parent_payload, sort_keys=True))
    first = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    second = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_graph_payload=reordered_payload,
        graph_reader=graph_reader,
    )
    assert first == second


@pytest.mark.conformance
def test_changed_parent_fails_closed() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    changed_parent = parent_revision.model_copy(
        update={"revision_id": "rev:00000000000000000000000000000000"}
    )
    with pytest.raises(ValueError, match="exact expected parent"):
        characterize_finalized_review(
            _state(),
            parent_revision=changed_parent,
            parent_graph_payload=parent_payload,
            graph_reader=graph_reader,
        )


@pytest.mark.conformance
def test_changed_parent_payload_fails_closed() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    changed_payload = copy.deepcopy(parent_payload)
    changed_payload["nodes"][0]["label"] = "tampered parent"
    with pytest.raises(ValueError, match="payload"):
        characterize_finalized_review(
            _state(),
            parent_revision=parent_revision,
            parent_graph_payload=changed_payload,
            graph_reader=graph_reader,
        )


@pytest.mark.conformance
def test_tampered_review_is_rejected_before_characterization() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["reviewed_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


@pytest.mark.conformance
def test_post_validation_review_mutation_is_rejected() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    state = _state()
    state.reviewed_contribution.assertions[0].label = "tampered after validation"
    with pytest.raises(ValueError, match="reload validation"):
        characterize_finalized_review(
            state,
            parent_revision=parent_revision,
            parent_graph_payload=parent_payload,
            graph_reader=graph_reader,
        )


@pytest.mark.conformance
def test_changed_identity_disposition_is_rejected_before_characterization() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["record"]["identity_verdicts"][0]["verdict"] = "confirm_existing"
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


@pytest.mark.conformance
def test_changed_evidence_lineage_is_rejected_before_characterization() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["reviewed_contribution"]["assertions"][0]["evidence_refs"][0][
        "evidence_ref_id"
    ] = "ev:tampered-lineage"
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


@pytest.mark.conformance
def test_rejected_review_history_is_not_an_effect() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_graph_payload=parent_payload,
        graph_reader=graph_reader,
    )
    rejected = set(actual["rejected_assertion_ids"])
    emitted = {
        assertion["assertion_id"]
        for effect in actual["object_effects"]
        for assertion in effect["assertions"]
    }
    emitted.update(
        assertion["assertion_id"]
        for effect in actual["relationship_effects"]
        for assertion in effect["assertions"]
    )
    assert rejected.isdisjoint(emitted)


@pytest.mark.conformance
def test_preexisting_relationship_in_parent_payload_fails_closed() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    changed_payload = copy.deepcopy(parent_payload)
    changed_payload["relationships"].append(
        {
            "relationship_id": "rel:existing-tripod-at-gate",
            "subject_object_id": "obj:gatewatch-mustering",
            "predicate": "dnd5e:located_at",
            "object_object_id": "obj:gatewatch-keep",
            "evidence_ref_ids": [],
        }
    )
    changed_revision = _revision_for_payload(parent_revision, changed_payload)

    def rebind_relationship_to_changed_parent(payload: dict[str, Any]) -> None:
        _mutate_relationship_to_existing_parent(payload)
        payload["record"]["plan_ref"].update(
            {
                "expected_parent_revision_id": changed_revision.revision_id,
                "base_graph_payload_sha256": changed_revision.graph_payload_sha256,
            }
        )

    with pytest.raises(
        ReviewEffectCharacterizationError,
        match="pre-existing relationship triples",
    ):
        characterize_finalized_review(
            _derived_state(rebind_relationship_to_changed_parent),
            parent_revision=changed_revision,
            parent_graph_payload=changed_payload,
            graph_reader=graph_reader,
        )


@pytest.mark.conformance
def test_duplicate_accepted_relationship_triple_fails_closed() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    with pytest.raises(
        ReviewEffectCharacterizationError,
        match="duplicate accepted relationship triples",
    ):
        characterize_finalized_review(
            _derived_state(_mutate_duplicate_accepted_relationship),
            parent_revision=parent_revision,
            parent_graph_payload=parent_payload,
            graph_reader=graph_reader,
        )


@pytest.mark.conformance
def test_semantic_profile_pin_is_required() -> None:
    parent_revision, graph_reader, parent_payload = _parent_inputs()
    changed_payload = copy.deepcopy(parent_payload)
    changed_payload["semantic_profile"]["profile_revision"] = "tampered"
    with pytest.raises(ValueError, match="payload"):
        characterize_finalized_review(
            _state(),
            parent_revision=parent_revision,
            parent_graph_payload=changed_payload,
            graph_reader=graph_reader,
        )
