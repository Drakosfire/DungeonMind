"""Exact-six Eldyrwild PC preflight and replay composition proofs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.eldyrwild_pc_identity_reconciliation import (
    ELDYRWILD_PC_MAPPINGS,
    ELDYRWILD_WORLD_ID,
    materialize_from_persisted_reconciliation,
    preflight_eldyrwild_pc_identity_reconciliation,
)
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.application.world_identity_reconciliation import (
    materialize_identity_reconciliation,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.identity import IdentityReconciliationDecision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository
from tests.unit.test_world_identity_reconciliation import _payload

NOW = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)


class _History:
    def __init__(self, decisions: list[IdentityReconciliationDecision] | None = None) -> None:
        self.decisions = decisions or []

    def list_for_world(self, world_id: str) -> list[IdentityReconciliationDecision]:
        return [item for item in self.decisions if item.world_id == world_id]


def _seed_graph(object_ids: list[str] | None = None) -> InMemoryWorldGraphRepository:
    graph = InMemoryWorldGraphRepository()
    ids = object_ids or [item.source_object_id for item in ELDYRWILD_PC_MAPPINGS] + ["node:anchor"]
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=ELDYRWILD_WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:seed-eldyrwild-pcs"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=_payload(ids),
            created_at=NOW,
        )
    )
    return graph


def test_preflight_materializes_exact_six_and_inventories_current_parent() -> None:
    graph = _seed_graph()
    preflight = preflight_eldyrwild_pc_identity_reconciliation(
        graph,
        _History(),
        created_at=NOW,
    )

    assert preflight.ready_to_apply is True
    assert preflight.parent_revision_id
    assert len(preflight.mappings) == 6
    assert len(preflight.materialization.decisions) == 6
    assert preflight.expected_child_revision_id.startswith("rev:")
    assert preflight.object_count == 7
    assert preflight.relationship_count == 1
    assert preflight.affected_relationship_ids == ("rel:companions",)
    assert preflight.affected_evidence_ref_ids == ("ev:identity",)


def test_preflight_fails_closed_when_a_target_already_exists() -> None:
    graph = _seed_graph(
        [
            *(item.source_object_id for item in ELDYRWILD_PC_MAPPINGS),
            "pc:ephanna",
            "node:anchor",
        ]
    )

    with pytest.raises(PersistenceIntegrityError) as error:
        preflight_eldyrwild_pc_identity_reconciliation(graph, _History(), created_at=NOW)

    assert error.value.details["reason"] == "unexpected_cohort_identity_state"
    assert error.value.details["missing_source_object_ids"] == []
    assert error.value.details["present_target_object_ids"] == [
        "pc:ephanna",
    ]


def test_preflight_fails_closed_when_a_source_is_not_current_canonical() -> None:
    payload = _payload(
        [item.source_object_id for item in ELDYRWILD_PC_MAPPINGS] + ["node:anchor"]
    )
    payload["objects"][0]["assertion_metadata"]["canon_state"] = "provisional"  # type: ignore[index]
    graph = InMemoryWorldGraphRepository()
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=ELDYRWILD_WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:seed-noncanonical"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=NOW,
        )
    )

    with pytest.raises(PersistenceIntegrityError) as error:
        preflight_eldyrwild_pc_identity_reconciliation(graph, _History(), created_at=NOW)

    assert error.value.details["reason"] == "source_identity_not_current_canonical"


def test_preflight_reports_existing_history_as_not_ready() -> None:
    graph = _seed_graph()
    prior = IdentityReconciliationDecision(
        decision_id="dec:prior",
        world_id=ELDYRWILD_WORLD_ID,
        operation_id="op:prior",
        source_object_id="node:prior",
        target_object_id="pc:prior",
        actor="steward",
        reason="prior",
        created_at=NOW,
    )

    preflight = preflight_eldyrwild_pc_identity_reconciliation(
        graph,
        _History([prior]),
        created_at=NOW,
    )

    assert preflight.ready_to_apply is False
    assert preflight.existing_reconciliation_count == 1


def test_replay_uses_persisted_decisions_and_reproduces_materialized_child() -> None:
    graph = _seed_graph()
    head = graph.get_head(ELDYRWILD_WORLD_ID)
    assert head is not None
    parent = graph.get_revision(ELDYRWILD_WORLD_ID, head.head_revision_id)
    assert parent is not None
    first = materialize_identity_reconciliation(
        parent,
        world_id=ELDYRWILD_WORLD_ID,
        operation_id="op:persisted-six",
        reconciliation_decisions=[item.as_request() for item in ELDYRWILD_PC_MAPPINGS],
        actor="steward",
        reason="persisted proof",
        created_at=NOW,
    )

    replayed = materialize_from_persisted_reconciliation(parent, first.decisions)

    assert replayed.graph_payload == first.graph_payload
    assert replayed.expected_published_revision_id == first.expected_published_revision_id
    assert canonical_sha256(replayed.graph_payload) == canonical_sha256(first.graph_payload)
