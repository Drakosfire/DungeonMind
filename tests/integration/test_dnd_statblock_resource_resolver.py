"""Real loopback composition of the statblock resolver through PR #20."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind_dnd.contracts.mechanics_resources import DndMechanicsResourceRef
from dungeonmind_dnd.contracts.mechanics_transport import (
    DndThreatMechanicsHydrationRequest,
)
from dungeonmind_dnd.integration.statblock_resource_resolver import (
    STATBLOCKS_AUTH_HEADER,
    STATBLOCKS_MEDIA_TYPE,
    STATBLOCKS_PROVIDER_ID,
    STATBLOCKS_RESOURCE_SCHEMA,
    STATBLOCKS_ROUTE_PREFIX,
    DndStatblockResourceResolver,
    DndStatblockResourceResolverConfig,
)
from dungeonmind_dnd.integration.threat_mechanics_api import (
    ThreatMechanicsAccessBinding,
    create_threat_mechanics_app,
)
from tests.unit.test_dnd_threat_mechanics import _reader, _stored_revision

pytestmark = pytest.mark.integration

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json"
)
WORLD_ID = "world:synthetic-gatewatch"
REVISION_ID = "rev:6e02bd224f6b5616534f10026c8b9679"
OBJECT_ID = "obj:48e170969a2bb3980e437f7430b7b1c1"
TOKEN = "integration-threat-mechanics-token"
PROVIDER_KEY = "integration-dungeonbuddy-key"
EXPECTED_DIGEST = "935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51"
PATH = f"{STATBLOCKS_ROUTE_PREFIX}/sb_000001/revisions/rev_000002"
HYDRATION_PATH = "/v1/dnd/threat-mechanics-hydrations"


def _provider_body() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _request() -> DndThreatMechanicsHydrationRequest:
    return DndThreatMechanicsHydrationRequest(
        world_id=WORLD_ID,
        graph_revision_id=REVISION_ID,
        object_id=OBJECT_ID,
        resource_ref=DndMechanicsResourceRef(
            ruleset_id="dnd5e",
            provider_id=STATBLOCKS_PROVIDER_ID,
            resource_id="sb_000001",
            resource_revision="rev_000002",
            resource_schema=STATBLOCKS_RESOURCE_SCHEMA,
            media_type=STATBLOCKS_MEDIA_TYPE,
            payload_sha256=EXPECTED_DIGEST,
        ),
    )


class _Repository:
    def __init__(self, stored: StoredGraphRevision) -> None:
        self.stored = stored
        self.get_revision_calls: list[tuple[str, str]] = []
        self.get_head_calls = 0

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision:
        self.get_revision_calls.append((world_id, revision_id))
        return self.stored.model_copy(deep=True)

    def get_head(self, *_args: Any, **_kwargs: Any) -> None:
        self.get_head_calls += 1
        raise AssertionError("exact hydration must not read current head")


class _ProviderServer:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[dict[str, str]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.calls.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get(STATBLOCKS_AUTH_HEADER, ""),
                    }
                )
                if self.path != PATH:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(owner.body)))
                self.end_headers()
                self.wfile.write(owner.body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="statblock-provider-loopback",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self) -> _ProviderServer:
        self.thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _app(repository: _Repository, resolver: DndStatblockResourceResolver):
    return create_threat_mechanics_app(
        graph_repository=cast(Any, repository),
        graph_reader=_reader(),
        resource_resolver=resolver,
        access_binding=ThreatMechanicsAccessBinding.from_secret(WORLD_ID, TOKEN),
        readiness_probe=lambda: {"status": "ready"},
    )


def _post(client: TestClient) -> Any:
    return client.post(
        HYDRATION_PATH,
        json=_request().model_dump(mode="json"),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


def _resolver(server: _ProviderServer) -> DndStatblockResourceResolver:
    return DndStatblockResourceResolver(
        config=DndStatblockResourceResolverConfig(
            base_url=server.base_url,
            internal_api_key=PROVIDER_KEY,
            timeout_seconds=5,
        )
    )


def test_exact_provider_response_hydrates_through_pr20_loopback() -> None:
    provider_bytes = FIXTURE.read_bytes()
    repository = _Repository(_stored_revision())
    with _ProviderServer(provider_bytes) as provider:
        resolver = _resolver(provider)
        try:
            with TestClient(_app(repository, resolver)) as client:
                response = _post(client)
        finally:
            resolver.close()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert canonical_sha256(response.json()["mechanics_payload"]) == EXPECTED_DIGEST
    assert response.json()["mechanics_payload"]["identity"]["name"] == "Ironhide Brute"
    assert repository.get_revision_calls == [(WORLD_ID, REVISION_ID)]
    assert repository.get_head_calls == 0
    assert provider.calls == [
        {
            "method": "GET",
            "path": PATH,
            "authorization": PROVIDER_KEY,
        }
    ]


def test_repeated_exact_posts_are_isolated_and_uncached() -> None:
    repository = _Repository(_stored_revision())
    with _ProviderServer(FIXTURE.read_bytes()) as provider:
        resolver = _resolver(provider)
        try:
            with TestClient(_app(repository, resolver)) as client:
                first = _post(client)
                first_body = first.json()
                first_body["mechanics_payload"]["identity"]["name"] = "client mutation"
                second = _post(client)
        finally:
            resolver.close()

    assert first.status_code == second.status_code == 200
    assert second.json()["mechanics_payload"]["identity"]["name"] == "Ironhide Brute"
    assert len(repository.get_revision_calls) == 2
    assert repository.get_head_calls == 0
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        lambda body: body.update({"statblock_id": "sb_000999"}),
        lambda body: body.update({"revision_id": "rev_000999"}),
        lambda body: body.update({"contract_version": "1.0.1"}),
    ],
)
def test_provider_identity_or_schema_disagreement_is_b3a_integrity_failure(
    mutation,
) -> None:
    body = _provider_body()
    mutation(body)
    repository = _Repository(_stored_revision())
    with _ProviderServer(json.dumps(body, separators=(",", ":")).encode()) as provider:
        resolver = _resolver(provider)
        try:
            with TestClient(_app(repository, resolver)) as client:
                response = _post(client)
        finally:
            resolver.close()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "mechanics_resource_integrity_failure"
    assert "Ironhide Brute" not in response.text
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda body: body.update({"definition_digest": "sha256:" + ("0" * 64)}),
        lambda body: body.update(
            {
                "canonical_definition": json.dumps(
                    {"identity": {"name": "changed mechanics"}},
                    separators=(",", ":"),
                )
            }
        ),
        lambda body: body.update(
            {"canonical_definition": json.dumps(["not", "an", "object"])}
        ),
    ],
)
def test_provider_digest_or_payload_disagreement_is_b3a_integrity_failure(
    mutation,
) -> None:
    body = _provider_body()
    mutation(body)
    repository = _Repository(_stored_revision())
    with _ProviderServer(json.dumps(body, separators=(",", ":")).encode()) as provider:
        resolver = _resolver(provider)
        try:
            with TestClient(_app(repository, resolver)) as client:
                response = _post(client)
        finally:
            resolver.close()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "mechanics_resource_integrity_failure"
    assert "changed mechanics" not in response.text
    assert "Ironhide Brute" not in response.text
    assert len(provider.calls) == 1
