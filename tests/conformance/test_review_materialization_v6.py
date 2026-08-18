"""V6 materializer mapping and fail-closed algebra (in-memory conformance).

Fixtures are shared with ``tests.unit.test_contribution_review_v2``; this
suite pins the per-kind mapping and every fail-closed reason at the
materialization boundary.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from dungeonmind.application.contribution_review_v2 import _build_review_state
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.application.review_materialization_v6 import (
    materialize_finalized_review_v6,
)
from dungeonmind.contracts.contribution import GraphContributionV2
from dungeonmind.contracts.contribution_review import (
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionIdentityVerdictKind,
)
from dungeonmind.contracts.contribution_review_v2 import ContributionReviewStateV2
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ContributionMaterializationError
from tests.unit.test_contribution_review_v2 import (
    EXISTING_EVIDENCE_ID,
    EXISTING_OBJECT_ID,
    NEW_OBJECT_ID,
    SECOND_OBJECT_ID,
    _candidate,
    _intent,
    _reader,
    _stored_parent,
    _submission,
)


def _materialize(state: ContributionReviewStateV2 | None = None):
    parent = _stored_parent()
    return parent, materialize_finalized_review_v6(
        state or _build_review_state(_submission(_intent(parent=parent))),
        parent=parent,
        graph_reader=_reader(),
    )


def test_v6_materialization_creates_updates_and_derives_ids() -> None:
    parent, result = _materialize()
    assert result.graph_schema == GRAPH_SCHEMA_V6
    assert result.expected_parent_revision_id == parent.revision.revision_id
    payload = result.graph_payload
    assert canonical_sha256(payload) == result.graph_payload_sha256

    objects = {obj["object_id"]: obj for obj in payload["objects"]}
    assert set(objects) == {EXISTING_OBJECT_ID, SECOND_OBJECT_ID, NEW_OBJECT_ID}
    created = objects[NEW_OBJECT_ID]
    assert created["kind"] == "dnd5e:npc"
    assert created["label"] == "New NPC"
    assert created["assertion_metadata"]["assertion_id"] == "assertion:test:node:new"
    assert created["assertion_metadata"]["evidence_ref_ids"] == ["evidence:new:node"]
    assert [alias["value"] for alias in created["aliases"]] == ["New NPC", "The Newcomer"]

    existing = objects[EXISTING_OBJECT_ID]
    assert existing["kind"] == "dnd5e:npc"
    assert existing["label"] == "Existing NPC"
    assert [alias["value"] for alias in existing["aliases"]] == [
        "The Existing One",
        "The Familiar",
    ]
    assert existing["aliases"][1]["assertion_metadata"]["assertion_id"] == (
        "assertion:test:alias:existing"
    )
    assert EXISTING_EVIDENCE_ID in existing["assertion_metadata"]["evidence_ref_ids"]
    assert "evidence:new:alias" in existing["assertion_metadata"]["evidence_ref_ids"]

    relationships = {rel["relationship_id"]: rel for rel in payload["relationships"]}
    edge_id = f"edge:{NEW_OBJECT_ID}:knows_about:{EXISTING_OBJECT_ID}"
    assert edge_id in relationships
    edge = relationships[edge_id]
    assert edge["predicate"] == "dnd5e:knows_about"
    assert edge["source_object_id"] == NEW_OBJECT_ID
    assert edge["target_object_id"] == EXISTING_OBJECT_ID
    assert edge["assertion_metadata"]["assertion_id"] == "assertion:test:edge:new"

    evidence_ids = {record["evidence_ref_id"] for record in payload["evidence_refs"]}
    assert evidence_ids == {
        EXISTING_EVIDENCE_ID,
        "evidence:new:node",
        "evidence:new:alias",
        "evidence:new:edge",
        "evidence:new:attribute",
    }
    lifted = {record["evidence_ref_id"]: record for record in payload["evidence_refs"]}
    assert lifted["evidence:new:node"]["source_domain_key"] == "session_recap"
    assert lifted["evidence:new:node"]["locator"] == "paragraph:002"

    # The output payload reparses under the pinned profile.
    snapshot = _reader().parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload)
    assert NEW_OBJECT_ID in snapshot.objects


def test_v6_materialization_explicit_edge_id_is_preserved() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = (
        '{"dm_predicate": "dnd5e:knows_about", "edge_id": "edge:custom:1"}'
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    relationship_ids = {rel["relationship_id"] for rel in result.graph_payload["relationships"]}
    assert relationship_ids == {"edge:custom:1"}


def test_v6_materialization_missing_qualified_kind_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["value"] = '{"kind": "npc"}'
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "missing_qualified_kind"


def test_v6_materialization_missing_qualified_predicate_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = "{}"
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "missing_qualified_predicate"


def test_v6_materialization_unqualified_terms_fail_output_validation() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["value"] = '{"dm_kind": "notaprofile:npc", "kind": "npc"}'
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "output_graph_validation"


def test_v6_materialization_edge_id_collision_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    # A second edge assertion reusing the same derived id with a different
    # qualified predicate must fail closed, not silently merge.
    second_edge = copy.deepcopy(candidate_payload["assertions"][2])
    second_edge["assertion_id"] = "assertion:test:edge:second"
    second_edge["value"] = '{"dm_predicate": "dnd5e:allied_with"}'
    candidate_payload["assertions"].append(second_edge)
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "relationship_id_collision"


def test_v6_materialization_exact_duplicate_edge_is_replay_safe() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    duplicate = copy.deepcopy(candidate_payload["assertions"][2])
    duplicate["assertion_id"] = "assertion:test:edge:duplicate"
    candidate_payload["assertions"].append(duplicate)
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    assert len(result.graph_payload["relationships"]) == 1


def test_v6_materialization_correction_removes_alias_record() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "ka:alias:npc:existing_npc:0",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:alias:existing",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    objects = {obj["object_id"]: obj for obj in result.graph_payload["objects"]}
    assert [alias["value"] for alias in objects[EXISTING_OBJECT_ID]["aliases"]] == ["The Familiar"]


def test_v6_materialization_correction_on_existence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "ka:object:npc:existing_npc",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:node:new",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "correction_target_existence"


def test_v6_materialization_unresolvable_correction_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "assertion:does:not:exist",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:node:new",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "correction_target_unresolvable"


def test_v6_materialization_non_mutating_outcome_is_skipped() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][3]["identity_resolution_outcome"] = "ambiguous"
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    evidence_ids = {record["evidence_ref_id"] for record in result.graph_payload["evidence_refs"]}
    assert "evidence:new:attribute" not in evidence_ids


def test_v6_materialization_evidence_fallback_synthesis() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    # Source-identity-only node assertion: valid for the contract, and the
    # materializer synthesizes the contribution-scoped fallback evidence.
    candidate_payload["assertions"][0]["evidence_refs"] = []
    candidate_payload["assertions"][0]["source_artifact_id"] = (
        "artifact:recap:longmont-c2:session-2"
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    objects = {obj["object_id"]: obj for obj in result.graph_payload["objects"]}
    reviewed_id = state.reviewed_contribution.contribution_id
    fallback_id = f"evidence:{reviewed_id}:{NEW_OBJECT_ID}"
    assert objects[NEW_OBJECT_ID]["assertion_metadata"]["evidence_ref_ids"] == [fallback_id]
    evidence = {
        record["evidence_ref_id"]: record for record in result.graph_payload["evidence_refs"]
    }
    assert evidence[fallback_id]["source_artifact_id"] == ("artifact:recap:longmont-c2:session-2")
    assert evidence[fallback_id]["source_domain_key"] == "manual_seed"


def test_v6_materialization_alias_without_evidence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = []
    candidate_payload["assertions"][1]["source_artifact_id"] = None
    candidate_payload["assertions"][1]["source_revision_id"] = None
    candidate = GraphContributionV2.model_validate(candidate_payload)
    with pytest.raises(ValidationError):
        _intent(candidate=candidate)


def test_v6_materialization_reuses_identical_parent_evidence() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = [
        {
            "evidence_ref_id": EXISTING_EVIDENCE_ID,
            "source_artifact_id": "artifact:recap:longmont-c2:session-1",
            "source_domain": "session_recap",
            "evidence_role": "support",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": "paragraph:001",
            "uri": None,
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    evidence_ids = [record["evidence_ref_id"] for record in result.graph_payload["evidence_refs"]]
    assert evidence_ids.count(EXISTING_EVIDENCE_ID) == 1


def test_v6_materialization_conflicting_parent_evidence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = [
        {
            "evidence_ref_id": EXISTING_EVIDENCE_ID,
            "source_artifact_id": "artifact:recap:longmont-c2:session-1",
            "source_domain": "session_recap",
            "evidence_role": "contradiction",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": "paragraph:001",
            "uri": None,
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "accepted_evidence_conflict"


def test_v6_materialization_create_new_on_existing_object_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["subject_object_id"] = EXISTING_OBJECT_ID
    candidate = GraphContributionV2.model_validate(candidate_payload)
    # Node and alias assertions now both target the existing object, so the
    # single identity proposal covers it — but with a create_new verdict,
    # which the materializer must refuse against the existing parent object.
    proposals = [
        ContributionIdentityProposal(
            candidate_id="cand:clash",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.PROVISIONAL_NEW,
            target_object_id=EXISTING_OBJECT_ID,
        )
    ]
    verdicts = [
        ContributionIdentityVerdict(
            candidate_id="cand:clash",
            verdict=ContributionIdentityVerdictKind.CREATE_NEW,
            target_object_id=EXISTING_OBJECT_ID,
        )
    ]
    intent = _intent(
        candidate=candidate,
        identity_proposals=proposals,
        identity_verdicts=verdicts,
    )
    state = _build_review_state(_submission(intent))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "parent_binding_mismatch"
