"""Native PostgreSQL and HTTP proofs for metadata-only recap context reads."""

import json
from contextlib import contextmanager

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.mind_turn import FixedClock
from dungeonmind.application.world_campaign_ingest_context import (
    WorldCampaignMembershipNotFoundError,
    WorldGraphNotInitializedError,
)
from dungeonmind.domain.errors import StaleParentRevisionError
from dungeonmind.infrastructure.postgres.database import ensure_campaign
from dungeonmind.infrastructure.postgres.world_campaign_ingest_context import (
    PostgresWorldCampaignIngestContextReader,
)
from dungeonmind.service.api import create_publication_app
from dungeonmind.service.publication_access import PublicationAccessBinding
from tests.conftest import FIXED_NOW, WORLD_ID, make_publish

pytestmark = pytest.mark.integration
CAMPAIGN = "campaign:synthetic"
HEADERS = {"Authorization": "Bearer synthetic-secret"}


def _seed(pg, *, publish=True):
    with pg.database.transaction() as conn:
        ensure_campaign(conn, WORLD_ID, CAMPAIGN, created_at=FIXED_NOW)
    if publish:
        return pg.world_graph.publish_revision(make_publish(payload={"prose": "synthetic"}))
    return None


def _client(pg, reader=None):
    return TestClient(create_publication_app(
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=pg.finalized_review_publications,
        graph_reader=VersionedUnionGraphSnapshotReader(), clock=FixedClock(FIXED_NOW),
        access_binding=PublicationAccessBinding.from_secret(WORLD_ID, "synthetic-secret"),
        readiness_probe=lambda: {"status": "ready"},
        ingest_context_reader=reader or PostgresWorldCampaignIngestContextReader(pg.database),
    ))


def _url(world=WORLD_ID, campaign=CAMPAIGN):
    return f"/v1/worlds/{world}/campaigns/{campaign}/ingest-context"


def test_http_returns_only_exact_metadata_and_does_not_write(pg) -> None:
    revision = _seed(pg)
    before = pg.world_graph.get_head(WORLD_ID)
    response = _client(pg).get(_url(), headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "schema_version": "dm_world_campaign_ingest_context_v1",
        "world_id": WORLD_ID, "campaign_id": CAMPAIGN, "membership": "member",
        "head_revision_id": revision.revision_id,
        "graph_schema": revision.graph_schema,
        "graph_payload_sha256": revision.graph_payload_sha256,
    }
    assert pg.world_graph.get_head(WORLD_ID) == before
    with pg.database.transaction() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.world_graph_head_events"
        ).fetchone()
    assert row["n"] == 1
    print(json.dumps({
        "witness": "metadata_read", "result": response.json(),
        "head_unchanged": True, "head_events": row["n"],
    }))


def test_missing_membership_and_valid_membership_without_head_fail_closed(pg) -> None:
    reader = PostgresWorldCampaignIngestContextReader(pg.database)
    with pytest.raises(WorldCampaignMembershipNotFoundError):
        reader.read_ingest_context(world_id=WORLD_ID, campaign_id=CAMPAIGN)
    client = _client(pg)
    missing = client.get(_url(), headers=HEADERS)
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
    with pg.database.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM dungeonmind.worlds").fetchone()["n"] == 0
    _seed(pg, publish=False)
    with pytest.raises(WorldCampaignMembershipNotFoundError):
        reader.read_ingest_context(world_id="world:other", campaign_id=CAMPAIGN)
    with pytest.raises(WorldGraphNotInitializedError):
        reader.read_ingest_context(world_id=WORLD_ID, campaign_id=CAMPAIGN)
    response = client.get(_url(), headers=HEADERS)
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "world_graph_not_initialized"
    print(json.dumps({"witness": "fail_closed", "missing_membership": 404, "no_head": 409}))


def test_read_is_one_snapshot_despite_concurrent_membership_and_head_change(pg) -> None:
    first = _seed(pg)
    calls = []
    original_transaction = pg.database.transaction

    def change_state():
        pg.world_graph.publish_revision(make_publish(
            parent=first.revision_id, operation_ids=["op:descendant"], payload={"next": True}
        ))
        with original_transaction() as conn:
            conn.execute(
                "DELETE FROM dungeonmind.campaigns WHERE world_id = %s AND campaign_id = %s",
                (WORLD_ID, CAMPAIGN),
            )

    class InterleavedDatabase:
        @contextmanager
        def transaction(self):
            with original_transaction() as conn:
                class Connection:
                    def execute(self, query, params):
                        calls.append(query.as_string(conn))
                        cursor = conn.execute(query, params)
                        if len(calls) == 1:
                            change_state()
                        return cursor
                yield Connection()

    observed = PostgresWorldCampaignIngestContextReader(InterleavedDatabase()).read_ingest_context(
        world_id=WORLD_ID, campaign_id=CAMPAIGN
    )
    assert len(calls) == 1
    assert observed.head_revision_id == first.revision_id
    assert observed.graph_payload_sha256 == first.graph_payload_sha256
    with pytest.raises(WorldCampaignMembershipNotFoundError):
        PostgresWorldCampaignIngestContextReader(pg.database).read_ingest_context(
            world_id=WORLD_ID, campaign_id=CAMPAIGN
        )
    with pytest.raises(StaleParentRevisionError):
        pg.world_graph.publish_revision(make_publish(parent=observed.head_revision_id))
    print(json.dumps({
        "witness": "consistent_snapshot", "observed": observed.model_dump(),
        "statements": len(calls), "later_membership_missing": True, "stale_cas_rejected": True,
    }))
