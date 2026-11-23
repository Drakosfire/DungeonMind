from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import Connection, sql

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
)
from dungeonmind.application.vnext.native_source_admission import (
    publish_native_text_source_evidence,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository
from tests.unit.test_vnext_native_source_admission import BODY, _request
from tests.unit.test_vnext_native_source_evidence_extension import (
    access,
    exercise_access_and_conflict,
    exercise_duplicates,
    exercise_governed_extension,
    exercise_refusal,
    exercise_success,
    extension,
    governed_extension,
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


def test_postgres_batch_reads_only_matching_extension_and_preserves_epoch(pg, monkeypatch):
    from dungeonmind.infrastructure.postgres import vnext_sources

    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    old = repo.open_native_source_view(root.space_id)
    needed = publish(repo, domain, profile, extension(repo, root))
    unrelated = extension(repo, root, operation="extension:unrelated", start=16, end=20)
    publish(repo, domain, profile, unrelated)
    current = repo.open_native_source_view(root.space_id)
    pair = root.source_artifact_id, root.source_revision_id
    wanted = (*pair, needed.bindings[0].span_id)
    base = (*pair, root.bindings[0].span_id)
    checked = []
    verify = vnext_sources._verify_extension_row

    def observe(conn, space_id, row, **kwargs):
        checked.append(row["extension_id"])
        return verify(conn, space_id, row, **kwargs)

    monkeypatch.setattr(vnext_sources, "_verify_extension_row", observe)
    assert old.get_native_text_sources((wanted,)) == (None,)
    result = current.get_native_text_sources((wanted, base, wanted))
    assert [item.span_proof.span_id for item in result] == [wanted[2], base[2], wanted[2]]
    assert checked == [needed.extension_id]
    assert result[0].authority_epoch == needed.source_authority_epoch

    repo.withdraw_native_source(
        space_id=root.space_id, source_artifact_id=pair[0], source_revision_id=pair[1],
    )
    assert current.get_native_text_sources((wanted,)) == (result[0],)
    fresh = repo.open_native_source_view(root.space_id)
    assert fresh.get_native_text_sources((wanted,))[0].source_artifact.status == "retracted"


def test_postgres_discovery_batches_full_extension_proofs_and_reuses_verified_roots(
    pg, monkeypatch,
):
    from dungeonmind.infrastructure.postgres import vnext_sources

    repo = repository(pg)
    domain, profile, _, first = setup_source(repo)
    second_body = f"{BODY}\nSecond source"
    second = publish_native_text_source_evidence(
        repository=repo,
        request=_request(
            space_id=first.space_id, parent_revision_id=first.published_revision_id,
            admission_id="admit:discovery-second", body=second_body,
        ),
        domain_contract=domain, semantic_profile=profile,
    )
    old = repo.open_native_source_view(first.space_id)
    first_proof = publish(
        repo, domain, profile, extension(repo, first, operation="extension:first"),
    )
    extra = publish(repo, domain, profile, extension(
        repo, first, operation="extension:extra", start=16, end=20,
    ))
    second_proof = publish(repo, domain, profile, extension(
        repo, second, operation="extension:second",
    ).model_copy(update={"expected_body_sha256": hashlib.sha256(second_body.encode()).hexdigest()}))
    view = repo.open_native_source_view(first.space_id)

    def key(root, receipt):
        return root.source_artifact_id, root.source_revision_id, receipt.bindings[0].span_id

    wanted = (key(second, second_proof), key(first, first_proof), key(second, second_proof))
    original = key(first, first)
    assert old.get_native_text_sources_for_discovery((*wanted, original)) == (
        None, None, None,
        old.get_native_text_source(
            source_artifact_id=original[0], source_revision_id=original[1], span_id=original[2],
        ),
    )
    expected = tuple(
        view.get_native_text_source(source_artifact_id=a, source_revision_id=r, span_id=s)
        for a, r, s in wanted
    )
    assert all(expected)

    queries = []
    execute = Connection.execute

    def count(connection, query, *args, **kwargs):
        queries.append(query if isinstance(query, str) else query.as_string(connection))
        return execute(connection, query, *args, **kwargs)

    def refuse_reread(*args, **kwargs):
        pytest.fail("discovery re-read an original admission")

    with monkeypatch.context() as trace:
        trace.setattr(Connection, "execute", count)
        trace.setattr(vnext_sources, "_read_native_record", refuse_reread)
        assert view.get_native_text_sources_for_discovery(wanted) == expected
    assert sum("knowledge_native_source_extensions" in query for query in queries) == 1
    assert sum("knowledge_publication_receipts" in query for query in queries) == 1

    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_publication_receipts SET record_fingerprint = %s "
            "WHERE space_id = %s AND publication_id = %s",
            ("0" * 64, first.space_id, extra.extension_id),
        )
    # The unrelated extension contributes no requested span but still needs proof.
    assert view.get_native_text_sources(wanted) == expected
    with pytest.raises(PersistenceIntegrityError, match="publication receipt fingerprint drift"):
        view.get_native_text_sources_for_discovery(wanted)
    with pytest.raises(PersistenceIntegrityError, match="publication receipt fingerprint drift"):
        view.get_native_text_source(
            source_artifact_id=wanted[1][0], source_revision_id=wanted[1][1], span_id=wanted[1][2],
        )


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


@pytest.mark.parametrize("hide_requested_span", [False, True])
def test_postgres_tampered_extension_receipt_cannot_open_or_replay(pg, hide_requested_span):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    receipt = publish(repo, domain, profile, req)
    with pg.database.transaction() as conn:
        replacement = (
            "receipt_payload #- '{proofs,0}'"
            if hide_requested_span
            else """jsonb_set(receipt_payload,'{source_revision_id}', '"forged"')"""
        )
        conn.execute(
            sql.SQL(
                "UPDATE dungeonmind.knowledge_native_source_extensions "
                "SET receipt_payload={} WHERE space_id=%s AND extension_id=%s"
            ).format(sql.SQL(replacement)),
            (root.space_id, req.extension_id),
        )
    with pytest.raises(PersistenceIntegrityError):
        publish(repo, domain, profile, req)
    with pytest.raises(PersistenceIntegrityError):
        access(repo, domain, root, receipt.bindings[0].evidence_ref_id)
    view = repo.open_native_source_view(root.space_id)
    with pytest.raises(PersistenceIntegrityError):
        view.get_native_text_sources((
            (root.source_artifact_id, root.source_revision_id, receipt.bindings[0].span_id),
        ))


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
            == "0024_selective_read_projection"
        )


def test_postgres_governed_extension_commits_one_child_and_replays(pg):
    exercise_governed_extension(repository(pg), lambda: repository(pg))


def test_postgres_governed_extension_rolls_back_both_changes(pg):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    request = governed_extension(repo, root)
    before = snapshot(pg)

    def fail():
        raise RuntimeError("injected combined publication failure")

    repo._after_native_receipt_insert = fail
    with pytest.raises(RuntimeError, match="injected combined"):
        publish(repo, domain, profile, request)
    assert snapshot(pg) == before


@pytest.mark.parametrize("governed", [False, True])
def test_postgres_metadata_recovery_after_withdrawal(pg, governed):
    from tests.unit.test_vnext_native_source_evidence_extension import exercise_metadata_recovery

    repo = repository(pg)
    request, receipt = exercise_metadata_recovery(repo, governed=governed)
    # The helper asserts head/event conservation; all tables remain unchanged
    # across an additional recovery using original immutable descriptors.
    from dungeonmind.application.vnext.native_source_extension import (
        recover_native_source_evidence_extension,
    )
    from tests.unit.test_vnext_native_source_evidence_extension import _domain, _profile

    domain, profile = _domain(), _profile()
    domain.claim_modes = ["test:source"]
    from dungeonmind.contracts.vnext.domain import SemanticProfilePredicate

    profile.predicates = [
        SemanticProfilePredicate(term="test:name", allowed_value_kinds=["literal"])
    ]
    before = snapshot(pg)
    assert (
        recover_native_source_evidence_extension(
            repository=repository(pg),
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )
        == receipt
    )
    assert snapshot(pg) == before


@pytest.mark.parametrize("corruption", ["missing_root", "missing_ancestor", "wrong_row", "cycle"])
def test_postgres_recovery_verifies_immutable_ancestry(pg, corruption):
    from tests.unit.test_vnext_native_source_evidence_extension import (
        exercise_corrupt_recovery_ancestry,
    )

    exercise_corrupt_recovery_ancestry(repository(pg), corruption)
