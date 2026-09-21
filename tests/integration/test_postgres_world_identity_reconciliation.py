"""Owning PostgreSQL proofs for atomic current-World identity reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.application.world_identity_reconciliation import (
    CanonicalRebindRequest,
    materialize_identity_reconciliation,
    publish_identity_reconciliation,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.postgres import (
    PostgresRepositoryBundle,
    PostgresWorldIdentityReconciliationRepository,
)
from tests.unit.test_world_identity_reconciliation import (
    NOW,
    WORLD_ID,
    _payload,
)

pytestmark = pytest.mark.integration


def _seed(pg, *, object_ids: list[str] | None = None):
    return pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:seed"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=_payload(object_ids),
            created_at=NOW,
        )
    )


def _requests(count: int = 6) -> list[CanonicalRebindRequest]:
    return [
        CanonicalRebindRequest(f"node:pc-{index}", f"pc:pc-{index}")
        for index in range(1, count + 1)
    ]


def _publish(pg, parent_id: str, *, repository=None, requests=None, operation_id="op:six"):
    return publish_identity_reconciliation(
        WORLD_ID,
        parent_id,
        operation_id,
        requests or _requests(),
        actor="steward",
        reason="canonical identity reconciliation",
        published_at=NOW,
        world_graph_repository=pg.world_graph,
        reconciliation_repository=repository or pg.identity_reconciliation,
    )


@pytest.mark.integration
def test_postgres_legacy_identity_append_rejects_reconciliation_record(pg) -> None:
    seeded_parent = _seed(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, seeded_parent.revision_id)
    assert parent is not None
    materialized = materialize_identity_reconciliation(
        parent,
        world_id=WORLD_ID,
        operation_id="op:append-guard",
        reconciliation_decisions=[CanonicalRebindRequest("node:ephanna", "pc:ephanna")],
        actor="steward",
        reason=None,
        created_at=NOW,
    )

    with pytest.raises(PersistenceIntegrityError, match="atomic reconciliation publisher"):
        pg.identity_decisions.append(materialized.decisions[0])  # type: ignore[arg-type]
    assert pg.identity_decisions.list_for_world(WORLD_ID) == []
    assert pg.identity_reconciliation.list_for_world(WORLD_ID) == []


@pytest.mark.integration
def test_postgres_reconciliation_restart_replay_and_exact_retry(pg) -> None:
    seeded_parent = _seed(
        pg,
        object_ids=[*(f"node:pc-{index}" for index in range(1, 7)), "node:anchor"],
    )
    parent = pg.world_graph.get_revision(WORLD_ID, seeded_parent.revision_id)
    assert parent is not None
    result = _publish(pg, parent.revision.revision_id)

    child = pg.world_graph.get_revision(WORLD_ID, result.published_revision_id)
    assert child is not None
    assert child.revision.parent_revision_id == parent.revision.revision_id
    assert len(pg.identity_decisions.list_for_world(WORLD_ID)) == 6
    assert {item["object_id"] for item in child.graph_payload["objects"]} == {  # type: ignore[index]
        *(f"pc:pc-{index}" for index in range(1, 7)),
        "node:anchor",
    }
    assert child.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]

    with pg.database.connect() as conn:
        before = {
            "revisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
            "head_events": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_head_events "
                "WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
            "decisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.identity_decisions WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
        }
    # The second bundle models a process restart. It reads the exact stored
    # parent, child, head, and decisions through fresh connections.
    restarted = PostgresRepositoryBundle(pg.database)
    assert restarted.world_graph.get_head(WORLD_ID).head_revision_id == result.published_revision_id  # type: ignore[union-attr]
    stored_decisions = restarted.identity_reconciliation.list_for_world(WORLD_ID)
    assert len(stored_decisions) == 6
    replayed = materialize_identity_reconciliation(
        parent,
        world_id=WORLD_ID,
        operation_id=stored_decisions[0].operation_id,
        reconciliation_decisions=[
            CanonicalRebindRequest(
                decision.source_object_id,
                decision.target_object_id,
            )
            for decision in stored_decisions
        ],
        actor=stored_decisions[0].actor,
        reason=stored_decisions[0].reason,
        created_at=stored_decisions[0].created_at,
    )
    assert replayed.graph_payload == child.graph_payload

    retried = _publish(
        restarted,
        parent.revision.revision_id,
        repository=restarted.identity_reconciliation,
    )
    assert retried.already_applied is True
    assert retried.published_revision_id == result.published_revision_id
    assert retried.decision_ids == result.decision_ids
    with pg.database.connect() as conn:
        after = {
            "revisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
            "head_events": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_head_events "
                "WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
            "decisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.identity_decisions WHERE world_id = %s",
                (WORLD_ID,),
            ).fetchone()["count"],
        }
    assert after == before


@pytest.mark.integration
@pytest.mark.parametrize("failure_phase", ["identity_decision_4", "before_graph_revision"])
def test_postgres_reconciliation_failure_rolls_back_every_family(
    pg, failure_phase: str
) -> None:
    parent = _seed(
        pg,
        object_ids=[*(f"node:pc-{index}" for index in range(1, 7)), "node:anchor"],
    )

    def fail(phase: str) -> None:
        if phase == failure_phase:
            raise RuntimeError(f"injected {phase}")

    repository = PostgresWorldIdentityReconciliationRepository(
        pg.database,
        failure_hook=fail,
    )
    with pytest.raises(RuntimeError, match=failure_phase):
        _publish(
            pg,
            parent.revision_id,
            repository=repository,
        )

    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == parent.revision_id  # type: ignore[union-attr]
    assert pg.identity_decisions.list_for_world(WORLD_ID) == []
    with pg.database.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s",
            (WORLD_ID,),
        ).fetchone()["count"] == 1


@pytest.mark.integration
def test_postgres_reconciliation_stale_parent_has_zero_effects(pg) -> None:
    parent = _seed(
        pg,
        object_ids=[*(f"node:pc-{index}" for index in range(1, 7)), "node:anchor"],
    )
    advanced = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision_id,
            expected_parent_revision_id=parent.revision_id,
            operation_ids=["op:independent-advance"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=_payload(),
            created_at=datetime(2026, 9, 21, 13, 0, tzinfo=UTC),
        )
    )

    with pytest.raises(StaleParentRevisionError):
        _publish(pg, parent.revision_id, operation_id="op:stale")

    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == advanced.revision_id  # type: ignore[union-attr]
    assert pg.identity_decisions.list_for_world(WORLD_ID) == []
    with pg.database.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s",
            (WORLD_ID,),
        ).fetchone()["count"] == 2


@pytest.mark.integration
def test_postgres_reconciliation_same_operation_different_material_conflicts(pg) -> None:
    parent = _seed(pg)
    _publish(
        pg,
        parent.revision_id,
        operation_id="op:conflict",
        requests=[CanonicalRebindRequest("node:ephanna", "pc:ephanna")],
    )

    with pytest.raises(IdempotencyConflictError):
        _publish(
            pg,
            parent.revision_id,
            operation_id="op:conflict",
            requests=[CanonicalRebindRequest("node:ephanna", "pc:other")],
        )
    assert len(pg.identity_decisions.list_for_world(WORLD_ID)) == 1
