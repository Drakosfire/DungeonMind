"""One-statement metadata read of native campaign membership and graph head."""

from psycopg import sql
from pydantic import ValidationError

from ...application.world_campaign_ingest_context import (
    WorldCampaignMembershipNotFoundError,
    WorldGraphNotInitializedError,
)
from ...contracts.graph import GRAPH_HEAD_SCHEMA, GRAPH_REVISION_SCHEMA
from ...contracts.world_campaign_ingest_context import WorldCampaignIngestContextV1
from ...domain.errors import PersistenceIntegrityError
from .database import SCHEMA, PostgresDatabase


class PostgresWorldCampaignIngestContextReader:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def read_ingest_context(
        self, *, world_id: str, campaign_id: str
    ) -> WorldCampaignIngestContextV1:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT c.world_id, c.campaign_id, h.head_revision_id,
                           h.schema_version AS head_schema_version,
                           r.revision_id, r.schema_version AS revision_schema_version,
                           r.graph_schema, r.graph_payload_sha256
                    FROM {schema}.campaigns c
                    LEFT JOIN {schema}.world_graph_heads h ON h.world_id = c.world_id
                    LEFT JOIN {schema}.graph_revisions r
                      ON r.world_id = h.world_id AND r.revision_id = h.head_revision_id
                    WHERE c.world_id = %s AND c.campaign_id = %s
                    """
                ).format(schema=sql.Identifier(SCHEMA)),
                (world_id, campaign_id),
            ).fetchone()
        if row is None:
            raise WorldCampaignMembershipNotFoundError()
        if row["head_revision_id"] is None:
            raise WorldGraphNotInitializedError()
        if (
            row["head_schema_version"] != GRAPH_HEAD_SCHEMA
            or row["revision_schema_version"] != GRAPH_REVISION_SCHEMA
            or row["revision_id"] != row["head_revision_id"]
        ):
            raise PersistenceIntegrityError("ingest context head/revision metadata is inconsistent")
        try:
            return WorldCampaignIngestContextV1(
                world_id=row["world_id"], campaign_id=row["campaign_id"],
                head_revision_id=row["head_revision_id"], graph_schema=row["graph_schema"],
                graph_payload_sha256=row["graph_payload_sha256"],
            )
        except ValidationError:
            raise PersistenceIntegrityError("ingest context metadata failed validation") from None
