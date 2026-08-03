"""Executable B.2f-0 review-to-graph-effects characterization."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import (
    ParsedGraphSnapshot,
    UnionGraphV3SnapshotReader,
)
from dungeonmind.contracts.contribution_review import ContributionReviewState
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

from .review_materialization_characterization import (
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
    WorldGraphRevision, ParsedGraphSnapshot, dict[str, Any]
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
        reader.parse(
            graph_schema=graph["graph_schema"],
            graph_payload=payload,
        ),
        payload,
    )


def _state() -> ContributionReviewState:
    return ContributionReviewState.model_validate(
        json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    )


@pytest.mark.conformance
def test_tripod_effect_spec_matches_derived_fixture() -> None:
    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_snapshot=parent_snapshot,
        parent_graph_payload=parent_payload,
    )
    expected = json.loads(EFFECT_FIXTURE.read_text(encoding="utf-8"))
    assert actual == expected
    assert len(actual["object_effects"]) == 2
    assert len(actual["relationship_effects"]) == 3
    assert len(actual["rejected_assertion_ids"]) == 2
    assert actual["durable_writes"] == []


@pytest.mark.conformance
def test_effect_spec_is_deterministic_under_parent_mapping_order() -> None:
    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    reordered = replace(
        parent_snapshot,
        objects=dict(reversed(list(parent_snapshot.objects.items()))),
        relationships=dict(reversed(list(parent_snapshot.relationships.items()))),
    )
    first = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_snapshot=parent_snapshot,
        parent_graph_payload=parent_payload,
    )
    second = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_snapshot=reordered,
        parent_graph_payload=parent_payload,
    )
    assert first == second


@pytest.mark.conformance
def test_changed_parent_fails_closed() -> None:
    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    changed_parent = parent_revision.model_copy(
        update={"revision_id": "rev:00000000000000000000000000000000"}
    )
    with pytest.raises(ValueError, match="exact expected parent"):
        characterize_finalized_review(
            _state(),
            parent_revision=changed_parent,
            parent_snapshot=parent_snapshot,
            parent_graph_payload=parent_payload,
        )


@pytest.mark.conformance
def test_changed_parent_payload_fails_closed() -> None:
    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    changed_payload = copy.deepcopy(parent_payload)
    changed_payload["nodes"][0]["label"] = "tampered parent"
    with pytest.raises(ValueError, match="payload"):
        characterize_finalized_review(
            _state(),
            parent_revision=parent_revision,
            parent_snapshot=parent_snapshot,
            parent_graph_payload=changed_payload,
        )


@pytest.mark.conformance
def test_tampered_review_is_rejected_before_characterization() -> None:
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["reviewed_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewState.model_validate(payload)


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
    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    actual = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_snapshot=parent_snapshot,
        parent_graph_payload=parent_payload,
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
def test_preexisting_relationship_is_characterized_as_reuse() -> None:
    from dungeonmind.application.graph_snapshot import GraphRelationshipView

    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    existing = GraphRelationshipView(
        relationship_id="rel:existing-tripod-at-gate",
        subject_object_id="obj:48e170969a2bb3980e437f7430b7b1c1",
        predicate="dnd5e:located_at",
        object_object_id="obj:north-gate",
    )
    relationships = dict(parent_snapshot.relationships)
    relationships[existing.relationship_id] = existing
    changed_snapshot = replace(parent_snapshot, relationships=relationships)
    actual = characterize_finalized_review(
        _state(),
        parent_revision=parent_revision,
        parent_snapshot=changed_snapshot,
        parent_graph_payload=parent_payload,
    )
    located_at = next(
        effect
        for effect in actual["relationship_effects"]
        if effect["relationship_key"]["predicate"] == "dnd5e:located_at"
    )
    assert located_at["effect"] == "reuse_existing_relationship"
    assert located_at["existing_relationship_ids"] == [
        "rel:existing-tripod-at-gate"
    ]


@pytest.mark.conformance
def test_semantic_profile_pin_is_required() -> None:
    from dungeonmind.contracts.semantic_profile import SemanticProfileRef

    parent_revision, parent_snapshot, parent_payload = _parent_inputs()
    changed_snapshot = replace(
        parent_snapshot,
        semantic_profile_ref=SemanticProfileRef(
            profile_id="synthetic.other",
            profile_revision="v1",
            descriptor_sha256="f" * 64,
        ),
    )
    with pytest.raises(ValueError, match="semantic profile"):
        characterize_finalized_review(
            _state(),
            parent_revision=parent_revision,
            parent_snapshot=changed_snapshot,
            parent_graph_payload=parent_payload,
        )
