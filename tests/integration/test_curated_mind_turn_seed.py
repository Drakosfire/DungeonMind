"""PostgreSQL seed proof for curated Mind Turn."""

from __future__ import annotations

import pytest

from dungeonmind.domain.errors import IdempotencyConflictError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)

pytestmark = pytest.mark.integration


def test_seed_is_idempotent(pg) -> None:
    fixture = load_curated_mind_turn_fixture()
    first = seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    second = seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    assert first.revision_id == second.revision_id
    assert first.embedding_run_id == second.embedding_run_id
    assert second.status == "reused"
    assert pg.embedding_runs.get_active_run_id(fixture.world_id) == first.embedding_run_id


def test_seed_rejects_different_existing_head(pg) -> None:
    fixture = load_curated_mind_turn_fixture()
    seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    # Mutate fixture payload identity without writing through seed.
    divergent = dict(fixture.raw)
    payload = dict(divergent["graph_payload"])
    nodes = list(payload["nodes"])
    nodes[0] = {**nodes[0], "label": "Not Vael"}
    payload["nodes"] = nodes
    divergent["graph_payload"] = payload

    class _Divergent:
        raw = divergent
        world_id = fixture.world_id
        graph_schema = fixture.graph_schema
        graph_payload = payload
        authorized_demo_binding = fixture.authorized_demo_binding

        def created_at(self):
            return fixture.created_at()

        def completed_at(self):
            return fixture.completed_at()

        def thread_created_at(self):
            return fixture.thread_created_at()

    with pytest.raises(IdempotencyConflictError, match="different graph head"):
        seed_curated_mind_turn(
            world_graph=pg.world_graph,
            sources=pg.sources,
            embedding_runs=pg.embedding_runs,
            semantic_documents=pg.semantic_documents,
            threads=pg.threads,
            fixture=_Divergent(),  # type: ignore[arg-type]
        )


def test_divergent_head_without_thread_rejects_before_writes(pg) -> None:
    """A conflicting head must fail closed before the demo thread is created."""
    from dungeonmind.contracts.graph import PublishRevisionCommand

    fixture = load_curated_mind_turn_fixture()
    payload = dict(fixture.graph_payload)
    nodes = list(payload["nodes"])
    nodes[0] = {**nodes[0], "label": "Not Vael"}
    payload["nodes"] = nodes
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:foreign-head"],
            graph_schema=fixture.graph_schema,
            graph_payload=payload,
            created_at=fixture.created_at(),
        )
    )
    thread_id = str(fixture.authorized_demo_binding["thread_id"])
    with pytest.raises(IdempotencyConflictError, match="different graph head"):
        seed_curated_mind_turn(
            world_graph=pg.world_graph,
            sources=pg.sources,
            embedding_runs=pg.embedding_runs,
            semantic_documents=pg.semantic_documents,
            threads=pg.threads,
            fixture=fixture,
        )
    with pg.database.connect() as conn:
        row = conn.execute(
            "SELECT 1 AS ok FROM dungeonmind.mind_threads WHERE thread_id = %s",
            (thread_id,),
        ).fetchone()
    assert row is None
