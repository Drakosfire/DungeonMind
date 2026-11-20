"""PostgreSQL and loopback HTTP proofs for B.2f-d."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from fastapi.testclient import TestClient

from dungeonmind.application.mind_turn import FixedClock
from dungeonmind.contracts import FinalizedReviewPublication
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceUnavailableError
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind.service.api import create_publication_app
from dungeonmind.service.bootstrap import (
    build_publication_readiness_probe,
    create_publication_service_app,
)
from dungeonmind.service.publication_access import PublicationAccessBinding
from tests.integration.test_postgres_review_publication import (
    PARENT_REVISION_ID,
    PUBLISHED_AT,
    PUBLISHED_REVISION_ID,
    REVIEW_ID,
    WORLD_ID,
    _head_event_count,
    _publish,
    _publish_descendant,
    _reader,
    _seed_tripod,
)

pytestmark = pytest.mark.integration

TOKEN = "sentinel-publication-bearer-token"
LATER = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
CLIENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "finalized_review_publication_client"
    / "client.py"
)


def _body(review_id: str = REVIEW_ID, world_id: str = WORLD_ID) -> dict[str, str]:
    return {
        "schema_version": "dm_finalized_review_publication_request_v1",
        "world_id": world_id,
        "review_id": review_id,
    }


def _app(
    bundle: PostgresRepositoryBundle,
    *,
    clock: datetime = PUBLISHED_AT,
    graph_reader: Any | None = None,
    publication_repository: Any | None = None,
    review_repository: Any | None = None,
):
    return create_publication_app(
        review_repository=(
            bundle.contribution_reviews
            if review_repository is None
            else review_repository
        ),
        world_graph_repository=bundle.world_graph,
        publication_repository=(
            bundle.finalized_review_publications
            if publication_repository is None
            else publication_repository
        ),
        graph_reader=_reader() if graph_reader is None else graph_reader,
        clock=FixedClock(clock),
        access_binding=PublicationAccessBinding.from_secret(WORLD_ID, TOKEN),
        readiness_probe=build_publication_readiness_probe(
            bundle=bundle,
            world_id=WORLD_ID,
        ),
    )


def _post(client: TestClient, *, body: dict[str, Any] | None = None, token: str = TOKEN):
    return client.post(
        "/v1/finalized-review-publications",
        json=_body() if body is None else body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_unpublished_finalized_review_cannot_advance_head(pg) -> None:
    _seed_tripod(pg)
    before_head = pg.world_graph.get_head(WORLD_ID)
    before_events = _head_event_count(pg)
    with TestClient(_app(pg, graph_reader=_RejectingReader())) as client:
        response = _post(client)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "contribution_review_not_found"
    assert pg.world_graph.get_head(WORLD_ID) == before_head
    assert pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None
    assert _head_event_count(pg) == before_events
    assert _publication_count(pg) == 0


def _publication_count(pg) -> int:
    with pg.database.connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.finalized_review_publications
            WHERE world_id = %s
            """,
            (WORLD_ID,),
        ).fetchone()
    return int(row["count"])


def test_immediate_replay_is_exact_and_does_not_materialize_or_write(pg) -> None:
    _seed_tripod(pg)
    original = _publish(pg, _reader())
    events = _head_event_count(pg)
    publications = _publication_count(pg)
    with TestClient(_app(pg, clock=LATER, graph_reader=_RejectingReader())) as replay_client:
        replay = _post(replay_client)
    assert replay.status_code == 200
    assert replay.json() == original.model_dump(mode="json")
    assert canonical_sha256(replay.json()) == (
        "3e7a632142c41066d3866c8682290fdc8e57b8f08b3324689c2964f6b045958c"
    )
    assert _head_event_count(pg) == events
    assert _publication_count(pg) == publications


def test_two_app_instances_replay_one_durable_record(pg, database_url: str) -> None:
    _seed_tripod(pg)
    _publish(pg, _reader())
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(database_url))
    app_a = _app(pg, clock=PUBLISHED_AT)
    app_b = _app(bundle_b, clock=LATER)
    barrier = threading.Barrier(2)
    responses: list[Any] = [None, None]

    def invoke(index: int, app) -> None:
        with TestClient(app) as client:
            barrier.wait(timeout=5)
            responses[index] = _post(client)

    threads = [
        threading.Thread(target=invoke, args=(0, app_a)),
        threading.Thread(target=invoke, args=(1, app_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert _publication_count(pg) == 1


class _RejectingReader:
    def read(self, *args, **kwargs):
        raise AssertionError("receipt replay must not open graph sources")


@pytest.mark.parametrize("head_state", ["descendant", "rollback"])
def test_historical_replay_does_not_follow_or_republish_current_head(pg, head_state: str) -> None:
    _seed_tripod(pg)
    original = _publish(pg, _reader())
    if head_state == "descendant":
        expected_head = _publish_descendant(pg, PUBLISHED_REVISION_ID).revision.revision_id
    else:
        pg.world_graph.rollback_head(
            WORLD_ID,
            PARENT_REVISION_ID,
            updated_at=LATER,
        )
        expected_head = PARENT_REVISION_ID
    events = _head_event_count(pg)
    with TestClient(_app(pg, clock=LATER, graph_reader=_RejectingReader())) as client:
        replay = _post(client)
    assert replay.status_code == 200
    assert replay.json() == original.model_dump(mode="json")
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == expected_head  # type: ignore[union-attr]
    assert _head_event_count(pg) == events


def test_missing_review_is_404_and_unauthorized_requests_do_not_lookup_or_mutate(pg) -> None:
    with TestClient(_app(pg)) as client:
        missing = _post(client, body=_body("review:missing"))
        unauthorized = _post(client, token="wrong-token")
        wrong_world = _post(client, body=_body(world_id="world:other"))
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "contribution_review_not_found"
    assert unauthorized.status_code == wrong_world.status_code == 403
    assert unauthorized.json()["error"]["code"] == "capability_denied"
    assert wrong_world.json()["error"]["code"] == "capability_denied"
    assert _publication_count(pg) == 0


def test_invalid_request_rejects_authority_fields_before_application(pg) -> None:
    with TestClient(_app(pg)) as client:
        response = _post(
            client,
            body={
                **_body(),
                "operation_id": "operation-sentinel",
                "graph_payload": {"campaign": "sentinel"},
            },
        )
    assert response.status_code == 422
    assert "operation-sentinel" not in response.text
    assert "campaign" not in response.text
    assert _publication_count(pg) == 0


def test_openapi_readiness_and_cors_contract(pg) -> None:
    _seed_tripod(pg)
    app = _app(pg)
    with TestClient(app) as client:
        openapi = client.get("/openapi.json")
        readiness = client.get("/readyz")
        preflight = client.options(
            "/v1/finalized-review-publications",
            headers={
                "Origin": "https://arbitrary.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        response = _post(client)
    assert set(path for path in openapi.json()["paths"]) == {
        "/healthz",
        "/readyz",
        "/v1/finalized-review-publications",
        "/v1/worlds/{world_id}/campaigns/{campaign_id}/ingest-context",
    }
    document = json.dumps(openapi.json())
    assert "FinalizedReviewPublicationCommand" not in document
    publication_schema = openapi.json()["components"]["schemas"]["FinalizedReviewPublication"]
    request_schema = openapi.json()["components"]["schemas"]["FinalizedReviewPublicationRequest"]
    assert "graph_payload" not in publication_schema["properties"]
    assert set(request_schema["properties"]) == {"schema_version", "world_id", "review_id"}
    assert readiness.json() == {
        "status": "ready",
        "world_id": WORLD_ID,
        "publication_schema": "dm_finalized_review_publication_v1",
    }
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in response.headers


def test_readiness_does_not_require_a_review_or_current_head(pg) -> None:
    with TestClient(_app(pg)) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["world_id"] == WORLD_ID
    assert _publication_count(pg) == 0


def test_publication_bootstrap_rejects_missing_configuration_without_secret_leak(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DUNGEONMIND_PUBLICATION_WORLD_ID", raising=False)
    monkeypatch.delenv("DUNGEONMIND_PUBLICATION_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("DUNGEONMIND_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DUNGEONMIND_PUBLICATION_WORLD_ID"):
        create_publication_service_app()

    monkeypatch.setenv("DUNGEONMIND_PUBLICATION_WORLD_ID", WORLD_ID)
    with pytest.raises(ValueError, match="DUNGEONMIND_PUBLICATION_BEARER_TOKEN"):
        create_publication_service_app()
    monkeypatch.setenv("DUNGEONMIND_PUBLICATION_BEARER_TOKEN", TOKEN)
    with pytest.raises(PersistenceUnavailableError) as raised:
        create_publication_service_app()
    assert TOKEN not in str(raised.value)
    assert TOKEN not in repr(raised.value)


def test_real_loopback_client_uses_exact_request_and_replay(pg) -> None:
    _seed_tripod(pg)
    _publish(pg, _reader())
    import uvicorn

    app = _app(pg)
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off")
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = int(sock.getsockname()[1])
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with __import__("urllib.request", fromlist=["urlopen"]).urlopen(
                f"{base_url}/healthz",
                timeout=0.5,
            ) as health:
                if health.status == 200:
                    break
        except OSError:
            time.sleep(0.02)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("loopback publication server did not become ready")
    env = os.environ.copy()
    env["DUNGEONMIND_PUBLICATION_BEARER_TOKEN"] = TOKEN
    result = subprocess.run(
        [
            sys.executable,
            str(CLIENT_PATH),
            "--base-url",
            base_url,
            "--world-id",
            WORLD_ID,
            "--review-id",
            REVIEW_ID,
            "--verify-replay",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[2],
    )
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert result.returncode == 0, result.stderr
    publication = FinalizedReviewPublication.model_validate(json.loads(result.stdout))
    assert publication.published_revision_id == PUBLISHED_REVISION_ID
    assert TOKEN not in result.stdout
    assert TOKEN not in result.stderr
    assert _publication_count(pg) == 1
