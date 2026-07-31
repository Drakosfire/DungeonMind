"""HTTP Mind Turn API over PostgreSQL."""

from __future__ import annotations

import pytest

# Core CI installs neither the ``api`` nor ``postgres`` extras. Skip collection
# when FastAPI is absent so ``pytest -m "not integration"`` stays clean.
pytest.importorskip("fastapi")

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
def seeded_client(pg):
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
    return TestClient(app), fixture, service


def _request_body(fixture, *, request_id: str, message: str, **overrides):
    binding = fixture.authorized_demo_binding
    body = {
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
    body.update(overrides)
    return body


def test_healthz_readyz_and_mind_turn(seeded_client) -> None:
    client, fixture, _service = seeded_client
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/readyz")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["world_id"] == fixture.world_id
    assert payload["embedding_run_id"] == fixture.raw["embedding_run"]["run_id"]

    response = client.post(
        "/v1/mind-turn",
        json=_request_body(
            fixture,
            request_id="req:api-safeguards",
            message="Who safeguards the Sun Ledger?",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "mind_turn_v1"
    assert "Mere Astor" in body["answer"]
    assert body["revision_id"].startswith("rev:")
    assert body["source_reads"] == []


def test_grounded_miss(seeded_client) -> None:
    client, fixture, _service = seeded_client
    response = client.post(
        "/v1/mind-turn",
        json=_request_body(
            fixture,
            request_id="req:api-moon-king",
            message="Who is the Moon King?",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Moon King" not in "".join(
        str(proj.get("payload", {}).get("label", ""))
        for proj in body["semantic_projections"]
    )
    assert any(
        "do not have grounded knowledge" in body["answer"].lower()
        or "abstain" in d.get("code", "")
        for d in [{"answer": body["answer"]}, *body.get("diagnostics", [])]
    )


def test_caller_mismatch_forbidden(seeded_client) -> None:
    client, fixture, _service = seeded_client
    response = client.post(
        "/v1/mind-turn",
        json=_request_body(
            fixture,
            request_id="req:api-bad-caller",
            message="Who safeguards the Sun Ledger?",
            caller_scope={
                "caller_id": "caller:intruder",
                "tenant_id": None,
                "roles": list(fixture.authorized_demo_binding["roles"]),
            },
        ),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "capability_denied"


def test_admissibility_escalation_forbidden(seeded_client) -> None:
    client, fixture, _service = seeded_client
    # Binding is GM; request player is still a mismatch (exact match required).
    response = client.post(
        "/v1/mind-turn",
        json=_request_body(
            fixture,
            request_id="req:api-player",
            message="Who safeguards the Sun Ledger?",
            admissibility="player",
        ),
    )
    assert response.status_code == 403


def test_invalid_payload_422(seeded_client) -> None:
    client, _fixture, _service = seeded_client
    response = client.post("/v1/mind-turn", json={"schema_version": "mind_turn_v1"})
    assert response.status_code == 422


def test_openapi_only_intended_endpoints(seeded_client) -> None:
    client, _fixture, _service = seeded_client
    paths = set(client.app.openapi()["paths"])
    assert paths == {"/healthz", "/readyz", "/v1/mind-turn"}


def test_missing_revision_mapped_404(seeded_client) -> None:
    client, fixture, _service = seeded_client
    response = client.post(
        "/v1/mind-turn",
        json=_request_body(
            fixture,
            request_id="req:api-missing-rev",
            message="Who safeguards the Sun Ledger?",
            requested_revision_id="rev:does-not-exist",
        ),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "revision_not_found"
