"""Replay and partial-persistence recovery over PostgreSQL HTTP path."""

from __future__ import annotations

import pytest

# Core CI installs neither the ``api`` nor ``postgres`` extras. Skip collection
# when FastAPI is absent so ``pytest -m "not integration"`` stays clean.
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.application.mind_turn import FixedClock, MindTurnService, _session_id_for
from dungeonmind.contracts.mind_turn import MindTurnRequest
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.service.api import create_app
from dungeonmind.service.bootstrap import build_readiness_probe
from dungeonmind.service.demo_access import DemoAccessBinding, authorize_demo_request

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


def seed_completed_turn(client, service, body):
    request = MindTurnRequest.model_validate(body)
    binding = client.app.state.mind_turn.demo_binding
    return service.execute(authorize_demo_request(request, binding=binding))


def test_exact_http_retry_does_not_reinvoke_agent(seeded) -> None:
    client, fixture, service, pg = seeded
    body = _body(fixture, "req:replay-1", "Who safeguards the Sun Ledger?")
    original = seed_completed_turn(client, service, body)
    first = client.post("/v1/mind-turn", json=body)
    assert first.status_code == 200
    assert first.json() == original.model_dump(mode="json")
    count_after_first = service.agent_invocation_count
    second = client.post("/v1/mind-turn", json=body)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert service.agent_invocation_count == count_after_first
    turns = pg.threads.list_turns(fixture.authorized_demo_binding["thread_id"])
    matching = [t for t in turns if t[0].request_id == "req:replay-1"]
    assert len(matching) == 1


def test_changed_payload_same_request_id_conflicts(seeded) -> None:
    client, fixture, service, _pg = seeded
    body = _body(fixture, "req:replay-conflict", "Who safeguards the Sun Ledger?")
    seed_completed_turn(client, service, body)
    changed = dict(body)
    changed["message"] = "Where does Mere Astor live?"
    response = client.post("/v1/mind-turn", json=changed)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


def test_concurrent_completed_replays_do_not_reinvoke_agent(seeded) -> None:
    import concurrent.futures

    client, fixture, service, pg = seeded
    body = _body(fixture, "req:concurrent-1", "Who safeguards the Sun Ledger?")

    seed_completed_turn(client, service, body)

    def _post() -> int:
        response = client.post("/v1/mind-turn", json=body)
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: _post(), range(2)))

    assert statuses == [200, 200]
    assert service.agent_invocation_count == 1
    turns = pg.threads.list_turns(fixture.authorized_demo_binding["thread_id"])
    matching = [t for t in turns if t[0].request_id == "req:concurrent-1"]
    assert len(matching) == 1


def test_unfinished_session_is_not_resumed_over_http(seeded, monkeypatch) -> None:
    client, fixture, service, pg = seeded
    request_id = "req:unfinished"
    body = _body(fixture, request_id, "Who safeguards the Sun Ledger?")

    def fail_append(*args, **kwargs):
        raise RuntimeError("fixture interruption after retrieval session persistence")

    with monkeypatch.context() as patch:
        patch.setattr(pg.threads, "append_turn", fail_append)
        with pytest.raises(RuntimeError, match="fixture interruption"):
            seed_completed_turn(client, service, body)

    session_id = _session_id_for(request_id)
    assert pg.retrieval_sessions.get(session_id) is not None
    turns = pg.threads.list_turns(body["thread_id"])
    agent_calls = service.agent_invocation_count

    def fail_session_lookup(*args, **kwargs):
        pytest.fail("receipt-only HTTP route inspected an unfinished retrieval session")

    monkeypatch.setattr(pg.retrieval_sessions, "get", fail_session_lookup)
    response = client.post("/v1/mind-turn", json=body)
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "classic_mind_turn_execution_retired"
    assert pg.threads.list_turns(body["thread_id"]) == turns
    assert service.agent_invocation_count == agent_calls
