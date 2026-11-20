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


@pytest.mark.parametrize("field", ["format", "parsed_format"])
def test_current_row_with_future_body_manifest_fails_closed(migrated_database, pg, field):
    from dungeonmind.application.vnext.native_source_access import _parse_verified_revision

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    packet = json.loads(repo.get_native_read_artifact(stored))
    packet[field] = "future"
    body = canonical_json(packet).encode()
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_read_artifacts "
            "SET artifact_bytes=%s,artifact_length=%s,artifact_sha256=%s",
            (body, len(body), hashlib.sha256(body).hexdigest()),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="format mismatch"):
        _parse_verified_revision(repo, repo.get_revision(SPACE, stored.revision.revision_id))


@pytest.mark.parametrize("field", ["codec_version", "parsed_format"])
def test_genuinely_future_stored_version_is_absent_to_current_reader(migrated_database, pg, field):
    from psycopg import sql

    from dungeonmind.application.vnext.native_source_access import (
        _parse_revision,
        _parse_verified_revision,
    )

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            sql.SQL("UPDATE dungeonmind.knowledge_native_read_artifacts SET {}=%s").format(
                sql.Identifier(field)
            ),
            ("future",),
        )
        conn.commit()
    assert repo.get_native_read_artifact(stored) is None
    assert _parse_verified_revision(repo, stored) == _parse_revision(stored)


def test_backfill_holds_exact_source_lock_until_artifact_write(migrated_database, pg, monkeypatch):
    from threading import Event

    from psycopg.errors import LockNotAvailable

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    entered, release = Event(), Event()
    generate = artifacts._generate

    def blocked(source):
        entered.set()
        assert release.wait(10)
        return generate(source)

    monkeypatch.setattr(artifacts, "_generate", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(repo.backfill_native_read_artifact, SPACE, stored.revision.revision_id)
        try:
            assert entered.wait(10)
            with PostgresDatabase(migrated_database).connect() as conn:
                conn.execute("SET LOCAL lock_timeout = '150ms'")
                with pytest.raises(LockNotAvailable):
                    conn.execute(
                        "UPDATE dungeonmind.knowledge_revisions "
                        "SET revision_payload=revision_payload "
                        "WHERE space_id=%s AND revision_id=%s",
                        (SPACE, stored.revision.revision_id),
                    )
                conn.rollback()
        finally:
            release.set()
        assert future.result(timeout=10)
    assert repo.get_native_read_artifact(stored)


def test_head_advance_does_not_retarget_historical_backfill(migrated_database, pg, monkeypatch):
    from threading import Event

    repo = _repo(migrated_database)
    parent = repo.publish_revision(genesis_command())
    entered, release = Event(), Event()
    generate = artifacts._generate

    def blocked(source):
        if source.revision.revision_id == parent.revision.revision_id:
            entered.set()
            assert release.wait(10)
        return generate(source)

    monkeypatch.setattr(artifacts, "_generate", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(repo.backfill_native_read_artifact, SPACE, parent.revision.revision_id)
        try:
            assert entered.wait(10)
            child = repo.publish_revision(
                genesis_command(
                    parent_revision_id=parent.revision.revision_id,
                    expected_parent_revision_id=parent.revision.revision_id,
                    operation_ids=["op:descendant"],
                )
            )
        finally:
            release.set()
        assert future.result(timeout=10)
    assert repo.get_head(SPACE).head_revision_id == child.revision.revision_id
    for source in (parent, child):
        assert (
            decode_read_artifact(repo.get_native_read_artifact(source), source).revision_id
            == source.revision.revision_id
        )
    assert _count(migrated_database, "knowledge_native_read_artifacts") == 2


def test_prospective_result_failure_rolls_back_child_artifact(migrated_database, pg):
    from dungeonmind.application.vnext.errors import KnowledgePublicationOutcomeUnknownError
    from tests.integration.test_postgres_vnext_prospective_publication import _publish, _setup
    from tests.unit.test_vnext_prospective_publication import _contribution, _entity

    setup, parent = _setup(migrated_database)
    before = setup.get_native_read_artifact(setup.get_revision(SPACE, parent.revision_id))

    def boom():
        raise RuntimeError("prospective result failure")

    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database), after_prospective_result_insert=boom
    )
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        _publish(repo, parent, _contribution([_entity()]), "prepared:artifact-rollback")
    assert _count(migrated_database, "knowledge_native_read_artifacts") == 1
    assert setup.get_native_read_artifact(setup.get_revision(SPACE, parent.revision_id)) == before
    assert setup.get_head(SPACE).head_revision_id == parent.revision_id
    for table in ("knowledge_publication_receipts", "knowledge_prospective_publication_results"):
        assert _count(migrated_database, table) == 0


def test_direct_source_rows_match_artifact_and_reject_changed_primary(migrated_database, pg):
    from dungeonmind.application.vnext._read_artifact import parse_verified_source_rows
    from dungeonmind.infrastructure.postgres.vnext_knowledge import VerifiedKnowledgeRevisionCache

    database = PostgresDatabase(migrated_database)
    reader = PostgresKnowledgeRevisionRepository(
        database, verification_cache=VerifiedKnowledgeRevisionCache(max_bytes=1_000_000),
    )
    stored = reader.publish_revision(genesis_command())
    pin = SPACE, stored.revision.revision_id
    expected = decode_read_artifact(reader.get_native_read_artifact(stored), stored)
    assert expected is not None
    for _ in range(2):
        current, load_rows = reader.get_revision_for_native_read(*pin)
        assert current == stored and load_rows is not None
        assert parse_verified_source_rows(current, load_rows()) == expected

    with database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_revisions "
            "SET graph_payload = jsonb_set(graph_payload, '{unexpected}', 'true') "
            "WHERE space_id = %s AND revision_id = %s",
            pin,
        )
    with pytest.raises(PersistenceIntegrityError):
        reader.get_revision_for_native_read(*pin)


def test_old_valid_source_without_artifact_falls_back_without_read_side_write(
    migrated_database, pg
):
    from dungeonmind.application.vnext.native_source_access import (
        _parse_revision,
        _parse_verified_revision,
    )

    repo = _repo(migrated_database)
    stored = repo.publish_revision(genesis_command())
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute("DELETE FROM dungeonmind.knowledge_native_read_artifacts")
        conn.commit()
    assert _parse_verified_revision(repo, stored) == _parse_revision(stored)
    assert _count(migrated_database, "knowledge_native_read_artifacts") == 0



def test_existing_verified_artifact_supports_lazy_authorized_alias_read_without_mutation(
    migrated_database,
    pg,
):
    from dataclasses import asdict

    from dungeonmind.application.vnext.alias_search import AliasSearchReadService
    from dungeonmind.application.vnext.alias_search_index import AliasSearchIndexCache
    from dungeonmind.application.vnext.materialization import encode_native_graph_payload
    from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
    from dungeonmind.application.vnext.read_context import KnowledgeReadContext
    from dungeonmind.contracts.semantic_profile import SemanticProfileRef
    from dungeonmind.contracts.vnext.domain import DomainContractRef, Entity
    from dungeonmind.infrastructure.postgres.vnext_knowledge import _read_revision
    from tests.unit.test_vnext_alias_search import alias, context

    item = alias("alias:artifact", "Cobalt keeper")
    template, _ = context([item], evidence=[], artifacts={}, revisions={})
    payload = encode_native_graph_payload(
        entities={"ent:one": Entity(entity_id="ent:one")},
        assertions={},
        aliases={item.alias_id: item},
        evidence={},
    )
    command = genesis_command(payload=payload).model_copy(
        update={
            "domain_contract_ref": DomainContractRef(**asdict(template.parsed.domain_contract_ref)),
            "semantic_profile_ref": SemanticProfileRef(
                **asdict(template.parsed.semantic_profile_ref)
            ),
        }
    )
    repo = _repo(migrated_database)
    stored = repo.publish_revision(command)
    head, events = repo.get_head(SPACE), repo.head_events(SPACE)
    tables = (
        "knowledge_revisions",
        "knowledge_native_read_artifacts",
        "knowledge_heads",
        "knowledge_head_events",
    )
    counts = {table: _count(migrated_database, table) for table in tables}
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        verified = _read_revision(conn, SPACE, stored.revision.revision_id)
        wire = artifacts._read_artifact(conn, verified)
        parsed = decode_read_artifact(wire, verified)
    assert parsed is not None
    reader = InMemoryKnowledgeSourceReader()
    ctx = KnowledgeReadContext(
        parsed=parsed,
        request=template.request.model_copy(
            update={"space_id": SPACE, "revision_id": stored.revision.revision_id}
        ),
        domain_contract=template.domain_contract,
        semantic_profile=template.semantic_profile,
        domain_policy=template.domain_policy,
        source_reader=reader,
    )
    structural = AliasSearchIndexCache(max_entries=1, max_postings=10_000)
    result = AliasSearchReadService().search_aliases(ctx, "cobalt", index_cache=structural)
    (hit,) = result.hits
    assert hit.alias.alias_id == item.alias_id and result.completeness.status == "complete"
    assert reader.snapshot_call_count == 0  # evidence-less identities preserve existing semantics
    assert repo.get_head(SPACE) == head and repo.head_events(SPACE) == events
    assert {table: _count(migrated_database, table) for table in tables} == counts
    assert repo.get_native_read_artifact(stored) == wire
