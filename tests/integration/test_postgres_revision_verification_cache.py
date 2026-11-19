"""Fresh PostgreSQL source authority precedes every exact proof reuse."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresDatabase
from dungeonmind.infrastructure.postgres import vnext_knowledge as k
from dungeonmind.infrastructure.postgres.database import jsonb
from tests.unit.test_vnext_cas_publication import NOW, SPACE, genesis_command

pytestmark = pytest.mark.integration


def _setup(dsn, payload=None):
    db = PostgresDatabase(dsn)
    ordinary = k.PostgresKnowledgeRevisionRepository(db)
    stored = ordinary.publish_revision(genesis_command(origin=None, payload=payload))
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=10_000_000)
    cached = k.PostgresKnowledgeRevisionRepository(db, verification_cache=cache)
    assert cached.get_revision(SPACE, stored.revision.revision_id) == stored
    return db, ordinary, cached, cache, stored


@pytest.mark.parametrize(
    "column",
    [
        "parent_revision_id",
        "created_at",
        "graph_schema",
        "graph_payload_sha256",
        "schema_version",
        "record_fingerprint",
        "revision_payload",
        "graph_payload",
    ],
)
def test_every_mutable_source_field_rechecked_before_cached_return(migrated_database, pg, column):
    del pg
    db, ordinary, cached, cache, stored = _setup(migrated_database)
    value = {
        "parent_revision_id": stored.revision.revision_id,
        "created_at": NOW + timedelta(seconds=1),
        "graph_schema": "forged",
        "graph_payload_sha256": "00" * 32,
        "schema_version": "forged",
        "record_fingerprint": "00" * 32,
        "revision_payload": jsonb({**stored.revision.model_dump(mode="json"), "unknown": True}),
        "graph_payload": jsonb({"changed": True}),
    }[column]
    with db.transaction() as conn:
        conn.execute(
            sql.SQL(
                "UPDATE dungeonmind.knowledge_revisions SET {}=%s "
                "WHERE space_id=%s AND revision_id=%s"
            ).format(sql.Identifier(column)),
            (value, SPACE, stored.revision.revision_id),
        )
    previous_bytes = cache.retained_bytes
    with pytest.raises(PersistenceIntegrityError) as expected:
        ordinary.get_revision(SPACE, stored.revision.revision_id)
    with pytest.raises(PersistenceIntegrityError) as actual:
        cached.get_revision(SPACE, stored.revision.revision_id)
    assert str(actual.value) == str(expected.value)
    assert cache.retained_bytes == previous_bytes


@pytest.mark.parametrize("column", ["space_id", "revision_id"])
def test_identity_movement_cannot_return_stale_source(migrated_database, pg, column):
    del pg
    db, ordinary, cached, _cache, stored = _setup(migrated_database)
    with db.transaction() as conn:
        # Remove derived dependents before deliberately corrupting source identity.
        conn.execute(
            "DELETE FROM dungeonmind.knowledge_native_read_artifacts "
            "WHERE space_id=%s AND revision_id=%s",
            (SPACE, stored.revision.revision_id),
        )
        conn.execute("DELETE FROM dungeonmind.knowledge_head_events WHERE space_id=%s", (SPACE,))
        conn.execute("DELETE FROM dungeonmind.knowledge_heads WHERE space_id=%s", (SPACE,))
        if column == "space_id":
            conn.execute(
                "INSERT INTO dungeonmind.knowledge_spaces VALUES (%s,%s)", ("space:moved", NOW)
            )
        value = "space:moved" if column == "space_id" else "rev:moved"
        conn.execute(
            sql.SQL(
                "UPDATE dungeonmind.knowledge_revisions SET {}=%s "
                "WHERE space_id=%s AND revision_id=%s"
            ).format(sql.Identifier(column)),
            (value, SPACE, stored.revision.revision_id),
        )
    assert cached.get_revision(SPACE, stored.revision.revision_id) is None
    args = (value, stored.revision.revision_id) if column == "space_id" else (SPACE, value)
    with pytest.raises(PersistenceIntegrityError):
        ordinary.get_revision(*args)
    with pytest.raises(PersistenceIntegrityError):
        cached.get_revision(*args)


def test_self_consistent_payload_hash_fingerprint_cannot_forge_revision_identity(
    migrated_database, pg
):
    del pg
    db, ordinary, cached, _cache, stored = _setup(migrated_database)
    payload = {"changed": True}
    envelope = stored.revision.model_dump(mode="json")
    envelope["graph_payload_sha256"] = canonical_sha256(payload)
    fingerprint = canonical_sha256({"graph_payload": payload, "revision": envelope})
    with db.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_revisions SET graph_payload=%s, "
            "revision_payload=%s, graph_payload_sha256=%s, record_fingerprint=%s "
            "WHERE space_id=%s AND revision_id=%s",
            (
                jsonb(payload),
                jsonb(envelope),
                envelope["graph_payload_sha256"],
                fingerprint,
                SPACE,
                stored.revision.revision_id,
            ),
        )
    for reader in (ordinary, cached):
        with pytest.raises(PersistenceIntegrityError, match="recomputed native revision id"):
            reader.get_revision(SPACE, stored.revision.revision_id)


def test_current_historical_and_read_only_ephemeral_readers(migrated_database, pg):
    del pg
    _db, ordinary, _cached, cache, first = _setup(migrated_database, {"value": 1})
    second = ordinary.publish_revision(
        genesis_command(
            origin=None,
            payload={"value": 1.0},
            parent_revision_id=first.revision.revision_id,
            expected_parent_revision_id=first.revision.revision_id,
            operation_ids=["op:second"],
        )
    )
    dsn = make_conninfo(migrated_database, options="-c default_transaction_read_only=on")
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        for expected in (first, second, first):
            for _ in range(2):
                reader = k.PostgresKnowledgeRevisionRepository(
                    PostgresDatabase(dsn), verification_cache=cache
                )
                actual = reader.get_revision(SPACE, expected.revision.revision_id)
                assert actual == expected
                actual.revision.domain_contract_ref.domain_id = "caller mutation"
        assert reconstruct.call_count == 2  # First was cached by _setup.


def test_missing_row_does_not_reuse_a_verified_proof(migrated_database, pg):
    del pg
    db, _ordinary, cached, _cache, stored = _setup(migrated_database)
    with db.transaction() as conn:
        # Remove derived dependents before deliberately corrupting source identity.
        conn.execute(
            "DELETE FROM dungeonmind.knowledge_native_read_artifacts "
            "WHERE space_id=%s AND revision_id=%s",
            (SPACE, stored.revision.revision_id),
        )
        conn.execute("DELETE FROM dungeonmind.knowledge_head_events WHERE space_id=%s", (SPACE,))
        conn.execute("DELETE FROM dungeonmind.knowledge_heads WHERE space_id=%s", (SPACE,))
        conn.execute("DELETE FROM dungeonmind.knowledge_revisions WHERE space_id=%s", (SPACE,))
    assert cached.get_revision(SPACE, stored.revision.revision_id) is None
