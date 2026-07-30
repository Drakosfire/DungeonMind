"""PostgreSQL world-graph CAS, audit events, restart, and failure injection."""

from __future__ import annotations

import pytest

from tests.conftest import FIXED_LATER, FIXED_NOW, WORLD_ID, make_publish


@pytest.mark.integration
def test_genesis_publish_chain_and_stale_parent(pg) -> None:
    from dungeonmind.domain.errors import StaleParentRevisionError

    repo = pg.world_graph
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    rev2 = repo.publish_revision(
        make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    )
    assert repo.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]

    with pytest.raises(StaleParentRevisionError):
        repo.publish_revision(make_publish(parent=None, expected=None, payload={"v": 3}))
    assert repo.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]
    assert repo.get_revision(WORLD_ID, rev1.revision_id) is not None


@pytest.mark.integration
def test_rollback_keeps_revisions_and_writes_audit_events(pg, db) -> None:
    repo = pg.world_graph
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    rev2 = repo.publish_revision(
        make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    )
    repo.rollback_head(WORLD_ID, rev1.revision_id, updated_at=FIXED_LATER)
    assert repo.get_head(WORLD_ID).head_revision_id == rev1.revision_id  # type: ignore[union-attr]
    assert repo.get_revision(WORLD_ID, rev2.revision_id) is not None

    with db.connect() as conn:
        events = conn.execute(
            """
            SELECT event_kind, previous_revision_id, target_revision_id
            FROM dungeonmind.world_graph_head_events
            WHERE world_id = %s
            ORDER BY event_id
            """,
            (WORLD_ID,),
        ).fetchall()
    kinds = [e["event_kind"] for e in events]
    assert kinds == ["publish", "publish", "rollback"]
    assert events[-1]["previous_revision_id"] == rev2.revision_id
    assert events[-1]["target_revision_id"] == rev1.revision_id


@pytest.mark.integration
def test_restart_rereads_head(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresWorldGraphRepository,
    )

    first = PostgresWorldGraphRepository(PostgresDatabase(migrated_database))
    rev = first.publish_revision(make_publish(payload={"persist": True}))

    second = PostgresWorldGraphRepository(PostgresDatabase(migrated_database))
    head = second.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == rev.revision_id
    stored = second.get_revision(WORLD_ID, rev.revision_id)
    assert stored is not None
    assert stored.graph_payload == {"persist": True}


@pytest.mark.integration
def test_unavailable_database_maps_to_persistence_error() -> None:
    from dungeonmind.domain.errors import PersistenceUnavailableError
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresWorldGraphRepository,
    )

    repo = PostgresWorldGraphRepository(
        PostgresDatabase("postgresql://dungeonmind:bad@127.0.0.1:1/dungeonmind")
    )
    with pytest.raises(PersistenceUnavailableError):
        repo.get_head(WORLD_ID)


@pytest.mark.integration
def test_head_schema_version_drift_fails_closed(migrated_database: str, pg) -> None:
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    repo = pg.world_graph
    repo.publish_revision(make_publish(payload={"v": 1}))
    db = PostgresDatabase(migrated_database)
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.world_graph_heads SET schema_version = %s "
            "WHERE world_id = %s",
            ("dm_graph_head_corrupt", WORLD_ID),
        )
    with pytest.raises(PersistenceIntegrityError, match="schema_version"):
        repo.get_head(WORLD_ID)


@pytest.mark.integration
def test_revision_extracted_column_drift_fails_closed(
    migrated_database: str, pg
) -> None:
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    repo = pg.world_graph
    rev = repo.publish_revision(make_publish(payload={"v": 1}))
    db = PostgresDatabase(migrated_database)
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.graph_revisions SET graph_payload_sha256 = %s "
            "WHERE world_id = %s AND revision_id = %s",
            ("deadbeef" * 8, WORLD_ID, rev.revision_id),
        )
    with pytest.raises(PersistenceIntegrityError, match="graph_payload_sha256"):
        repo.get_revision(WORLD_ID, rev.revision_id)


@pytest.mark.integration
def test_failed_publish_via_trigger_leaves_prior_head(pg, db) -> None:
    repo = pg.world_graph
    fail_world = "world:fail"
    good = repo.publish_revision(
        make_publish(world_id=fail_world, payload={"ok": 1}, created_at=FIXED_NOW)
    )
    assert repo.get_head(fail_world).head_revision_id == good.revision_id  # type: ignore[union-attr]

    with db.connect() as conn:
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION dungeonmind.abort_fail_world_publish()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.world_id = 'world:fail' AND NEW.event_kind = 'publish' THEN
                    RAISE EXCEPTION 'injected publish failure for world:fail';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        conn.execute(
            """
            DROP TRIGGER IF EXISTS abort_fail_world_publish
            ON dungeonmind.world_graph_head_events
            """
        )
        conn.execute(
            """
            CREATE TRIGGER abort_fail_world_publish
            BEFORE INSERT ON dungeonmind.world_graph_head_events
            FOR EACH ROW
            EXECUTE FUNCTION dungeonmind.abort_fail_world_publish()
            """
        )
        conn.commit()

    try:
        from dungeonmind.domain.errors import PersistenceIntegrityError

        with pytest.raises(PersistenceIntegrityError):
            repo.publish_revision(
                make_publish(
                    world_id=fail_world,
                    parent=good.revision_id,
                    payload={"ok": 2},
                    created_at=FIXED_LATER,
                )
            )
        head = repo.get_head(fail_world)
        assert head is not None
        assert head.head_revision_id == good.revision_id
        assert repo.get_revision(fail_world, good.revision_id) is not None
    finally:
        with db.connect() as conn:
            conn.execute(
                """
                DROP TRIGGER IF EXISTS abort_fail_world_publish
                ON dungeonmind.world_graph_head_events
                """
            )
            conn.execute(
                "DROP FUNCTION IF EXISTS dungeonmind.abort_fail_world_publish()"
            )
            conn.commit()
