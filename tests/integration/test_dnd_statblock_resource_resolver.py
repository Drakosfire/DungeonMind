"""Real loopback provider composition through direct classic hydration."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest

from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind_dnd.application.threat_mechanics_transport import (
    DndThreatMechanicsTransportError,
    hydrate_threat_mechanics_request,
)
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
from tests.unit.test_dnd_threat_mechanics import _reader, _stored_revision

pytestmark = pytest.mark.integration

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json"
)
WORLD_ID = "world:synthetic-gatewatch"
REVISION_ID = "rev:6e02bd224f6b5616534f10026c8b9679"
OBJECT_ID = "obj:48e170969a2bb3980e437f7430b7b1c1"
PROVIDER_KEY = "integration-dungeonbuddy-key"
EXPECTED_DIGEST = "935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51"
PATH = f"{STATBLOCKS_ROUTE_PREFIX}/sb_000001/revisions/rev_000002"


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
    def __init__(self, body: bytes, *, status_code: int = 200) -> None:
        self.body = body
        self.status_code = status_code
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
                self.send_response(owner.status_code)
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


class _ProxyServer:
    def __init__(self) -> None:
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
                body = b"hostile proxy secret sentinel"
                self.send_response(502)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="statblock-proxy-loopback",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self) -> _ProxyServer:
        self.thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _hydrate(repository: _Repository, resolver: DndStatblockResourceResolver):
    return hydrate_threat_mechanics_request(
        _request(),
        graph_repository=cast(Any, repository),
        graph_reader=_reader(),
        resource_resolver=resolver,
    )


def _resolver(server: _ProviderServer) -> DndStatblockResourceResolver:
    return DndStatblockResourceResolver(
        config=DndStatblockResourceResolverConfig(
            base_url=server.base_url,
            internal_api_key=PROVIDER_KEY,
            timeout_seconds=5,
        )
    )


def test_exact_loopback_provider_response_hydrates_through_library() -> None:
    provider_bytes = FIXTURE.read_bytes()
    repository = _Repository(_stored_revision())
    with _ProviderServer(provider_bytes) as provider:
        resolver = _resolver(provider)
        try:
            response = _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert canonical_sha256(response.mechanics_payload) == EXPECTED_DIGEST
    assert response.mechanics_payload["identity"]["name"] == "Ironhide Brute"
    assert repository.get_revision_calls == [(WORLD_ID, REVISION_ID)]
    assert repository.get_head_calls == 0
    assert provider.calls == [
        {
            "method": "GET",
            "path": PATH,
            "authorization": PROVIDER_KEY,
        }
    ]


def test_public_resolver_bypasses_ambient_proxy_and_reaches_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _Repository(_stored_revision())
    with _ProviderServer(FIXTURE.read_bytes()) as provider, _ProxyServer() as proxy:
        for variable in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            monkeypatch.setenv(variable, proxy.base_url)
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")

        resolver = _resolver(provider)
        try:
            response = _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert canonical_sha256(response.mechanics_payload) == EXPECTED_DIGEST
    assert repository.get_revision_calls == [(WORLD_ID, REVISION_ID)]
    assert repository.get_head_calls == 0
    assert len(provider.calls) == 1
    assert proxy.calls == []


def test_repeated_exact_hydrations_are_isolated_and_uncached() -> None:
    repository = _Repository(_stored_revision())
    with _ProviderServer(FIXTURE.read_bytes()) as provider:
        resolver = _resolver(provider)
        try:
            first = _hydrate(repository, resolver)
            first.mechanics_payload["identity"]["name"] = "caller mutation"
            second = _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert second.mechanics_payload["identity"]["name"] == "Ironhide Brute"
    assert len(repository.get_revision_calls) == 2
    assert repository.get_head_calls == 0
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("status_code", "provider_body", "expected_code"),
    [
        (
            404,
            b"provider miss secret sentinel",
            "mechanics_resource_not_found",
        ),
        (
            410,
            b"provider gone secret sentinel",
            "mechanics_resource_not_found",
        ),
        (
            503,
            b"provider failure secret sentinel",
            "mechanics_resource_unavailable",
        ),
        (
            200,
            b'{"diagnostic":NaN}',
            "mechanics_resource_unavailable",
        ),
    ],
)
def test_provider_miss_and_unavailable_paths_are_exact_and_sanitized(
    status_code: int,
    provider_body: bytes,
    expected_code: str,
) -> None:
    repository = _Repository(_stored_revision())
    with _ProviderServer(provider_body, status_code=status_code) as provider:
        resolver = _resolver(provider)
        try:
            with pytest.raises(DndThreatMechanicsTransportError) as raised:
                _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert raised.value.reason == expected_code
    assert "secret sentinel" not in repr(raised.value.details) + str(raised.value)
    assert repository.get_revision_calls == [(WORLD_ID, REVISION_ID)]
    assert repository.get_head_calls == 0
    assert len(provider.calls) == 1
    assert provider.calls[0] == {
        "method": "GET",
        "path": PATH,
        "authorization": PROVIDER_KEY,
    }


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
            with pytest.raises(DndThreatMechanicsTransportError) as raised:
                _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert raised.value.reason == "mechanics_resource_integrity_failure"
    assert "Ironhide Brute" not in repr(raised.value.details) + str(raised.value)
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
            with pytest.raises(DndThreatMechanicsTransportError) as raised:
                _hydrate(repository, resolver)
        finally:
            resolver.close()

    assert raised.value.reason == "mechanics_resource_integrity_failure"
    assert "changed mechanics" not in repr(raised.value.details) + str(raised.value)
    assert "Ironhide Brute" not in repr(raised.value.details) + str(raised.value)
    assert len(provider.calls) == 1
