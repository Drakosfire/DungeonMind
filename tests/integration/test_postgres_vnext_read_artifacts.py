"""Derived artifacts are transactional hints, never new primary authority."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from dungeonmind.application.vnext._read_artifact import decode_read_artifact
from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import vnext_read_artifacts as artifacts
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.vnext_knowledge import PostgresKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import SPACE, genesis_command

pytestmark = pytest.mark.integration


def _repo(dsn):
    return PostgresKnowledgeRevisionRepository(PostgresDatabase(dsn))


def _count(dsn, table):
    from psycopg import sql

    with PostgresDatabase(dsn).connect() as conn:
        return conn.execute(
            sql.SQL("SELECT count(*) AS n FROM dungeonmind.{}").format(sql.Identifier(table))
        ).fetchone()["n"]


def test_publication_generates_byte_exact_artifact_and_replay_adds_no_work(
    migrated_database, pg, monkeypatch
):
    repo = _repo(migrated_database)
    command = genesis_command()
    receipt = repo.publish_publication(command, "publication:artifact-replay")
    stored = repo.get_revision(SPACE, receipt.published_revision_id)
    body = repo.get_native_read_artifact(repo.get_revision(SPACE, stored.revision.revision_id))
    assert decode_read_artifact(body, stored)
    assert _count(migrated_database, "knowledge_native_read_artifacts") == 1

    def forbidden(*args, **kwargs):
        pytest.fail("replay generated artifact")

    monkeypatch.setattr(artifacts, "_generate", forbidden)
    assert repo.publish_publication(command, "publication:artifact-replay") == receipt


@pytest.mark.parametrize("failure", ["generation", "after_insert"])
def test_failure_rolls_back_revision_artifact_head_and_event(
    migrated_database, pg, monkeypatch, failure
):
    def boom(*args, **kwargs):
        raise RuntimeError("artifact injection")

    if failure == "generation":
        monkeypatch.setattr(artifacts, "_generate", boom)
    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database),
        after_revision_insert=boom if failure == "after_insert" else None,
    )
    with pytest.raises(RuntimeError, match="artifact injection"):
        repo.publish_revision(genesis_command())
    for table in (
        "knowledge_revisions",
        "knowledge_native_read_artifacts",
        "knowledge_heads",
        "knowledge_head_events",
    ):
        assert _count(migrated_database, table) == 0


def test_opaque_native_publication_remains_accepted_without_artifact(migrated_database, pg):
    repo = _repo(migrated_database)
    payload = genesis_command().graph_payload
    payload["assertions"][0]["metadata"]["standing"] = "opaque"
    stored = repo.publish_revision(genesis_command(payload=payload))
    assert repo.get_head(SPACE).head_revision_id == stored.revision.revision_id
    assert repo.get_native_read_artifact(stored) is None
    assert not repo.backfill_native_read_artifact(SPACE, stored.revision.revision_id)


def test_explicit_backfill_repairs_corrupt_hint_and_preserves_head(migrated_database, pg):
    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    first = repo.get_native_read_artifact(stored)
    head = repo.get_head(SPACE)
    events = repo.head_events(SPACE)
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_read_artifacts SET artifact_sha256=%s", ("0" * 64,)
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="checksum"):
        repo.get_native_read_artifact(stored)
    assert repo.backfill_native_read_artifact(SPACE, stored.revision.revision_id)
    assert repo.get_native_read_artifact(stored) == first
    assert repo.get_head(SPACE) == head and repo.head_events(SPACE) == events
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert all(
            pool.map(
                lambda _: _repo(migrated_database).backfill_native_read_artifact(
                    SPACE, stored.revision.revision_id
                ),
                range(3),
            )
        )
    assert _count(migrated_database, "knowledge_native_read_artifacts") == 1


def test_oversized_blob_not_transferred_to_client(migrated_database, pg):
    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    body = b"x" * (8 * len(stored._payload_json.encode()) + 4097)
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_read_artifacts "
            "SET artifact_bytes=%s, artifact_length=%s, artifact_sha256=%s",
            (body, len(body), hashlib.sha256(body).hexdigest()),
        )
        conn.commit()
    rows = []
    with PostgresDatabase(migrated_database).connect() as conn:

        class Proxy:
            def execute(self, *args, **kwargs):
                cursor = conn.execute(*args, **kwargs)

                class Cursor:
                    def fetchone(self):
                        row = cursor.fetchone()
                        rows.append(row)
                        return row

                return Cursor()

        with pytest.raises(PersistenceIntegrityError, match="length"):
            artifacts._read_artifact(Proxy(), stored)
    assert rows[0]["body"] is None


def test_recomputed_blob_checksum_cannot_forge_source(migrated_database, pg):
    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    packet = json.loads(repo.get_native_read_artifact(stored))
    index = packet["entities"][0]
    text = packet["strings"][index]
    packet["strings"][index] = text[:-1] + "x"
    body = canonical_json(packet).encode()
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_read_artifacts "
            "SET artifact_bytes=%s,artifact_length=%s,artifact_sha256=%s",
            (body, len(body), hashlib.sha256(body).hexdigest()),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError):
        decode_read_artifact(repo.get_native_read_artifact(stored), stored)


def test_readonly_transaction_can_read_verified_artifact(migrated_database, pg):
    from dungeonmind.infrastructure.postgres.vnext_knowledge import _read_revision

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        verified = _read_revision(conn, SPACE, stored.revision.revision_id)
        assert decode_read_artifact(artifacts._read_artifact(conn, verified), verified)


@pytest.mark.parametrize("failure", ["sql", "after_receipt"])
def test_receipt_publication_rolls_back_complete_artifact_unit(
    migrated_database,
    pg,
    monkeypatch,
    failure,
):
    def boom():
        raise RuntimeError("receipt failure")

    if failure == "sql":
        monkeypatch.setattr(artifacts, "_generate", lambda stored: b"")
    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database),
        after_receipt_insert=boom if failure == "after_receipt" else None,
    )
    expected = PersistenceIntegrityError if failure == "sql" else RuntimeError
    with pytest.raises(expected):
        repo.publish_publication(genesis_command(), "publication:rollback")
    for table in (
        "knowledge_revisions",
        "knowledge_native_read_artifacts",
        "knowledge_heads",
        "knowledge_head_events",
        "knowledge_publication_receipts",
        "knowledge_prospective_publication_results",
    ):
        assert _count(migrated_database, table) == 0


def test_select_only_role_consumes_artifact_without_write_privilege(migrated_database, pg):
    from uuid import uuid4

    from psycopg import sql

    from dungeonmind.infrastructure.postgres.vnext_knowledge import _read_revision

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    role = "artifact_reader_" + uuid4().hex[:12]
    with PostgresDatabase(migrated_database).connect() as conn:
        try:
            # Transactional role/grants disappear on rollback; nothing persists
            # in this cluster's role catalog or any serving database.
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA dungeonmind TO {}").format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA dungeonmind TO {}").format(
                    sql.Identifier(role)
                )
            )
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            assert conn.execute("SELECT current_user AS name").fetchone()["name"] == role
            assert not conn.execute(
                "SELECT has_table_privilege(current_user, "
                "'dungeonmind.knowledge_native_read_artifacts', 'INSERT') AS allowed"
            ).fetchone()["allowed"]
            verified = _read_revision(conn, SPACE, stored.revision.revision_id)
            assert decode_read_artifact(artifacts._read_artifact(conn, verified), verified)
        finally:
            conn.rollback()
        assert (
            conn.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[
                "n"
            ]
            == 0
        )


def test_postgres_artifact_memory_hit_refreshes_withdrawal_and_source_verification(pg, monkeypatch):
    from dungeonmind.application.vnext import publish_native_text_source_evidence
    from dungeonmind.application.vnext.native_source_access import (
        NativeParsedRevisionCache,
        open_admitted_native_text,
        open_native_text_source_access_context,
    )
    from tests.integration.test_postgres_vnext_native_source_admission import _init, _repository
    from tests.unit.test_vnext_native_source_admission import _request

    repo = _repository(pg)
    domain, profile, genesis = _init(repo)
    request = _request(space_id=genesis.space_id, parent_revision_id=genesis.published_revision_id)
    receipt = publish_native_text_source_evidence(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile
    )
    args = dict(
        repository=repo,
        space_id=receipt.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
        parsed_cache=NativeParsedRevisionCache(),
    )
    first = open_native_text_source_access_context(**args)
    repo.withdraw_native_source(
        space_id=receipt.space_id,
        source_artifact_id=receipt.source_artifact_id,
        source_revision_id=receipt.source_revision_id,
    )
    second = open_native_text_source_access_context(**args)
    assert second.parsed is first.parsed
    evidence = receipt.bindings[0].evidence_ref_id
    assert open_admitted_native_text(first, evidence).status == "available"
    assert open_admitted_native_text(second, evidence).status == "unavailable"
    with pg.database.connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_revisions SET record_fingerprint=%s "
            "WHERE space_id=%s AND revision_id=%s",
            ("0" * 64, receipt.space_id, receipt.published_revision_id),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="fingerprint"):
        open_native_text_source_access_context(**args)
