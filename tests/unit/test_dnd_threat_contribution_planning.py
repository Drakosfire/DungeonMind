"""Deterministic create-or-connect planning matrix for B.2d."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    UnionGraphV3SnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.contribution_planning import (
    plan_threat_candidate_contribution,
)
from dungeonmind_dnd.contracts.contribution_planning import (
    DndExistingObjectVerificationState,
    DndPlanBlockerCode,
    DndRelationshipPlanState,
    DndThreatPlanStatus,
)
from dungeonmind_dnd.domain.errors import DndContributionPlanningError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
PACKET_PATH = FIXTURES / "tripod-null-calf-threat-candidates-v1.json"
GRAPH_PATH = FIXTURES / "gatewatch-world-graph-v3.json"
EXPECTED_PLAN_PATH = FIXTURES / "tripod-null-calf-contribution-plan-v1.json"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "dungeonmind_dnd"
    / "profiles"
    / "dnd5e-v2.json"
)

ACTOR = "operator:synthetic-reviewer"
PLANNED_AT = datetime(2026, 8, 1, 18, 0, tzinfo=UTC)
TRIPOD = "cand:tripod-null-calf"
BREACH = "cand:north-gate-breach"
NORTH_GATE = "obj:north-gate"


def _packet() -> dict[str, Any]:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def _graph_fixture() -> dict[str, Any]:
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def _dnd_reader() -> UnionGraphV3SnapshotReader:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    return UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _stored_revision(
    graph_fixture: dict[str, Any] | None = None,
    *,
    payload_override: dict[str, Any] | None = None,
    digest_override: str | None = None,
    schema_override: str | None = None,
    world_override: str | None = None,
) -> StoredGraphRevision:
    fixture = graph_fixture if graph_fixture is not None else _graph_fixture()
    payload = copy.deepcopy(payload_override or fixture["graph_payload"])
    meta = fixture["revision_metadata"]
    world_id = world_override or fixture["world_id"]
    graph_schema = schema_override or fixture["graph_schema"]
    payload_digest = digest_override or canonical_sha256(payload)
    revision_id = compute_revision_id(
        world_id=world_id,
        parent_revision_id=meta["parent_revision_id"],
        operation_ids=list(meta["operation_ids"]),
        graph_schema=graph_schema,
        graph_payload_sha256=payload_digest,
    )
    revision = WorldGraphRevision(
        world_id=world_id,
        revision_id=revision_id,
        parent_revision_id=meta["parent_revision_id"],
        created_at=datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00")),
        operation_ids=list(meta["operation_ids"]),
        graph_schema=graph_schema,
        graph_payload_sha256=payload_digest,
    )
    return StoredGraphRevision(revision=revision, graph_payload=payload)


def _plan(
    packet: dict[str, Any] | None = None,
    stored: StoredGraphRevision | None = None,
    *,
    actor: str = ACTOR,
    planned_at: datetime = PLANNED_AT,
    reader: UnionGraphV3SnapshotReader | None = None,
):
    return plan_threat_candidate_contribution(
        packet if packet is not None else _packet(),
        stored_revision=stored if stored is not None else _stored_revision(),
        graph_reader=reader or _dnd_reader(),
        actor=actor,
        planned_at=planned_at,
    )


def _add_node(
    payload: dict[str, Any],
    *,
    object_id: str,
    kind: str,
    label: str,
    aliases: list[str] | None = None,
) -> None:
    evidence_id = f"ev:fixture-{object_id.replace(':', '-')}"
    payload["evidence_refs"].append(
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": evidence_id,
            "source_artifact_id": "src:synthetic-gatewatch-codex",
            "source_revision_id": "srcrev:synthetic-gatewatch-codex-v1",
            "source_domain": "prep",
            "evidence_role": "support",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": f"fixture://synthetic-gatewatch-codex#{object_id}",
            "uri": None,
        }
    )
    node: dict[str, Any] = {
        "object_id": object_id,
        "kind": kind,
        "label": label,
        "evidence_ref_ids": [evidence_id],
        "alias_assertions": [],
        "summary_assertion": None,
    }
    for index, alias in enumerate(aliases or []):
        alias_ev = f"{evidence_id}-alias-{index}"
        payload["evidence_refs"].append(
            {
                "schema_version": "dm_evidence_ref_v1",
                "evidence_ref_id": alias_ev,
                "source_artifact_id": "src:synthetic-gatewatch-codex",
                "source_revision_id": "srcrev:synthetic-gatewatch-codex-v1",
                "source_domain": "prep",
                "evidence_role": "support",
                "can_open_source": True,
                "can_highlight_span": True,
                "locator": f"fixture://synthetic-gatewatch-codex#{object_id}-alias-{index}",
                "uri": None,
            }
        )
        node["alias_assertions"].append(
            {
                "assertion_id": f"asrt:fixture-{object_id.replace(':', '-')}-{index}",
                "alias": alias,
                "evidence_ref_ids": [alias_ev],
            }
        )
    payload["nodes"].append(node)


def _blocker_codes(plan) -> list[str]:
    return [blocker.code.value for blocker in plan.blockers]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_matches_expected_plan_fixture() -> None:
    plan = _plan()
    expected = json.loads(EXPECTED_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan.model_dump(mode="json") == expected
    assert plan.status is DndThreatPlanStatus.READY_FOR_REVIEW
    assert plan.confirmation_required is True
    assert plan.expected_parent_revision_id == plan.base_revision_id
    assert plan.proposed_contribution is not None
    assert len(plan.proposed_contribution.assertions) == 10


def test_happy_path_identity_and_relationship_outcomes() -> None:
    plan = _plan()
    by_id = {r.candidate_id: r for r in plan.candidate_resolutions}
    assert by_id[TRIPOD].outcome is IdentityOutcome.PROVISIONAL_NEW
    assert by_id[BREACH].outcome is IdentityOutcome.PROVISIONAL_NEW
    assert by_id[TRIPOD].matched_object_ids == []
    assert by_id[BREACH].matched_object_ids == []
    assert len(plan.existing_object_verifications) == 1
    verification = plan.existing_object_verifications[0]
    assert verification.existing_object_id == NORTH_GATE
    assert verification.state is DndExistingObjectVerificationState.VERIFIED
    assert verification.actual_kind == "dnd5e:location"
    assert all(
        rel.state is DndRelationshipPlanState.READY for rel in plan.relationship_plans
    )
    assert plan.blockers == []


def test_exact_replay_is_byte_identical() -> None:
    first = _plan().model_dump(mode="json")
    second = _plan().model_dump(mode="json")
    assert first == second


def test_replan_on_newer_clean_base_keeps_proposed_object_ids() -> None:
    first = _plan()
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:south-gate",
        kind="dnd5e:location",
        label="South Gate",
    )
    fixture["revision_metadata"] = {
        "created_at": "2026-08-01T17:30:00Z",
        "parent_revision_id": first.base_revision_id,
        "operation_ids": ["op:seed-gatewatch-south-gate-v1"],
    }
    newer = _stored_revision(fixture, payload_override=payload)
    second = _plan(stored=newer)
    first_ids = {
        r.candidate_id: r.target_object_id for r in first.candidate_resolutions
    }
    second_ids = {
        r.candidate_id: r.target_object_id for r in second.candidate_resolutions
    }
    assert first_ids == second_ids
    assert first.plan_id != second.plan_id
    assert first.proposed_contribution is not None
    assert second.proposed_contribution is not None
    assert (
        first.proposed_contribution.contribution_id
        != second.proposed_contribution.contribution_id
    )


def test_contribution_preview_is_candidate_gm_only() -> None:
    plan = _plan()
    contribution = plan.proposed_contribution
    assert contribution is not None
    assert contribution.identity_decision_ids == []
    assert contribution.unresolved_mentions == []
    assert contribution.diagnostics == {}
    kinds = [a.assertion_kind for a in contribution.assertions]
    assert kinds.count("label") == 2
    assert kinds.count("alias") == 3
    assert kinds.count("summary") == 2
    assert kinds.count("relationship") == 3
    for assertion in contribution.assertions:
        assert assertion.acceptance_state.value == "candidate"
        assert assertion.visibility.value == "gm"
        assert assertion.epistemic_kind.value == "asserted"
        assert assertion.evidence_refs


# ---------------------------------------------------------------------------
# Candidate identity
# ---------------------------------------------------------------------------


def test_exact_same_kind_label_match_resolves_existing() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:existing-tripod",
        kind="dnd5e:creature",
        label="Tripod Null-Calf",
    )
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    resolution = next(r for r in plan.candidate_resolutions if r.candidate_id == TRIPOD)
    assert resolution.outcome is IdentityOutcome.RESOLVED_EXISTING
    assert resolution.target_object_id == "obj:existing-tripod"
    assert resolution.match_channels[0].value == "label"
    assert plan.status is DndThreatPlanStatus.READY_FOR_REVIEW


def test_exact_same_kind_alias_match_resolves_existing() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:existing-tripod-alias",
        kind="dnd5e:creature",
        label="Unrelated Creature Name",
        aliases=["the three-legged calf"],
    )
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    resolution = next(r for r in plan.candidate_resolutions if r.candidate_id == TRIPOD)
    assert resolution.outcome is IdentityOutcome.RESOLVED_EXISTING
    assert resolution.target_object_id == "obj:existing-tripod-alias"
    assert any(channel.value == "alias" for channel in resolution.match_channels)


def test_multiple_same_kind_matches_block_ambiguous() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:tripod-a",
        kind="dnd5e:creature",
        label="Tripod Null-Calf",
    )
    _add_node(
        payload,
        object_id="obj:tripod-b",
        kind="dnd5e:creature",
        label="Tripod Null-Calf",
    )
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert plan.proposed_contribution is None
    assert DndPlanBlockerCode.AMBIGUOUS_IDENTITY.value in _blocker_codes(plan)
    resolution = next(r for r in plan.candidate_resolutions if r.candidate_id == TRIPOD)
    assert resolution.outcome is IdentityOutcome.AMBIGUOUS
    assert resolution.target_object_id is None


def test_wrong_kind_exact_match_blocks_cross_kind() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:location-named-tripod",
        kind="dnd5e:location",
        label="Tripod Null-Calf",
    )
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.CROSS_KIND_COLLISION.value in _blocker_codes(plan)
    resolution = next(r for r in plan.candidate_resolutions if r.candidate_id == TRIPOD)
    assert resolution.outcome is IdentityOutcome.BLOCKED_COLLISION


def test_same_kind_plus_wrong_kind_blocks_cross_kind() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:tripod-creature",
        kind="dnd5e:creature",
        label="Tripod Null-Calf",
    )
    _add_node(
        payload,
        object_id="obj:tripod-location",
        kind="dnd5e:location",
        label="Tripod Null-Calf",
    )
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.CROSS_KIND_COLLISION.value in _blocker_codes(plan)


def test_packet_candidate_identity_collision_blocks() -> None:
    packet = _packet()
    packet["nodes"][1]["surface_forms"] = ["Tripod Null-Calf", "the gate breach"]
    plan = _plan(packet)
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.AMBIGUOUS_IDENTITY.value in _blocker_codes(plan)
    assert plan.proposed_contribution is None


def test_fuzzy_spelling_and_summary_similarity_do_not_match() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id="obj:tripod-typo",
        kind="dnd5e:creature",
        label="Tripod Null Calf",  # missing hyphen — not an exact match
    )
    _add_node(
        payload,
        object_id="obj:summary-alike",
        kind="dnd5e:creature",
        label="Totally Different Name",
    )
    # Graph summary resembling the candidate summary must not match.
    payload["nodes"][-1]["summary_assertion"] = {
        "assertion_id": "asrt:summary-alike",
        "summary": "A skittish three-legged creature seen pacing outside the North Gate.",
        "evidence_ref_ids": [payload["nodes"][-1]["evidence_ref_ids"][0]],
    }
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    resolution = next(r for r in plan.candidate_resolutions if r.candidate_id == TRIPOD)
    assert resolution.outcome is IdentityOutcome.PROVISIONAL_NEW


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------


def test_missing_explicit_object_blocks() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    payload["nodes"] = [n for n in payload["nodes"] if n["object_id"] != NORTH_GATE]
    # Drop relationships/evidence that referenced the removed node.
    payload["relationships"] = [
        r
        for r in payload["relationships"]
        if NORTH_GATE not in (r["subject_object_id"], r["object_object_id"])
    ]
    used = {eid for n in payload["nodes"] for eid in n["evidence_ref_ids"]}
    used |= {
        eid for r in payload["relationships"] for eid in r["evidence_ref_ids"]
    }
    for node in payload["nodes"]:
        for alias in node.get("alias_assertions", []):
            used.update(alias["evidence_ref_ids"])
        summary = node.get("summary_assertion")
        if summary:
            used.update(summary["evidence_ref_ids"])
    payload["evidence_refs"] = [
        e for e in payload["evidence_refs"] if e["evidence_ref_id"] in used
    ]
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.EXISTING_OBJECT_MISSING.value in _blocker_codes(plan)
    assert DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED.value in _blocker_codes(plan)
    assert plan.proposed_contribution is None


def test_wrong_kind_explicit_object_blocks() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    for node in payload["nodes"]:
        if node["object_id"] == NORTH_GATE:
            node["kind"] = "dnd5e:creature"
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert (
        DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH.value in _blocker_codes(plan)
    )


def test_multiple_typed_refs_to_same_object_yield_blocked_plan() -> None:
    """One object ID with two expected kinds: verified + kind_mismatch.

    Catalog-valid because ``dnd5e:threatens`` accepts creature/faction/location
    as object. Must return a blocked plan, never a planning exception.
    """
    packet = _packet()
    for relationship in packet["relationships"]:
        if relationship["candidate_id"] == "candrel:tripod-threatens-north-gate":
            relationship["object"] = {
                "existing_object_id": NORTH_GATE,
                "expected_kind": "dnd5e:creature",
            }
    plan = _plan(packet)
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert plan.proposed_contribution is None
    by_pair = {
        (v.existing_object_id, v.expected_kind): v
        for v in plan.existing_object_verifications
    }
    assert by_pair[(NORTH_GATE, "dnd5e:location")].state is (
        DndExistingObjectVerificationState.VERIFIED
    )
    assert by_pair[(NORTH_GATE, "dnd5e:creature")].state is (
        DndExistingObjectVerificationState.KIND_MISMATCH
    )
    assert DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH.value in _blocker_codes(
        plan
    )
    mismatch_blockers = [
        b
        for b in plan.blockers
        if b.code is DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH
    ]
    assert len(mismatch_blockers) == 1
    assert mismatch_blockers[0].object_id == NORTH_GATE
    assert mismatch_blockers[0].expected_kind == "dnd5e:creature"
    threatens = next(
        p
        for p in plan.relationship_plans
        if p.relationship_candidate_id == "candrel:tripod-threatens-north-gate"
    )
    assert threatens.state is DndRelationshipPlanState.ENDPOINT_BLOCKED
    located = next(
        p
        for p in plan.relationship_plans
        if p.relationship_candidate_id == "candrel:tripod-located-at-north-gate"
    )
    assert located.state is DndRelationshipPlanState.READY


def test_explicit_id_is_not_substituted_by_label_similarity() -> None:
    packet = _packet()
    # Point the existing endpoint at a missing ID while a similarly-labeled
    # object remains in the graph — verification is by ID only.
    for relationship in packet["relationships"]:
        endpoint = relationship["object"]
        if endpoint.get("existing_object_id") == NORTH_GATE:
            endpoint["existing_object_id"] = "obj:missing-north-gate"
    plan = _plan(packet)
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.EXISTING_OBJECT_MISSING.value in _blocker_codes(plan)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def test_duplicate_packet_triple_blocks() -> None:
    packet = _packet()
    duplicate = copy.deepcopy(packet["relationships"][0])
    duplicate["candidate_id"] = "candrel:tripod-located-at-north-gate-dup"
    duplicate["evidence_ref_ids"] = ["ev:tripod-threatens-gate"]
    packet["relationships"].append(duplicate)
    plan = _plan(packet)
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.DUPLICATE_PACKET_RELATIONSHIP.value in _blocker_codes(plan)


def test_existing_graph_triple_blocks() -> None:
    first = _plan()
    tripod_id = next(
        r.target_object_id
        for r in first.candidate_resolutions
        if r.candidate_id == TRIPOD
    )
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    _add_node(
        payload,
        object_id=tripod_id,
        kind="dnd5e:creature",
        label="Unrelated Placeholder",
    )
    evidence_id = "ev:existing-tripod-at-gate"
    payload["evidence_refs"].append(
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": evidence_id,
            "source_artifact_id": "src:synthetic-gatewatch-codex",
            "source_revision_id": "srcrev:synthetic-gatewatch-codex-v1",
            "source_domain": "prep",
            "evidence_role": "support",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": "fixture://synthetic-gatewatch-codex#existing-tripod-at-gate",
            "uri": None,
        }
    )
    payload["relationships"].append(
        {
            "relationship_id": "rel:existing-tripod-at-gate",
            "subject_object_id": tripod_id,
            "predicate": "dnd5e:located_at",
            "object_object_id": NORTH_GATE,
            "evidence_ref_ids": [evidence_id],
        }
    )
    # Packet must resolve the tripod as existing via exact label match so the
    # relationship endpoints become the same triple as the graph edge.
    for node in payload["nodes"]:
        if node["object_id"] == tripod_id:
            node["label"] = "Tripod Null-Calf"
    plan = _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert plan.status is DndThreatPlanStatus.BLOCKED
    assert DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS.value in _blocker_codes(plan)


def test_same_endpoints_different_predicate_ready() -> None:
    # Happy path already has located_at and threatens to the same North Gate.
    plan = _plan()
    predicates = {rel.predicate for rel in plan.relationship_plans}
    assert "dnd5e:located_at" in predicates
    assert "dnd5e:threatens" in predicates
    assert plan.status is DndThreatPlanStatus.READY_FOR_REVIEW


# ---------------------------------------------------------------------------
# Integrity failures
# ---------------------------------------------------------------------------


def test_blank_actor_raises() -> None:
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(actor="   ")
    assert exc_info.value.code == "dnd_contribution_planning_error"


def test_payload_digest_mismatch_raises() -> None:
    stored = _stored_revision(
        digest_override="0" * 64,
    )
    # Recompute revision_id against the fake digest so the envelope is
    # internally consistent, but the recomputed payload hash will diverge.
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(stored=stored)
    assert "digest" in str(exc_info.value).casefold()


def test_packet_revision_world_mismatch_raises() -> None:
    stored = _stored_revision(world_override="world:other")
    # Keep payload world as synthetic-gatewatch so envelope/payload also disagree,
    # or align payload — handoff says packet/revision world mismatch is an error.
    payload = copy.deepcopy(stored.graph_payload)
    payload["world_id"] = "world:other"
    stored = StoredGraphRevision(
        revision=stored.revision.model_copy(update={"world_id": "world:other"}),
        graph_payload=payload,
    )
    # Need digest/revision_id to match the mutated payload.
    digest = canonical_sha256(payload)
    revision_id = compute_revision_id(
        world_id="world:other",
        parent_revision_id=stored.revision.parent_revision_id,
        operation_ids=list(stored.revision.operation_ids),
        graph_schema=stored.revision.graph_schema,
        graph_payload_sha256=digest,
    )
    stored = StoredGraphRevision(
        revision=stored.revision.model_copy(
            update={
                "world_id": "world:other",
                "revision_id": revision_id,
                "graph_payload_sha256": digest,
            }
        ),
        graph_payload=payload,
    )
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(stored=stored)
    assert "world" in str(exc_info.value).casefold()


@pytest.mark.parametrize("schema", [GRAPH_SCHEMA_V1, GRAPH_SCHEMA_V2])
def test_unsupported_graph_schema_raises(schema: str) -> None:
    stored = _stored_revision(schema_override=schema)
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(stored=stored)
    assert "schema" in str(exc_info.value).casefold()


def test_profile_revision_mismatch_raises() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    payload["semantic_profile"]["profile_revision"] = "dnd5e-profile-v1"
    # Reader will fail integrity on digest mismatch for the pinned ref; either
    # parse failure or profile mismatch is a planning error.
    with pytest.raises(DndContributionPlanningError):
        _plan(stored=_stored_revision(fixture, payload_override=payload))


def test_proposed_id_collision_with_graph_object_raises() -> None:
    first = _plan()
    tripod_id = next(
        r.target_object_id
        for r in first.candidate_resolutions
        if r.candidate_id == TRIPOD
    )
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    # Plant an object with the would-be proposed ID but a non-matching label
    # so the candidate still resolves as provisional_new, then collides.
    _add_node(
        payload,
        object_id=tripod_id,
        kind="dnd5e:faction",
        label="Completely Different Faction",
    )
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert "collides" in str(exc_info.value).casefold()


def test_malformed_v3_payload_raises_sanitized_planning_error() -> None:
    fixture = _graph_fixture()
    payload = copy.deepcopy(fixture["graph_payload"])
    payload["nodes"] = "not-a-list"
    with pytest.raises(DndContributionPlanningError) as exc_info:
        _plan(stored=_stored_revision(fixture, payload_override=payload))
    assert exc_info.value.code == "dnd_contribution_planning_error"


def test_planner_uses_versioned_reader_compatible_with_v3() -> None:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    plan = _plan(reader=reader)  # type: ignore[arg-type]
    assert plan.status is DndThreatPlanStatus.READY_FOR_REVIEW
    assert plan.base_graph_schema == GRAPH_SCHEMA_V3
