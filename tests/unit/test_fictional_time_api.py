"""FT1b HTTP host proofs: auth-before-read, sanitized errors, no-store."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.contracts.fictional_time import (
    FICTIONAL_TIME_QUERY_SCHEMA,
    FictionalTimeClaimBundle,
)
from dungeonmind.contracts.fictional_time_transport import (
    FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA,
)
from dungeonmind.contracts.graph import PublishRevisionCommand, StoredGraphRevision
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository
from dungeonmind.service.api import create_fictional_time_query_app
from dungeonmind.service.bootstrap import build_fictional_time_readiness_probe
from dungeonmind.service.fictional_time_access import FictionalTimeQueryAccessBinding

FIX = Path(__file__).resolve().parents[1] / "fixtures/fictional_time"
ROOT = Path(__file__).resolve().parents[2] / "src/dungeonmind"
SECRET = "sentinel-fictional-time-bearer"
WORLD = "world:ft1-fictional-time"
SENTINEL = "__FT1A_SENTINEL_LEAK_PROBE__"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"
GATE = "anchor:lysandra-mireward-gate-arrival"
STATE = "state:lysandra-returned-home-current-campaign-arc"
BOUNDARY = "state-boundary:lysandra-returned-at-mireward-gate"
LATER = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)
READER = UnionGraphV1SnapshotReader()


def _gold_queries() -> list[dict[str, Any]]:
    return [
        {
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:hempholm-tree-before-beetles",
            "query_kind": "strict_before",
            "before_anchor_id": TREE,
            "after_anchor_id": BEETLES,
        },
        {
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:hempholm-tree-absolute-time",
            "query_kind": "absolute_fictional_time",
            "anchor_id": TREE,
        },
        {
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:lysandra-returned-before-gate",
            "query_kind": "state_at_boundary",
            "state_id": STATE,
            "boundary_anchor_id": GATE,
            "position": "immediately_before",
        },
        {
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:lysandra-returned-after-gate",
            "query_kind": "state_at_boundary",
            "state_id": STATE,
            "boundary_anchor_id": GATE,
            "position": "immediately_after",
        },
    ]


def _seed(repo: InMemoryWorldGraphRepository):
    stored = StoredGraphRevision.model_validate(
        json.loads((FIX / "ft1-two-case-graph-v1.json").read_text())
    )
    rev = repo.publish_revision(
        PublishRevisionCommand(
            world_id=stored.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=list(stored.revision.operation_ids),
            graph_schema=stored.revision.graph_schema,
            graph_payload=copy.deepcopy(stored.graph_payload),
            created_at=stored.revision.created_at,
        )
    )
    bundle = FictionalTimeClaimBundle.model_validate(
        json.loads((FIX / "ft1-two-case-claim-bundle-v1.json").read_text())
    ).model_copy(
        update={
            "graph_revision_id": rev.revision_id,
            "graph_payload_sha256": rev.graph_payload_sha256,
        }
    )
    return rev, bundle


class _CountingRepo:
    def __init__(self, inner: InMemoryWorldGraphRepository) -> None:
        self.inner = inner
        self.get_revision_calls = 0

    def get_revision(self, world_id: str, revision_id: str):
        self.get_revision_calls += 1
        return self.inner.get_revision(world_id, revision_id)

    def get_head(self, world_id: str):
        return self.inner.get_head(world_id)

    def publish_revision(self, command: PublishRevisionCommand):
        return self.inner.publish_revision(command)

    def rollback_head(self, world_id: str, target_revision_id: str, *, updated_at):
        return self.inner.rollback_head(world_id, target_revision_id, updated_at=updated_at)


class _TamperedRepo(_CountingRepo):
    def get_revision(self, world_id: str, revision_id: str):
        self.get_revision_calls += 1
        stored = self.inner.get_revision(world_id, revision_id)
        if stored is None:
            return None
        bad = stored.model_copy(deep=True)
        bad.graph_payload = copy.deepcopy(bad.graph_payload)
        bad.graph_payload["nodes"][0]["label"] = "tampered"
        return bad


def _body(bundle: FictionalTimeClaimBundle, query: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA,
        "world_id": WORLD,
        "graph_revision_id": bundle.graph_revision_id,
        "claim_bundle": bundle.model_dump(mode="json"),
        "query": query,
    }


def _app(repo, *, readiness=None):
    default_ready = {
        "status": "ready",
        "world_id": WORLD,
        "request_schema": FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA,
        "result_schema": "dm_fictional_time_query_result_v1",
    }
    return create_fictional_time_query_app(
        world_graph_repository=repo,
        graph_reader=READER,
        access_binding=FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET),
        readiness_probe=readiness or (lambda: default_ready),
    )


def _post(client: TestClient, body: dict[str, Any], token: str = SECRET):
    return client.post(
        "/v1/fictional-time-shadow-queries",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.fixture
def seeded_client():
    repo = _CountingRepo(InMemoryWorldGraphRepository())
    rev, bundle = _seed(repo.inner)
    with TestClient(_app(repo)) as client:
        yield client, repo, rev, bundle


@pytest.mark.parametrize("token", ["", "wrong", None])
def test_auth_denials_skip_repository_reads(seeded_client, token) -> None:
    client, repo, _rev, bundle = seeded_client
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/v1/fictional-time-shadow-queries",
        json=_body(bundle, _gold_queries()[0]),
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "capability_denied"
    assert repo.get_revision_calls == 0


def test_four_gold_queries_return_pinned_shadow_results(seeded_client) -> None:
    client, _repo, rev, bundle = seeded_client
    checks = [
        {"status": "entailed", "value": True, "proof_claim_ids": [
            "claim:hempholm-tree-before-revelry", "claim:hempholm-revelry-before-beetles",
        ]},
        {"status": "unresolved", "reason": "no_explicit_absolute_anchor"},
        {"value": False, "proof_claim_ids": [BOUNDARY]},
        {"value": True, "proof_claim_ids": [BOUNDARY]},
    ]
    for query, check in zip(_gold_queries(), checks, strict=True):
        response = _post(client, _body(bundle, query))
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["authority_mode"] == "shadow"
        assert body["graph_revision_id"] == rev.revision_id
        assert body["graph_payload_sha256"] == rev.graph_payload_sha256
        for key, expected in check.items():
            assert body[key] == expected
        assert SENTINEL not in json.dumps(body)
        assert "Session" not in json.dumps(body)


def test_missing_revision_returns_404_without_result(seeded_client) -> None:
    client, repo, _rev, bundle = seeded_client
    missing = "rev:" + "9" * 32
    body = _body(bundle, _gold_queries()[0])
    body["graph_revision_id"] = missing
    body["claim_bundle"]["graph_revision_id"] = missing
    response = _post(client, body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "revision_not_found"
    assert "status" not in response.json()
    assert repo.get_revision_calls == 1


def test_integrity_conflict_returns_409(seeded_client) -> None:
    repo = _TamperedRepo(InMemoryWorldGraphRepository())
    _rev, bundle = _seed(repo.inner)
    with TestClient(_app(repo)) as client:
        response = _post(client, _body(bundle, _gold_queries()[0]))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fictional_time_integrity_error"


def test_malformed_json_and_invalid_nested_return_sanitized_422(seeded_client) -> None:
    client, _repo, _rev, bundle = seeded_client
    bad_json = client.post(
        "/v1/fictional-time-shadow-queries",
        content=b"{",
        headers={"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"},
    )
    assert bad_json.status_code == 422
    nested = _body(bundle, _gold_queries()[0])
    nested["query"]["state_id"] = None
    invalid = _post(client, nested)
    assert invalid.status_code == 422
    for response in (bad_json, invalid):
        errors = response.json()["error"]["details"]["errors"]
        for error in errors:
            assert "input" not in error and "ctx" not in error and "url" not in error


def test_unexpected_exception_returns_empty_details(seeded_client, monkeypatch) -> None:
    _client, repo, _rev, bundle = seeded_client

    def boom(*_args, **_kwargs):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(
        "dungeonmind.service.api.query_fictional_time_shadow_at_revision",
        boom,
    )
    with TestClient(_app(repo), raise_server_exceptions=False) as client:
        response = _post(client, _body(bundle, _gold_queries()[0]))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["details"] == {}


def test_no_cors_headers_on_post_or_preflight(seeded_client) -> None:
    client, _repo, _rev, bundle = seeded_client
    preflight = client.options(
        "/v1/fictional-time-shadow-queries",
        headers={
            "Origin": "https://arbitrary.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    response = _post(client, _body(bundle, _gold_queries()[0]))
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in response.headers


def test_readyz_returns_ready_schemas(seeded_client) -> None:
    client, _repo, _rev, _bundle = seeded_client
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "world_id": WORLD,
        "request_schema": FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA,
        "result_schema": "dm_fictional_time_query_result_v1",
    }


def test_readiness_probe_missing_table_and_db_error() -> None:
    class _Row:
        def __init__(self, ok):
            self._ok = ok

        def fetchone(self):
            return self._ok

    class _Conn:
        def __init__(self, row):
            self._row = row

        def execute(self, sql, params=()):
            if "information_schema" in sql:
                return _Row(self._row)
            return _Row({"ok": 1})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Db:
        def __init__(self, *, row=None, fail=False):
            self._row = row
            self._fail = fail

        def connect(self):
            if self._fail:
                raise OSError("down")
            return _Conn(self._row)

    class _Bundle:
        def __init__(self, database):
            self.database = database

    with pytest.raises(PersistenceIntegrityError):
        build_fictional_time_readiness_probe(
            bundle=_Bundle(_Db(row=None)), world_id=WORLD
        )()
    with pytest.raises(PersistenceUnavailableError):
        build_fictional_time_readiness_probe(
            bundle=_Bundle(_Db(fail=True)), world_id=WORLD
        )()


def test_static_source_guard_has_no_head_publish_or_agent() -> None:
    files = (
        "contracts/fictional_time_transport.py",
        "application/fictional_time_query_service.py",
        "service/fictional_time_access.py",
    )
    forbidden = ("get_head", "publish_revision", "rollback_head", "openai", "agent_adapter")
    for rel in files:
        text = (ROOT / rel).read_text()
        for token in forbidden:
            assert token not in text, f"{rel} contains {token}"


def test_identical_posts_are_byte_equivalent(seeded_client) -> None:
    client, _repo, _rev, bundle = seeded_client
    body = _body(bundle, _gold_queries()[0])
    first = _post(client, body)
    second = _post(client, body)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content


def test_sentinel_missing_object_integrity_is_sanitized(seeded_client) -> None:
    repo = _CountingRepo(InMemoryWorldGraphRepository())
    rev, bundle = _seed(repo.inner)
    payload = copy.deepcopy(
        StoredGraphRevision.model_validate(
            json.loads((FIX / "ft1-two-case-graph-v1.json").read_text())
        ).graph_payload
    )
    payload["nodes"] = [n for n in payload["nodes"] if n["object_id"] != "obj:mireward-gate"]
    mutated = repo.inner.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD,
            parent_revision_id=rev.revision_id,
            expected_parent_revision_id=rev.revision_id,
            operation_ids=["op:ft1-missing-gate"],
            graph_schema=rev.graph_schema,
            graph_payload=payload,
            created_at=LATER,
        )
    )
    bad_bundle = bundle.model_copy(
        update={
            "graph_revision_id": mutated.revision_id,
            "graph_payload_sha256": mutated.graph_payload_sha256,
        }
    )
    with TestClient(_app(repo)) as client:
        response = _post(client, _body(bad_bundle, _gold_queries()[0]))
    assert response.status_code == 409
    blob = json.dumps(response.json())
    assert SENTINEL not in blob
    assert "Session" not in blob
    assert response.json()["error"]["details"].get("reason") == "anchor_object_not_found"
