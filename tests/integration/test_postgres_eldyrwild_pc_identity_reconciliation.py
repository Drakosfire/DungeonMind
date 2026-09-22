"""Owning PostgreSQL proof for the bounded Eldyrwild six-PC operation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.eldyrwild_pc_identity_reconciliation import (
    ELDYRWILD_PC_MAPPINGS,
    ELDYRWILD_WORLD_ID,
    apply_eldyrwild_pc_identity_reconciliation,
    materialize_from_persisted_reconciliation,
    preflight_eldyrwild_pc_identity_reconciliation,
)
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle
from tests.unit.test_world_identity_reconciliation import _payload

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)


def _seed(pg):
    return pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=ELDYRWILD_WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:seed-eldyrwild-pcs"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=_payload(
                [item.source_object_id for item in ELDYRWILD_PC_MAPPINGS] + ["node:anchor"]
            ),
            created_at=NOW,
        )
    )


def test_postgres_eldyrwild_six_pc_publish_reload_replay(pg) -> None:
    seeded = _seed(pg)
    preflight = preflight_eldyrwild_pc_identity_reconciliation(
        pg.world_graph,
        pg.identity_reconciliation,
        created_at=NOW,
    )
    assert preflight.parent_revision_id == seeded.revision_id
    assert preflight.ready_to_apply is True

    result = apply_eldyrwild_pc_identity_reconciliation(
        preflight,
        pg.world_graph,
        pg.identity_reconciliation,
        published_at=NOW,
    )

    restarted = PostgresRepositoryBundle(pg.database)
    parent = restarted.world_graph.get_revision(ELDYRWILD_WORLD_ID, result.parent_revision_id)
    child = restarted.world_graph.get_revision(ELDYRWILD_WORLD_ID, result.published_revision_id)
    assert parent is not None
    assert child is not None
    head = restarted.world_graph.get_head(ELDYRWILD_WORLD_ID)
    assert head is not None
    assert head.head_revision_id == result.published_revision_id

    child_ids = {record["object_id"] for record in child.graph_payload["objects"]}
    assert {item.target_object_id for item in ELDYRWILD_PC_MAPPINGS} <= child_ids
    assert not {item.source_object_id for item in ELDYRWILD_PC_MAPPINGS} & child_ids
    assert child.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]
    assert len(restarted.identity_reconciliation.list_for_world(ELDYRWILD_WORLD_ID)) == 6

    persisted = restarted.identity_reconciliation.list_for_world(ELDYRWILD_WORLD_ID)
    replayed = materialize_from_persisted_reconciliation(parent, persisted)
    assert replayed.graph_payload == child.graph_payload
    assert replayed.expected_published_revision_id == child.revision.revision_id
