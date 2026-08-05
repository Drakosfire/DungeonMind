"""FT1b Postgres integration: pinned R1 survives R2 head and restart."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dungeonmind.application.fictional_time_query_service import (
    query_fictional_time_shadow_at_revision,
)
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.contracts.fictional_time import (
    FICTIONAL_TIME_QUERY_SCHEMA,
    FictionalTimeClaimBundle,
    FictionalTimeQuery,
)
from dungeonmind.contracts.fictional_time_transport import FictionalTimeShadowQueryRequest
from dungeonmind.contracts.graph import PublishRevisionCommand, StoredGraphRevision
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind.service.api import create_fictional_time_query_app
from dungeonmind.service.bootstrap import build_fictional_time_readiness_probe
from dungeonmind.service.fictional_time_access import FictionalTimeQueryAccessBinding

FIX = Path(__file__).resolve().parents[1] / "fixtures/fictional_time"
WORLD = "world:ft1-fictional-time"
SECRET = "sentinel-fictional-time-bearer"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"
LATER = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)
READER = UnionGraphV1SnapshotReader()

pytestmark = pytest.mark.integration


def _fixture_stored() -> StoredGraphRevision:
    return StoredGraphRevision.model_validate(
        json.loads((FIX / "ft1-two-case-graph-v1.json").read_text())
    )


def _fixture_bundle() -> FictionalTimeClaimBundle:
    return FictionalTimeClaimBundle.model_validate(
        json.loads((FIX / "ft1-two-case-claim-bundle-v1.json").read_text())
    )


def _query() -> FictionalTimeQuery:
    return FictionalTimeQuery.model_validate(
        {
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:hempholm-tree-before-beetles",
            "query_kind": "strict_before",
            "before_anchor_id": TREE,
            "after_anchor_id": BEETLES,
        }
    )


def _publish_r1(pg) -> StoredGraphRevision:
    stored = _fixture_stored()
    envelope = pg.world_graph.publish_revision(
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
    published = pg.world_graph.get_revision(WORLD, envelope.revision_id)
    assert published is not None
    return published


def _rebind(stored: StoredGraphRevision) -> FictionalTimeClaimBundle:
    rev = stored.revision
    return _fixture_bundle().model_copy(
        update={
            "graph_revision_id": rev.revision_id,
            "graph_payload_sha256": rev.graph_payload_sha256,
        }
    )


def _request(bundle: FictionalTimeClaimBundle) -> FictionalTimeShadowQueryRequest:
    return FictionalTimeShadowQueryRequest(
        world_id=bundle.world_id,
        graph_revision_id=bundle.graph_revision_id,
        claim_bundle=bundle,
        query=_query(),
    )


def _app(pg):
    return create_fictional_time_query_app(
        world_graph_repository=pg.world_graph,
        graph_reader=READER,
        access_binding=FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET),
        readiness_probe=build_fictional_time_readiness_probe(bundle=pg, world_id=WORLD),
    )


def _revision_count(pg, world_id: str = WORLD) -> int:
    with pg.database.connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.graph_revisions
            WHERE world_id = %s
            """,
            (world_id,),
        ).fetchone()
    return int(row["count"])


def test_postgres_pinned_r1_survives_r2_head_and_restart(pg, database_url: str) -> None:
    stored = _publish_r1(pg)
    rev = stored.revision
    bundle = _rebind(stored)
    request = _request(bundle)

    first = query_fictional_time_shadow_at_revision(
        request,
        world_graph_repository=pg.world_graph,
        graph_reader=READER,
    )
    with TestClient(_app(pg)) as client:
        http = client.post(
            "/v1/fictional-time-shadow-queries",
            json=request.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {SECRET}"},
        )
    assert http.status_code == 200
    assert http.json() == first.model_dump(mode="json")

    payload = copy.deepcopy(stored.graph_payload)
    payload["nodes"][0] = {**payload["nodes"][0], "label": "Postgres mutated label"}
    r2 = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD,
            parent_revision_id=rev.revision_id,
            expected_parent_revision_id=rev.revision_id,
            operation_ids=["op:ft1-postgres-mutated"],
            graph_schema=rev.graph_schema,
            graph_payload=payload,
            created_at=LATER,
        )
    )
    assert pg.world_graph.get_head(WORLD).head_revision_id == r2.revision_id

    second = query_fictional_time_shadow_at_revision(
        request,
        world_graph_repository=pg.world_graph,
        graph_reader=READER,
    )
    assert second.model_dump(mode="json") == first.model_dump(mode="json")

    bundle_b = PostgresRepositoryBundle(PostgresDatabase(database_url))
    third = query_fictional_time_shadow_at_revision(
        request,
        world_graph_repository=bundle_b.world_graph,
        graph_reader=READER,
    )
    assert third.model_dump(mode="json") == first.model_dump(mode="json")
    assert _revision_count(pg) == 2
