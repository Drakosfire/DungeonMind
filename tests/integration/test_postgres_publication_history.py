"""Fresh native discovery after real publication, without an original plan."""

import pytest

from dungeonmind.application import discover_review_publications
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle
from tests.integration import test_postgres_review_publication as f

pytestmark = pytest.mark.integration


def _read(bundle, state, pin, **overrides):
    arguments = dict(
        world_id=f.WORLD_ID, revision_id=pin,
        reviewer_id=state.record.reviewer_id,
        source_plan_schema=state.record.plan_ref.source_plan_schema,
        world_graph_repository=bundle.world_graph,
        publication_repository=bundle.finalized_review_publications,
        review_repository=bundle.contribution_reviews,
    )
    arguments.update(overrides)
    return discover_review_publications(**arguments)


def test_fresh_postgres_discovery_is_complete_and_read_only(pg, monkeypatch):
    state = f._seed_tripod(pg)
    receipt = f._publish(pg, f._reader())
    descendant = f._publish_descendant(pg, receipt.published_revision_id)
    before_events = f._head_event_count(pg)
    before_publications = f._publication_count(pg)
    fresh = PostgresRepositoryBundle(pg.database)

    def forbidden(*args, **kwargs):
        raise AssertionError("discovery must not publish, finalize or replace its pin")

    for owner, method in (
        (fresh.world_graph, "get_head"), (fresh.world_graph, "publish_revision"),
        (fresh.finalized_review_publications, "publish"),
        (fresh.contribution_reviews, "finalize"),
    ):
        monkeypatch.setattr(owner, method, forbidden)
    found = _read(fresh, state, descendant.revision.revision_id)
    assert found.scanned_revision_count == 3
    assert len(found.publications) == 1
    assert found.publications[0].publication == receipt
    assert found.publications[0].review == state
    assert _read(fresh, state, f.PARENT_REVISION_ID).publications == ()
    assert _read(fresh, state, descendant.revision.revision_id,
                 reviewer_id="other-run").publications == ()
    assert _read(fresh, state, descendant.revision.revision_id,
                 source_plan_schema="other-family").publications == ()
    assert f._head_event_count(pg) == before_events
    assert f._publication_count(pg) == before_publications


@pytest.mark.parametrize("table", ["contribution_reviews", "finalized_review_publications"])
def test_corrupt_postgres_record_cannot_look_like_zero_coverage(pg, table):
    state = f._seed_tripod(pg)
    receipt = f._publish(pg, f._reader())
    # Only this disposable fixture database is damaged. Repository reconstruction
    # must reject the fingerprint before returning even an unmatched selection.
    with pg.database.connect() as connection:
        connection.execute(
            f"UPDATE dungeonmind.{table} SET record_fingerprint = %s WHERE world_id = %s",
            ("0" * 64, f.WORLD_ID),
        )
        connection.commit()
    fresh = PostgresRepositoryBundle(pg.database)
    with pytest.raises(PersistenceIntegrityError):
        _read(fresh, state, receipt.published_revision_id, reviewer_id="other-run")
