"""HTTP-boundary proof for the curated browser consumer contract.

Proves CORS, success, abstention, exact replay, and changed-body conflict
against the real PostgreSQL-backed Mind Turn host. Does not import browser JS
as a knowledge implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_REQUEST = (
    REPO_ROOT / "examples" / "curated_mind_turn_surface" / "demo-request.json"
)
ALLOWED_ORIGIN = "http://127.0.0.1:8081"
DISALLOWED_ORIGIN = "http://127.0.0.1:9999"


@pytest.fixture
def cors_client(pg):
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
        cors_origin=ALLOWED_ORIGIN,
    )
    return TestClient(app), fixture, service


def _template_body(*, request_id: str, message: str | None = None) -> dict:
    import json

    body = json.loads(DEMO_REQUEST.read_text(encoding="utf-8"))
    body["request_id"] = request_id
    if message is not None:
        body["message"] = message
    return body


def test_endpoint_set_remains_healthz_readyz_mind_turn(cors_client) -> None:
    client, _fixture, _service = cors_client
    routes = sorted(
        {
            route.path
            for route in client.app.routes
            if getattr(route, "path", None) and not str(route.path).startswith("/docs")
            and not str(route.path).startswith("/openapi")
            and not str(route.path).startswith("/redoc")
        }
    )
    assert routes == ["/healthz", "/readyz", "/v1/mind-turn"]


def test_allowed_origin_preflight_and_post_cors(cors_client) -> None:
    client, _fixture, _service = cors_client
    preflight = client.options(
        "/v1/mind-turn",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code in {200, 204}
    assert preflight.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in {
        k.lower() for k in preflight.headers
    } or preflight.headers.get("access-control-allow-credentials") != "true"

    body = _template_body(request_id="req:b1b-cors-success")
    response = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert response.headers.get("access-control-allow-credentials") in (None, "false")


def test_disallowed_origin_is_not_granted(cors_client) -> None:
    client, _fixture, _service = cors_client
    preflight = client.options(
        "/v1/mind-turn",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
    assert preflight.headers.get("access-control-allow-origin") in (None, "null", "")

    body = _template_body(request_id="req:b1b-cors-denied")
    response = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": DISALLOWED_ORIGIN},
    )
    # Server may still execute the request; browser would hide the body.
    # The contract under test is that the disallowed origin is not granted.
    assert response.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN


def test_readyz_consumable_from_allowed_origin(cors_client) -> None:
    client, fixture, _service = cors_client
    response = client.get("/readyz", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["world_id"] == fixture.world_id
    assert str(payload["revision_id"]).startswith("rev:")


def test_success_renders_grounded_semantics(cors_client) -> None:
    client, _fixture, _service = cors_client
    response = client.post(
        "/v1/mind-turn",
        json=_template_body(request_id="req:b1b-success"),
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    body = response.json()
    assert "Mere Astor" in body["answer"]
    assert body["revision_id"].startswith("rev:")
    kinds = {proj["kind"] for proj in body["semantic_projections"]}
    assert "entity_brief" in kinds
    assert "relationship_list" in kinds
    assert "evidence_summary" in kinds
    labels = {
        proj["payload"].get("label")
        for proj in body["semantic_projections"]
        if proj["kind"] == "entity_brief"
    }
    assert "Mere Astor" in labels
    assert "Sun Ledger" in labels or any("Ledger" in (label or "") for label in labels)
    rels = []
    for proj in body["semantic_projections"]:
        if proj["kind"] == "relationship_list":
            rels.extend(proj["payload"].get("relationships") or [])
    assert any(rel.get("predicate") == "safeguards" for rel in rels)
    evidence_ids = []
    for proj in body["semantic_projections"]:
        if proj["kind"] == "evidence_summary":
            evidence_ids.extend(proj["payload"].get("evidence_ref_ids") or [])
    assert evidence_ids


def test_abstention_has_no_fabricated_entity_or_relationship(cors_client) -> None:
    client, _fixture, _service = cors_client
    response = client.post(
        "/v1/mind-turn",
        json=_template_body(
            request_id="req:b1b-moon-king",
            message="Who is the Moon King?",
        ),
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    body = response.json()
    entity_labels = [
        proj["payload"].get("label", "")
        for proj in body["semantic_projections"]
        if proj["kind"] == "entity_brief"
    ]
    assert not any("Moon King" in label for label in entity_labels)
    rel_projections = [
        proj
        for proj in body["semantic_projections"]
        if proj["kind"] == "relationship_list"
    ]
    assert rel_projections == [] or all(
        not (proj.get("payload") or {}).get("relationships") for proj in rel_projections
    )


def test_exact_replay_matches_and_skips_second_agent(cors_client) -> None:
    client, _fixture, service = cors_client
    body = _template_body(request_id="req:b1b-replay")
    first = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert first.status_code == 200
    after_first = service.agent_invocation_count
    second = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert second.status_code == 200
    assert second.json() == first.json()
    assert service.agent_invocation_count == after_first


def test_changed_body_same_request_id_returns_sanitized_conflict(cors_client) -> None:
    client, _fixture, _service = cors_client
    body = _template_body(request_id="req:b1b-conflict")
    first = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert first.status_code == 200
    conflict = client.post(
        "/v1/mind-turn",
        json=_template_body(
            request_id="req:b1b-conflict",
            message="Who is the Moon King?",
        ),
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert conflict.status_code == 409
    envelope = conflict.json()
    assert set(envelope.keys()) == {"error"}
    assert envelope["error"]["code"] == "idempotency_conflict"
    assert "message" in envelope["error"]
    # Prior truth remains authoritative: replaying the original still works.
    replay = client.post(
        "/v1/mind-turn",
        json=body,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert replay.status_code == 200
    assert replay.json() == first.json()
