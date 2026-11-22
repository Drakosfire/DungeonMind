from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import Connection, sql

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
    execute = Connection.execute

    def observe(conn, query, params=None, **kwargs):
        checked.append(query)
        return execute(conn, query, params, **kwargs)

    with monkeypatch.context() as counter:
        counter.setattr(Connection, "execute", observe)
        assert old.get_native_text_sources((wanted,)) == (None,)
        result = current.get_native_text_sources((wanted, base, wanted))
    assert [item.span_proof.span_id for item in result] == [wanted[2], base[2], wanted[2]]
    assert len(checked) == 4
    assert all("receipt_payload" not in query and "span_proofs" not in query for query in checked)
    assert sum("native_citation_proofs p" in query for query in checked) == 2
    assert result[0].authority_epoch == needed.source_authority_epoch

    repo.withdraw_native_source(
        space_id=root.space_id, source_artifact_id=pair[0], source_revision_id=pair[1],
    )
    assert current.get_native_text_sources((wanted,)) == (result[0],)
    fresh = repo.open_native_source_view(root.space_id)
    assert fresh.get_native_text_sources((wanted,))[0].source_artifact.status == "retracted"


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
            == "0025_native_citation_proofs"
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


@pytest.mark.parametrize("damage", ["missing", "changed", "duplicate", "misbound"])
def test_postgres_typed_proof_corruption_fails_closed(pg, damage):
    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    extension_receipt = publish(repo, domain, profile, extension(repo, root))
    view = repo.open_native_source_view(root.space_id)
    span_id = extension_receipt.bindings[0].span_id
    keys = ((root.source_artifact_id, root.source_revision_id, span_id),)
    assert view.get_native_text_sources(keys)[0].span_proof.span_id == span_id
    with pg.database.transaction() as conn:
        params = (root.space_id, extension_receipt.extension_id, span_id)
        where = " WHERE (space_id, receipt_id, span_id) = (%s, %s, %s)"
        if damage == "missing":
            conn.execute("DELETE FROM dungeonmind.native_citation_proofs" + where, params)
        elif damage == "changed":
            conn.execute(
                "UPDATE dungeonmind.native_citation_proofs SET slice_sha256 = repeat('0', 64)"
                + where, params,
            )
        elif damage == "duplicate":
            conn.execute(
                """
                INSERT INTO dungeonmind.native_citation_proofs
                SELECT space_id, %s, span_id, evidence_ref_id, source_revision_id,
                       start_byte, end_byte, slice_sha256
                FROM dungeonmind.native_citation_proofs
                """ + where,
                (root.admission_id, *params),
            )
        else:
            conn.execute(
                "UPDATE dungeonmind.native_citation_proofs SET source_revision_id = 'wrong'"
                + where, params,
            )
    with pytest.raises(PersistenceIntegrityError, match="span index drift"):
        view.get_native_text_sources(keys)


def test_populated_citation_projection_roundtrip_verifies_existing_receipts(pg):
    import subprocess
    import sys
    from pathlib import Path

    repo = repository(pg)
    domain, profile, _, root = setup_source(repo)
    receipt = publish(repo, domain, profile, extension(repo, root))
    pair = (root.source_artifact_id, root.source_revision_id)
    keys = ((*pair, receipt.bindings[0].span_id), (*pair, root.bindings[0].span_id))
    view = repo.open_native_source_view(root.space_id)
    expected = view.get_native_text_sources(keys)
    assert all(item is not None for item in expected)
    cwd = Path(__file__).parents[2]

    for args in [("downgrade", "0024_selective_read_projection"), ("upgrade", "head")]:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "alembic", *args],
            cwd=cwd, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    assert view.get_native_text_sources(keys) == expected
