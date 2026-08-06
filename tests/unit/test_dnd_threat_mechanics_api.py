"""HTTP proofs for the separate exact Threat mechanics host."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
)
from dungeonmind_dnd.integration.threat_mechanics_api import (
    ThreatMechanicsAccessBinding,
    create_threat_mechanics_app,
)
from tests.unit.test_dnd_threat_mechanics import _reader, _resource, _stored_revision

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
REQUEST_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-request-v1.json"
HYDRATION_SHA256 = "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
SECRET = "sentinel-threat-mechanics-bearer"
WORLD = "world:synthetic-gatewatch"
PATH = "/v1/dnd/threat-mechanics-hydrations"


def _body() -> dict[str, Any]:
    return json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))


class _Repository:
    def __init__(self, stored: StoredGraphRevision | None) -> None:
        self.stored = stored
        self.get_revision_calls: list[tuple[str, str]] = []
        self.get_head_calls = 0

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        self.get_revision_calls.append((world_id, revision_id))
        return None if self.stored is None else self.stored.model_copy(deep=True)

    def get_head(self, *_args: Any, **_kwargs: Any) -> None:
        self.get_head_calls += 1
        raise AssertionError("get_head must not be called")


class _Resolver:
    def __init__(self, envelope: DndMechanicsResourceEnvelope | None) -> None:
        self.envelope = envelope
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope | None:
        self.calls.append(resource_ref.model_copy(deep=True))
        return None if self.envelope is None else self.envelope.model_copy(deep=True)


class _CountingReader:
    def __init__(self) -> None:
        self.inner = _reader()
        self.calls = 0

    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]):
        self.calls += 1
        return self.inner.parse(
            graph_schema=graph_schema,
            graph_payload=graph_payload,
        )


def _app(
    repository: _Repository,
    resolver: _Resolver,
    *,
    readiness=None,
    reader=None,
):
    return create_threat_mechanics_app(
        graph_repository=cast(Any, repository),
        graph_reader=_reader() if reader is None else reader,
        resource_resolver=resolver,
        access_binding=ThreatMechanicsAccessBinding.from_secret(WORLD, SECRET),
        readiness_probe=readiness or (lambda: {"status": "ready"}),
    )


def _post(
    client: TestClient,
    body: dict[str, Any] | None = None,
    *,
    token: str = SECRET,
):
    return client.post(
        PATH,
        json=_body() if body is None else body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_success_returns_existing_hydration_and_no_store() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())

    with TestClient(_app(repository, resolver)) as client:
        response = _post(client)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/json")
    assert canonical_sha256(response.json()) == HYDRATION_SHA256
    assert response.json()["binding"]["binding_id"] == (
        "mechbind:872167afbc6e6a6b242c6d93036767ab"
    )
    assert repository.get_revision_calls == [
        (WORLD, "rev:6e02bd224f6b5616534f10026c8b9679")
    ]
    assert repository.get_head_calls == 0
    assert len(resolver.calls) == 1


@pytest.mark.parametrize("token", ["", "wrong", None])
def test_invalid_bearer_precedes_malformed_body_and_dependencies(token) -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}

    with TestClient(_app(repository, resolver)) as client:
        response = client.post(
            PATH,
            content=b'{"world_id": "__AUTH_SENTINEL__"',
            headers={**headers, "Content-Type": "application/json"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "capability_denied"
    assert "__AUTH_SENTINEL__" not in response.text
    assert repository.get_revision_calls == []
    assert resolver.calls == []


def test_valid_bearer_then_malformed_json_returns_sanitized_422() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())

    with TestClient(_app(repository, resolver)) as client:
        response = client.post(
            PATH,
            content=b"{",
            headers={
                "Authorization": f"Bearer {SECRET}",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
    assert repository.get_revision_calls == []
    assert resolver.calls == []


def test_valid_bearer_then_invalid_request_hides_rejected_values() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    body = _body()
    body["graph_revision_id"] = "SENTINEL_REJECTED_REVISION"

    with TestClient(_app(repository, resolver)) as client:
        response = _post(client, body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
    assert "SENTINEL_REJECTED_REVISION" not in response.text
    assert repository.get_revision_calls == []
    assert resolver.calls == []


@pytest.mark.parametrize(
    ("field_location", "sentinel"),
    [
        ("top-level", "TOP_LEVEL_SECRET_SENTINEL"),
        ("nested", "NESTED_SECRET_SENTINEL"),
    ],
)
def test_validation_hides_malicious_extra_keys_before_dependencies(
    field_location: str,
    sentinel: str,
) -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    reader = _CountingReader()
    body = _body()
    if field_location == "top-level":
        body[sentinel] = "attacker-controlled"
    else:
        body["resource_ref"][sentinel] = "attacker-controlled"

    with TestClient(_app(repository, resolver, reader=reader)) as client:
        response = _post(client, body)

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "request_validation_error",
        "message": "Request validation failed.",
        "details": {"errors": [{"type": "request_validation_error"}]},
    }
    assert sentinel not in response.text
    assert repository.get_revision_calls == []
    assert reader.calls == 0
    assert resolver.calls == []


def test_wrong_world_is_forbidden_before_repository_access() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    body = _body()
    body["world_id"] = "world:other"

    with TestClient(_app(repository, resolver)) as client:
        response = _post(client, body)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "capability_denied"
    assert repository.get_revision_calls == []
    assert resolver.calls == []


def test_missing_revision_is_404_and_does_not_resolve_resource() -> None:
    repository = _Repository(None)
    resolver = _Resolver(_resource())

    with TestClient(_app(repository, resolver)) as client:
        response = _post(client)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "graph_revision_not_found"
    assert len(repository.get_revision_calls) == 1
    assert resolver.calls == []


def test_forged_revision_is_409_before_resolver_access() -> None:
    stored = _stored_revision()
    forged = StoredGraphRevision(
        revision=stored.revision.model_copy(
            update={"revision_id": "rev:" + ("0" * 32)}
        ),
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    repository = _Repository(forged)
    resolver = _Resolver(_resource())

    with TestClient(_app(repository, resolver)) as client:
        response = _post(client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "threat_mechanics_binding_invalid"
    assert resolver.calls == []


def test_resource_miss_and_provider_failure_use_stable_codes() -> None:
    repository = _Repository(_stored_revision())
    with TestClient(_app(repository, _Resolver(None))) as client:
        missing = _post(client)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "mechanics_resource_not_found"

    class _ExplodingResolver(_Resolver):
        def resolve(self, _: DndMechanicsResourceRef) -> None:
            self.calls.append(_)
            raise RuntimeError("https://provider.invalid/secret-path")

    exploding = _ExplodingResolver(_resource())
    with TestClient(_app(_Repository(_stored_revision()), exploding)) as client:
        unavailable = _post(client)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "mechanics_resource_unavailable"
    assert "provider.invalid" not in unavailable.text
    assert "secret-path" not in unavailable.text
    assert len(exploding.calls) == 1


def test_wrong_resource_ref_returns_502_without_payload_bytes() -> None:
    resource = _resource()
    changed = DndMechanicsResourceEnvelope(
        resource_ref=resource.resource_ref.model_copy(
            update={"resource_id": "statblock:sentinel-resource"}
        ),
        mechanics_payload=copy.deepcopy(resource.mechanics_payload),
    )
    resolver = _Resolver(changed)

    with TestClient(_app(_Repository(_stored_revision()), resolver)) as client:
        response = _post(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "mechanics_resource_integrity_failure"
    assert "Tripod Null-Calf" not in response.text
    assert "sentinel-resource" not in response.text
    assert len(resolver.calls) == 1


def test_successive_posts_are_isolated_and_recomputed() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())

    with TestClient(_app(repository, resolver)) as client:
        first = _post(client)
        first_body = first.json()
        first_body["mechanics_payload"]["name"] = "client mutation"
        second = _post(client)

    assert first.status_code == second.status_code == 200
    assert second.json()["mechanics_payload"]["name"] == "Tripod Null-Calf"
    assert len(resolver.calls) == 2


def test_health_readiness_and_openapi_surface_are_narrow() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    readiness_calls = 0

    def readiness() -> dict[str, str]:
        nonlocal readiness_calls
        readiness_calls += 1
        return {"status": "ready"}

    app = _app(repository, resolver, readiness=readiness)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ready"}
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        oauth2_redirect = client.get("/docs/oauth2-redirect")
        preflight = client.options(
            PATH,
            headers={
                "Origin": "https://arbitrary.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        schema = client.get("/openapi.json").json()

    assert readiness_calls == 1
    assert docs.status_code == 404
    assert redoc.status_code == 404
    assert oauth2_redirect.status_code == 404
    assert preflight.headers.get("access-control-allow-origin") is None
    assert set(schema["paths"]) == {"/healthz", "/readyz", PATH}
    route_paths = {route.path for route in app.routes}
    assert route_paths == {"/openapi.json", "/healthz", "/readyz", PATH}
    route_methods = {
        route.path: set(route.methods or ())
        for route in app.routes
    }
    assert route_methods[PATH] == {"POST"}
    assert "GET" in route_methods["/healthz"]
    assert "GET" in route_methods["/readyz"]
    assert "GET" in route_methods["/openapi.json"]
    assert repository.get_revision_calls == []
    assert repository.get_head_calls == 0
    assert resolver.calls == []


def test_unexpected_service_error_is_sanitized(monkeypatch) -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())
    monkeypatch.setattr(
        "dungeonmind_dnd.integration.threat_mechanics_api.hydrate_threat_mechanics_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("database://secret-path")
        ),
    )

    with TestClient(_app(repository, resolver), raise_server_exceptions=False) as client:
        response = _post(client)

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
    assert "secret-path" not in response.text
