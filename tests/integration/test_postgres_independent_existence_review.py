"""Actual native PostgreSQL reconstruction of the explicit V7-capable review family."""

import pytest

from dungeonmind.application.contribution_review_v5 import finalize_contribution_review_v5
from dungeonmind.contracts.contribution_review_v5 import ContributionReviewStateV5
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v5 import setup_case

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("schema", ["dm_union_graph_v6", "dm_union_graph_v7"])
def test_confirmed_v5_review_reconstructs_and_replays_on_real_postgres(
    pg, migrated_database, schema
):
    postgres_dsn = migrated_database
    case = setup_case(schema)
    parent = case[1]
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=parent.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=parent.revision.operation_ids,
            graph_schema=schema,
            graph_payload=parent.graph_payload,
            created_at=parent.revision.created_at,
        )
    )
    snapshot = source_snapshot()
    for source in snapshot.artifacts.values():
        pg.sources.put_artifact(source)
    for revision in snapshot.revisions.values():
        pg.sources.put_revision(revision)

    def finalize():
        return finalize_contribution_review_v5(
            case[4],
            capability_policy=case[5],
            world_graph_repository=pg.world_graph,
            review_repository=pg.contribution_reviews,
        )

    state = finalize()
    assert isinstance(state, ContributionReviewStateV5)
    # A separate repository/connection reconstructs the exact new family.
    fresh = PostgresRepositoryBundle(PostgresDatabase(postgres_dsn))
    assert fresh.contribution_reviews.get(state.record.world_id, state.record.review_id) == state
    assert finalize() == state
    assert (
        fresh.world_graph.get_head(state.record.world_id).head_revision_id
        == parent.revision.revision_id
    )
    with fresh.database.connect() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM dungeonmind.graph_contributions").fetchone()[
                "n"
            ]
            == 2
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM dungeonmind.contribution_reviews").fetchone()[
                "n"
            ]
            == 1
        )
        # Deliberate persisted identity-column corruption must be detected.
        conn.execute(
            "UPDATE dungeonmind.contribution_reviews SET schema_version=%s "
            "WHERE world_id=%s AND review_id=%s",
            ("dm_contribution_review_record_v4", state.record.world_id, state.record.review_id),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError):
        fresh.contribution_reviews.get(state.record.world_id, state.record.review_id)
