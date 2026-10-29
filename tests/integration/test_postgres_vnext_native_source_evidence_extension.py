from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import sql

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository
from tests.unit.test_vnext_native_source_evidence_extension import (
    access,
    exercise_access_and_conflict,
    exercise_duplicates,
    exercise_refusal,
    exercise_success,
    extension,
    publish,
    setup_source,
)

pytestmark = pytest.mark.integration


def repository(pg):
    return PostgresNativeSourceEvidenceRepository(pg.database)


def snapshot(pg):
    with pg.database.transaction() as conn:
        names = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='dungeonmind' ORDER BY tablename"
        ).fetchall()
        return {
            n["tablename"]: sorted(
                str(r["payload"])
                for r in conn.execute(
                    sql.SQL("SELECT to_jsonb(t)::text AS payload FROM dungeonmind.{} t").format(
                        sql.Identifier(n["tablename"])
                    )
                )
            )
            for n in names
        }


def test_postgres_extension_readers_replay_and_repository_reopen(pg):
    repo = repository(pg)
    domain, profile, root, req, receipt = exercise_success(repo)
    reopened = repository(pg)
    assert publish(reopened, domain, profile, req) == receipt
    assert access(reopened, domain, root, receipt.bindings[0].evidence_ref_id).status == "available"


@pytest.mark.parametrize(
    "change",
    ["body", "source", "root", "slice", "epoch", "parent", "space", "metadata", "utf8", "bounds"],
)
def test_postgres_invalid_request_preserves_publication(pg, change):
    exercise_refusal(repository(pg), change)


def test_postgres_duplicate_and_overlapping_intervals(pg):
    exercise_duplicates(repository(pg))


def test_postgres_current_access_replay_and_forged_root(pg):
    exercise_access_and_conflict(repository(pg))


@pytest.mark.parametrize(
    "hook",
    [
        "_after_revision_insert",
        "_after_receipt_insert",
        "_after_native_source_insert",
        "_after_native_receipt_insert",
    ],
)
def test_postgres_atomic_rollback_at_every_write_stage(pg, hook):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    before = snapshot(pg)

    def fail():
        raise RuntimeError("injected transaction failure")

    setattr(repo, hook, fail)
    with pytest.raises(RuntimeError, match="injected"):
        publish(repo, domain, profile, req)
    assert snapshot(pg) == before


def test_postgres_acknowledgement_loss_recovery_after_reopen(pg):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)

    def fail():
        raise RuntimeError("lost commit acknowledgement")

    repo._after_native_publication_commit = fail
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        publish(repo, domain, profile, req)
    before = snapshot(pg)
    reopened = repository(pg)
    receipt = publish(reopened, domain, profile, req)
    assert receipt == reopened.get_native_source_evidence_extension_receipt(
        root.space_id, req.extension_id
    )
    assert snapshot(pg) == before


def test_postgres_concurrent_same_operation_is_exactly_once(pg):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(repository(pg), domain, profile, req), range(2)))
    assert results[0] == results[1]
    with pg.database.transaction() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.knowledge_native_source_extensions"
            ).fetchone()["n"]
            == 1
        )


def test_postgres_concurrent_parent_epoch_race_is_fail_closed(pg):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    requests = [
        extension(repo, root, operation=f"extension:race:{i}", start=2 + i, end=8 + i)
        for i in range(2)
    ]

    def run(req):
        try:
            return publish(repository(pg), domain, profile, req)
        except (KnowledgeStaleParentRevisionError, NativeTextSourceAdmissionIntegrityError):
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, requests))
    assert sum(r == "refused" for r in results) == 1
    with pg.database.transaction() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.knowledge_native_source_extensions"
            ).fetchone()["n"]
            == 1
        )


def test_postgres_tampered_extension_receipt_cannot_open_or_replay(pg):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    receipt = publish(repo, domain, profile, req)
    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_source_extensions "
            "SET receipt_payload=jsonb_set(receipt_payload,'{source_revision_id}', '\"forged\"') "
            "WHERE space_id=%s AND extension_id=%s",
            (root.space_id, req.extension_id),
        )
    with pytest.raises(PersistenceIntegrityError):
        publish(repo, domain, profile, req)
    with pytest.raises(PersistenceIntegrityError):
        access(repo, domain, root, receipt.bindings[0].evidence_ref_id)


def test_populated_extension_authority_refuses_downgrade(pg):
    import subprocess
    import sys
    from pathlib import Path

    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    publish(repo, domain, profile, extension(repo, root))
    before = snapshot(pg)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "downgrade", "0017_publication_admission"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "cannot downgrade populated native source extensions" in result.stderr
    assert snapshot(pg) == before
    with pg.database.transaction() as conn:
        assert (
            conn.execute("SELECT version_num FROM dungeonmind.alembic_version").fetchone()[
                "version_num"
            ]
            == "0018_native_source_extensions"
        )
