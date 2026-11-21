"""PostgreSQL activation is atomic, exact-pin and concurrent-safe."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import sql

from dungeonmind.application.vnext._selective_read_proof import open_selective_read_proof
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.selective_read_projection import (
    publish_selective_read_projection,
)
from dungeonmind.infrastructure.postgres.vnext_knowledge import PostgresKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import SPACE, genesis_command

pytestmark = pytest.mark.integration
_TABLES = (
    "selective_read_activations",
    "selective_read_proofs",
    "selective_read_records",
    "selective_read_buckets",
)


def _counts(database):
    with database.transaction() as connection:
        return [
            connection.execute(
                sql.SQL("SELECT count(*) AS n FROM dungeonmind.{}").format(sql.Identifier(table))
            ).fetchone()["n"]
            for table in _TABLES
        ]


def test_concurrent_projection_publication_and_replay(pg, migrated_database):
    database = PostgresDatabase(migrated_database)
    repo = PostgresKnowledgeRevisionRepository(database)
    stored = repo.publish_revision(genesis_command())
    pin = dict(space_id=SPACE, revision_id=stored.revision.revision_id)

    def publish():
        return publish_selective_read_projection(database, **pin)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(publish)
        second = executor.submit(publish)
        digest = first.result(timeout=10)
        assert second.result(timeout=10) == digest
    counts = _counts(database)
    assert counts[:2] == [1, 1] and all(n > 0 for n in counts)
    assert publish() == digest
    assert _counts(database) == counts
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT a.proof_sha256,p.content FROM dungeonmind.selective_read_activations a "
            "JOIN dungeonmind.selective_read_proofs p USING(space_id, revision_id)"
        ).fetchone()
    assert row["proof_sha256"] == digest
    open_selective_read_proof(
        bytes(row["content"]), expected_sha256=digest, revision=stored.revision
    )
    assert repo.get_head(SPACE).head_revision_id == stored.revision.revision_id
    assert len(repo.head_events(SPACE)) == 1


def test_activation_and_all_projection_rows_roll_back_on_bucket_failure(pg, migrated_database):
    database = PostgresDatabase(migrated_database)
    repo = PostgresKnowledgeRevisionRepository(database)
    stored = repo.publish_revision(genesis_command())
    with database.transaction() as connection:
        connection.execute(
            "ALTER TABLE dungeonmind.selective_read_buckets ADD CONSTRAINT force_bucket_failure "
            "CHECK (false)"
        )
    try:
        with pytest.raises(PersistenceIntegrityError, match="force_bucket_failure"):
            publish_selective_read_projection(
                database,
                space_id=SPACE,
                revision_id=stored.revision.revision_id,
            )
        assert _counts(database) == [0, 0, 0, 0]
        assert repo.get_head(SPACE).head_revision_id == stored.revision.revision_id
    finally:
        with database.transaction() as connection:
            connection.execute(
                "ALTER TABLE dungeonmind.selective_read_buckets "
                "DROP CONSTRAINT force_bucket_failure"
            )


def test_published_projection_rejects_activation_anchor_drift(pg, migrated_database):
    database = PostgresDatabase(migrated_database)
    repo = PostgresKnowledgeRevisionRepository(database)
    stored = repo.publish_revision(genesis_command())
    pin = dict(space_id=SPACE, revision_id=stored.revision.revision_id)
    publish_selective_read_projection(database, **pin)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE dungeonmind.selective_read_activations SET source_sql_sha256 = %s",
            ("0" * 64,),
        )
    with pytest.raises(PersistenceIntegrityError, match="activation drift"):
        publish_selective_read_projection(database, **pin)
