"""Pure identity-reconciliation validation and deterministic materialization proofs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.application.world_identity_reconciliation import (
    CanonicalRebindRequest,
    materialize_identity_reconciliation,
)
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

WORLD_ID = "eldyrwild"
PARENT_REVISION_ID = "rev:parent-identity-reconciliation"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _metadata(assertion_id: str) -> dict[str, object]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": "longmont-c1",
        "visibility": "gm",
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": ["ev:identity"],
        "session_refs": [],
        "temporal_scope": {
            "schema_version": "dm_temporal_scope_ref_v1",
            "kind": "unknown",
        },
    }


def _payload(object_ids: list[str] | None = None) -> dict[str, object]:
    ids = object_ids or ["node:ephanna", "node:companion"]
    return {
        "world_id": WORLD_ID,
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": "test.profile",
            "profile_revision": "v1",
            "descriptor_sha256": "0" * 64,
        },
        "relationship_endpoint_aspect_schema": "dm_relationship_endpoint_aspect_v1",
        "objects": [
            {
                "object_id": object_id,
                "kind": "test:person",
                "label": object_id.split(":", 1)[1].title(),
                "assertion_metadata": _metadata(f"asrt:{object_id}"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [],
            }
            for object_id in ids
        ],
        "relationships": [
            {
                "relationship_id": "rel:companions",
                "source_object_id": ids[0],
                "target_object_id": ids[1],
                "predicate": "test:knows",
                "assertion_metadata": _metadata("asrt:companions"),
                "source_aspect_assertion_id": None,
                "target_aspect_assertion_id": None,
            }
        ],
        "evidence_refs": [
            {
                "schema_version": "dm_evidence_ref_v2",
                "evidence_ref_id": "ev:identity",
                "source_artifact_id": "src:identity",
                "source_revision_id": "srev:identity",
                "source_domain_key": "test.worldbuilding",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "can_highlight_span": False,
                "session_id": None,
                "source_span_ref_id": None,
                "locator": None,
                "uri": None,
                "source_locator": None,
                "line_ref": None,
            }
        ],
    }


def _parent(payload: dict[str, object] | None = None) -> StoredGraphRevision:
    graph_payload = payload or _payload()
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id=WORLD_ID,
            revision_id=PARENT_REVISION_ID,
            parent_revision_id=None,
            created_at=NOW,
            operation_ids=["seed"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload_sha256=canonical_sha256(graph_payload),
        ),
        graph_payload=graph_payload,
    )


def test_rebind_rewrites_current_identity_and_relationships_only() -> None:
    parent = _parent()

    materialized = materialize_identity_reconciliation(
        parent,
        world_id=WORLD_ID,
        operation_id="op:rebind-ephanna",
        reconciliation_decisions=[
            CanonicalRebindRequest("node:ephanna", "pc:ephanna")
        ],
        actor="steward",
        reason="accepted canonical identity history",
        created_at=NOW,
    )

    object_ids = {record["object_id"] for record in materialized.graph_payload["objects"]}  # type: ignore[index]
    relationships = materialized.graph_payload["relationships"]  # type: ignore[assignment]
    assert object_ids == {"pc:ephanna", "node:companion"}
    assert relationships[0]["source_object_id"] == "pc:ephanna"  # type: ignore[index]
    assert materialized.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]
    assert materialized.decisions[0].source_object_id == "node:ephanna"
    assert materialized.decisions[0].target_object_id == "pc:ephanna"
    assert materialized.decisions[0].decision_kind.value == "canonical_rebind"


def test_six_rebinds_are_one_deterministic_child_materialization() -> None:
    old_ids = [f"node:pc-{index}" for index in range(1, 7)]
    new_ids = [f"pc:pc-{index}" for index in range(1, 7)]
    parent = _parent(_payload([*old_ids, "node:anchor"]))

    first = materialize_identity_reconciliation(
        parent,
        world_id=WORLD_ID,
        operation_id="op:six-rebinds",
        reconciliation_decisions=[
            CanonicalRebindRequest(source, target)
            for source, target in zip(old_ids, new_ids, strict=True)
        ],
        actor="steward",
        reason="canonical identity reconciliation",
        created_at=NOW,
    )
    second = materialize_identity_reconciliation(
        parent,
        world_id=WORLD_ID,
        operation_id="op:six-rebinds",
        reconciliation_decisions=[
            CanonicalRebindRequest(source, target)
            for source, target in reversed(list(zip(old_ids, new_ids, strict=True)))
        ],
        actor="steward",
        reason="canonical identity reconciliation",
        created_at=NOW,
    )

    assert len(first.decisions) == 6
    assert first.graph_payload == second.graph_payload
    assert first.expected_published_revision_id == second.expected_published_revision_id
    assert first.request_digest == second.request_digest


@pytest.mark.parametrize(
    ("decisions", "reason"),
    [
        (
            [
                CanonicalRebindRequest("node:ephanna", "pc:ephanna"),
                CanonicalRebindRequest("node:ephanna", "pc:other"),
            ],
            "duplicate_source_identity",
        ),
        (
            [
                CanonicalRebindRequest("node:ephanna", "pc:other"),
                CanonicalRebindRequest("node:companion", "pc:other"),
            ],
            "duplicate_target_identity",
        ),
        (
            [
                CanonicalRebindRequest("node:ephanna", "node:companion"),
            ],
            "target_identity_collision",
        ),
    ],
)
def test_invalid_batch_fails_before_materialization(
    decisions: list[CanonicalRebindRequest], reason: str
) -> None:
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_identity_reconciliation(
            _parent(),
            world_id=WORLD_ID,
            operation_id="op:invalid",
            reconciliation_decisions=decisions,
            actor="steward",
            reason=None,
            created_at=NOW,
        )
    assert exc.value.details["reason"] == reason


def test_unknown_source_fails_closed_without_rewriting_history() -> None:
    parent = _parent()
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_identity_reconciliation(
            parent,
            world_id=WORLD_ID,
            operation_id="op:unknown-source",
            reconciliation_decisions=[
                CanonicalRebindRequest("node:missing", "pc:missing")
            ],
            actor="steward",
            reason=None,
            created_at=NOW,
        )
    assert exc.value.details["reason"] == "unknown_source_identity"
    assert parent.graph_payload["objects"][0]["object_id"] == "node:ephanna"  # type: ignore[index]
