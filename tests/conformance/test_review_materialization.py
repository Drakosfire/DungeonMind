"""Owning-boundary proofs for finalized-review graph materialization."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.application.review_materialization import (
    materialize_finalized_review,
)
from dungeonmind.contracts.contribution import AcceptanceState
from dungeonmind.contracts.contribution_review import ContributionReviewState
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ContributionMaterializationError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.contribution_planning import (
    plan_threat_candidate_contribution,
)

from .review_materialization_characterization import characterize_finalized_review
from .test_review_materialization_characterization import (
    _add_planner_match_alias,
    _derived_state,
    _mutate_duplicate_accepted_relationship,
    _mutate_parent_assertion_id_collision,
    _mutate_parent_evidence_id_collision,
    _mutate_reject_candidate,
    _mutate_relationship_to_existing_parent,
    _review_state_from_plan,
    _revision_for_payload,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GRAPH_FIXTURE = FIXTURES / "dungeonmind_dnd/gatewatch-world-graph-v3.json"
PACKET_FIXTURE = FIXTURES / "dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json"
PROFILE_DESCRIPTOR = (
    Path(__file__).resolve().parents[2] / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
)
STATE_FIXTURE = FIXTURES / "contribution_reviews/tripod-null-calf-finalized-review-state-v1.json"
MATERIALIZED_FIXTURE = (
    FIXTURES
    / "contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json"
)


def _parent_inputs() -> tuple[StoredGraphRevision, UnionGraphV3SnapshotReader]:
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
    return StoredGraphRevision(revision=revision, graph_payload=payload), reader


def _state() -> ContributionReviewState:
    return ContributionReviewState.model_validate(
        json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    )


def _materialize(
    state: ContributionReviewState,
    parent: StoredGraphRevision,
    reader: UnionGraphV3SnapshotReader,
):
    return materialize_finalized_review(state, parent=parent, graph_reader=reader)


def _assert_reason(exc: pytest.ExceptionInfo[ContributionMaterializationError], reason: str):
    assert exc.value.code == "contribution_materialization_error"
    assert exc.value.details["reason"] == reason
    assert "North Gate" not in str(exc.value)
    assert "fixture://" not in str(exc.value)


@pytest.mark.conformance
def test_tripod_materializes_exact_payload_and_independent_effects() -> None:
    parent, reader = _parent_inputs()
    result = _materialize(_state(), parent, reader)
    expected = json.loads(MATERIALIZED_FIXTURE.read_text(encoding="utf-8"))
    assert result.graph_payload == expected
    assert result.graph_payload_sha256 == canonical_sha256(expected)

    oracle = characterize_finalized_review(
        _state(),
        parent_revision=parent.revision,
        parent_graph_payload=parent.graph_payload,
        graph_reader=reader,
    )
    assert set(oracle["accepted_evidence"]) == {
        row["evidence_ref_id"]
        for row in result.graph_payload["evidence_refs"]
        if row["evidence_ref_id"]
        not in {
            "ev:gatewatch-north-gate-core",
            "ev:gatewatch-north-gate-alias",
            "ev:gatewatch-north-gate-summary",
            "ev:gatewatch-keep-core",
            "ev:gatewatch-mustering-core",
            "ev:mustering-at-keep",
        }
    }
    assert len(result.graph_payload["nodes"]) == len(oracle["object_effects"]) + 3
    assert len(result.graph_payload["relationships"]) == 1 + len(
        oracle["relationship_effects"]
    )


@pytest.mark.conformance
def test_result_binds_review_parent_and_is_replay_deterministic() -> None:
    parent, reader = _parent_inputs()
    state = _state()
    before = copy.deepcopy(parent.graph_payload)
    first = _materialize(state, parent, reader)
    second = _materialize(state, parent, reader)

    assert first == second
    assert first.graph_payload is not parent.graph_payload
    assert parent.graph_payload == before
    assert first.world_id == state.record.world_id
    assert first.review_id == state.record.review_id
    assert first.reviewed_contribution_id == state.record.reviewed_contribution_id
    assert first.reviewed_contribution_sha256 == state.record.reviewed_contribution_sha256
    assert first.review_intent_sha256 == state.record.review_intent_sha256
    assert first.confirmation_id == state.record.confirmation_id
    assert first.operation_id == state.record.operation_id
    assert first.expected_parent_revision_id == state.record.plan_ref.expected_parent_revision_id
    assert first.parent_graph_payload_sha256 == state.record.plan_ref.base_graph_payload_sha256
    assert first.graph_schema == state.record.plan_ref.base_graph_schema


@pytest.mark.conformance
def test_rejected_assertions_and_evidence_history_do_not_enter_graph_truth() -> None:
    parent, reader = _parent_inputs()
    state = _state()
    result = _materialize(state, parent, reader)
    rejected = {
        assertion.assertion_id
        for assertion in state.reviewed_contribution.assertions
        if assertion.acceptance_state is AcceptanceState.REJECTED
    }
    emitted_assertions = {
        assertion["assertion_id"]
        for node in result.graph_payload["nodes"]
        for assertion in (
            *node["alias_assertions"],
            *(
                [node["summary_assertion"]]
                if node["summary_assertion"] is not None
                else []
            ),
        )
    }
    assert rejected.isdisjoint(emitted_assertions)
    assert "the three-legged calf" not in {
        alias["alias"]
        for node in result.graph_payload["nodes"]
        for alias in node["alias_assertions"]
    }


@pytest.mark.conformance
def test_reject_candidate_produces_no_node_or_dependent_relationship() -> None:
    parent, reader = _parent_inputs()
    result = _materialize(_derived_state(_mutate_reject_candidate), parent, reader)
    assert all(
        node["object_id"] != "obj:48e170969a2bb3980e437f7430b7b1c1"
        for node in result.graph_payload["nodes"]
    )
    assert result.graph_payload["relationships"] == parent.graph_payload["relationships"]
    assert all(
        row["evidence_ref_id"]
        not in {
            "ev:tripod-null-calf-sighting",
            "ev:tripod-at-north-gate",
            "ev:tripod-in-breach",
            "ev:tripod-threatens-gate",
        }
        for row in result.graph_payload["evidence_refs"]
    )


@pytest.mark.conformance
def test_confirm_existing_uses_actual_planner_output_and_reviews() -> None:
    parent, reader = _parent_inputs()
    planner_payload = copy.deepcopy(parent.graph_payload)
    _add_planner_match_alias(planner_payload)
    planner_parent = _revision_for_payload(parent.revision, planner_payload)
    planner = plan_threat_candidate_contribution(
        json.loads(PACKET_FIXTURE.read_text(encoding="utf-8")),
        stored_revision=StoredGraphRevision(
            revision=planner_parent,
            graph_payload=planner_payload,
        ),
        graph_reader=reader,
        actor="operator:synthetic-reviewer",
        planned_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
    )
    assert planner.blockers == []
    assert planner.proposed_contribution is not None
    state = _review_state_from_plan(planner)
    result = materialize_finalized_review(
        state,
        parent=StoredGraphRevision(
            revision=planner_parent,
            graph_payload=planner_payload,
        ),
        graph_reader=reader,
    )
    mustering = next(
        node
        for node in result.graph_payload["nodes"]
        if node["object_id"] == "obj:gatewatch-mustering"
    )
    assert mustering["label"] == "North Gate Breach"
    assert mustering["alias_assertions"] == [
        {
            "assertion_id": "asrt:gatewatch-mustering-breach-alias",
            "alias": "North Gate Breach",
            "evidence_ref_ids": ["ev:gatewatch-mustering-breach-alias"],
        },
        {
            "assertion_id": next(
                assertion.assertion_id
                for assertion in planner.proposed_contribution.assertions
                if assertion.assertion_kind == "alias"
                and assertion.subject_object_id == "obj:gatewatch-mustering"
            ),
            "alias": "the gate breach",
            "evidence_ref_ids": ["ev:north-gate-breach-plan"],
        },
    ]
    assert mustering["summary_assertion"]["summary"].startswith("A prepared situation")


@pytest.mark.conformance
def test_state_reload_validation_fails_closed_after_mutation() -> None:
    parent, reader = _parent_inputs()
    state = _state()
    state.reviewed_contribution.assertions[0].label = "tampered"
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(state, parent, reader)
    _assert_reason(exc, "state_reload_validation")


@pytest.mark.conformance
def test_parent_digest_and_parent_identity_mismatches_fail_closed() -> None:
    parent, reader = _parent_inputs()
    changed_payload = copy.deepcopy(parent.graph_payload)
    changed_payload["nodes"][0]["label"] = "tampered parent"
    changed_parent = StoredGraphRevision(
        revision=parent.revision,
        graph_payload=changed_payload,
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_state(), changed_parent, reader)
    _assert_reason(exc, "parent_binding_mismatch")

    changed_revision = parent.revision.model_copy(
        update={"revision_id": "rev:00000000000000000000000000000000"}
    )
    changed_parent = StoredGraphRevision(
        revision=changed_revision,
        graph_payload=parent.graph_payload,
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_state(), changed_parent, reader)
    _assert_reason(exc, "parent_binding_mismatch")


@pytest.mark.conformance
def test_unsupported_parent_schema_fails_closed() -> None:
    parent, reader = _parent_inputs()
    changed_revision = parent.revision.model_copy(
        update={"graph_schema": "dm_union_graph_v2"}
    )
    changed_parent = StoredGraphRevision(
        revision=changed_revision,
        graph_payload=parent.graph_payload,
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_state(), changed_parent, reader)
    _assert_reason(exc, "unsupported_graph_schema")


@pytest.mark.conformance
@pytest.mark.parametrize(
    ("assertion_kind", "parent_assertion_id"),
    [
        ("alias", "asrt:gatewatch-north-gate-alias"),
        ("summary", "asrt:gatewatch-north-gate-summary"),
    ],
)
def test_parent_assertion_namespace_collisions_fail_closed(
    assertion_kind: str,
    parent_assertion_id: str,
) -> None:
    parent, reader = _parent_inputs()

    def mutate(payload: dict[str, Any]) -> None:
        _mutate_parent_assertion_id_collision(
            payload,
            assertion_kind=assertion_kind,
            parent_assertion_id=parent_assertion_id,
        )

    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_derived_state(mutate), parent, reader)
    _assert_reason(exc, "parent_assertion_id_collision")


@pytest.mark.conformance
def test_parent_evidence_namespace_collision_fails_closed() -> None:
    parent, reader = _parent_inputs()
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_derived_state(_mutate_parent_evidence_id_collision), parent, reader)
    _assert_reason(exc, "parent_evidence_id_collision")


def _mutate_missing_graph_evidence(payload: dict[str, Any]) -> None:
    target = "obj:48e170969a2bb3980e437f7430b7b1c1"
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        for assertion in payload[contribution_key]["assertions"]:
            if (
                assertion["assertion_kind"] == "label"
                and assertion["subject_object_id"] == target
            ):
                assertion["evidence_refs"] = []


@pytest.mark.conformance
def test_accepted_assertion_without_graph_evidence_fails_closed() -> None:
    parent, reader = _parent_inputs()
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_derived_state(_mutate_missing_graph_evidence), parent, reader)
    _assert_reason(exc, "accepted_assertion_missing_graph_evidence")


def _mutate_orphan_relationship(payload: dict[str, Any]) -> None:
    for contribution_key in ("candidate_contribution", "reviewed_contribution"):
        relationship = next(
            assertion
            for assertion in payload[contribution_key]["assertions"]
            if assertion["assertion_kind"] == "relationship"
        )
        relationship["object_object_id"] = "obj:missing-from-parent-and-review"


@pytest.mark.conformance
def test_orphan_accepted_assertion_fails_closed() -> None:
    parent, reader = _parent_inputs()
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_derived_state(_mutate_orphan_relationship), parent, reader)
    _assert_reason(exc, "orphan_accepted_assertion")


@pytest.mark.conformance
def test_duplicate_and_preexisting_relationships_fail_closed() -> None:
    parent, reader = _parent_inputs()
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_derived_state(_mutate_duplicate_accepted_relationship), parent, reader)
    _assert_reason(exc, "duplicate_relationship_triple")

    changed_payload = copy.deepcopy(parent.graph_payload)
    changed_payload["relationships"].append(
        {
            "relationship_id": "rel:existing-tripod-at-gate",
            "subject_object_id": "obj:gatewatch-mustering",
            "predicate": "dnd5e:located_at",
            "object_object_id": "obj:gatewatch-keep",
            "evidence_ref_ids": [],
        }
    )
    changed_parent = _revision_for_payload(parent.revision, changed_payload)

    def rebind(payload: dict[str, Any]) -> None:
        _mutate_relationship_to_existing_parent(payload)
        payload["record"]["plan_ref"].update(
            {
                "expected_parent_revision_id": changed_parent.revision_id,
                "base_graph_payload_sha256": changed_parent.graph_payload_sha256,
            }
        )

    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(
            _derived_state(rebind),
            StoredGraphRevision(revision=changed_parent, graph_payload=changed_payload),
            reader,
        )
    _assert_reason(exc, "preexisting_relationship_triple")


@pytest.mark.conformance
def test_relationship_id_collision_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    parent, reader = _parent_inputs()
    import dungeonmind.application.review_materialization as materializer

    monkeypatch.setattr(
        materializer,
        "_relationship_id",
        lambda **_kwargs: "rel:mustering-at-keep",
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_state(), parent, reader)
    _assert_reason(exc, "relationship_id_collision")


class _RejectOutputReader:
    def __init__(self, delegate: UnionGraphV3SnapshotReader) -> None:
        self.delegate = delegate
        self.calls = 0

    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]):
        self.calls += 1
        if self.calls == 2:
            raise ValueError("synthetic output rejection")
        return self.delegate.parse(
            graph_schema=graph_schema,
            graph_payload=graph_payload,
        )


@pytest.mark.conformance
def test_output_reparse_failure_is_sanitized_and_write_free() -> None:
    parent, reader = _parent_inputs()
    before = copy.deepcopy(parent.graph_payload)
    with pytest.raises(ContributionMaterializationError) as exc:
        _materialize(_state(), parent, _RejectOutputReader(reader))
    _assert_reason(exc, "output_graph_validation")
    assert parent.graph_payload == before
