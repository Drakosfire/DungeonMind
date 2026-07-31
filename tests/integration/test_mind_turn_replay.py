"""Replay and partial-persistence recovery over PostgreSQL HTTP path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.service.api import create_app
from dungeonmind.service.bootstrap import build_readiness_probe
from dungeonmind.service.demo_access import DemoAccessBinding

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded(pg):
    fixture = load_curated_mind_turn_fixture()
    seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    binding = DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)
    service = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=UnionGraphV1SnapshotReader(),
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(fixture.created_at()),
    )
    app = create_app(
        service=service,
        demo_binding=binding,
        readiness_probe=build_readiness_probe(
            bundle=pg,
            world_id=fixture.world_id,
            embedding_run_id=str(fixture.raw["embedding_run"]["run_id"]),
            thread_id=str(fixture.authorized_demo_binding["thread_id"]),
        ),
    )
    return TestClient(app), fixture, service, pg


def _body(fixture, request_id: str, message: str):
    binding = fixture.authorized_demo_binding
    return {
        "schema_version": "mind_turn_v1",
        "request_id": request_id,
        "thread_id": binding["thread_id"],
        "caller_scope": {
            "caller_id": binding["caller_id"],
            "tenant_id": binding["tenant_id"],
            "roles": list(binding["roles"]),
        },
        "world_id": binding["world_id"],
        "campaign_id": binding["campaign_id"],
        "admissibility": binding["admissibility"],
        "surface_context": {"surface_id": binding["surface_id"]},
        "message": message,
    }


def test_exact_http_retry_does_not_reinvoke_agent(seeded) -> None:
    client, fixture, service, pg = seeded
    body = _body(fixture, "req:replay-1", "Who safeguards the Sun Ledger?")
    first = client.post("/v1/mind-turn", json=body)
    assert first.status_code == 200
    count_after_first = service.agent_invocation_count
    second = client.post("/v1/mind-turn", json=body)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert service.agent_invocation_count == count_after_first
    turns = pg.threads.list_turns(fixture.authorized_demo_binding["thread_id"])
    matching = [t for t in turns if t[0].request_id == "req:replay-1"]
    assert len(matching) == 1


def test_changed_payload_same_request_id_conflicts(seeded) -> None:
    client, fixture, _service, _pg = seeded
    body = _body(fixture, "req:replay-conflict", "Who safeguards the Sun Ledger?")
    assert client.post("/v1/mind-turn", json=body).status_code == 200
    changed = dict(body)
    changed["message"] = "Where does Mere Astor live?"
    response = client.post("/v1/mind-turn", json=changed)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"
