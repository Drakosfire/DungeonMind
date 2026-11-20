"""Owning transaction/reopen/recovery proofs using fixture-owned PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
)
from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository
from tests.integration.test_postgres_vnext_native_source_evidence_extension import snapshot
from tests.unit.test_vnext_native_source_evidence_extension import setup_source
from tests.unit.test_vnext_native_source_publication import (
    REFUSALS,
    advance_head,
    exercise_all_origin_lookups,
    exercise_authorized_reads,
    exercise_crossfamily_id_conflicts,
    exercise_refusal,
    exercise_success,
    publish,
    recover,
    request_for,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_postgres_atomic_commit_reopen_and_recovery(pg, mode):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, root, request, receipt = exercise_success(repo, mode)
    reopened = PostgresNativeSourceEvidenceRepository(pg.database)
    assert recover(reopened, domain, profile, request) == receipt
    assert publish(reopened, domain, profile, request) == receipt
    repo.withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    before = snapshot(pg)
    assert recover(reopened, domain, profile, request) == receipt
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(reopened, domain, profile, request)
    assert snapshot(pg) == before


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
@pytest.mark.parametrize(
    "hook",
    [
        "_after_revision_insert",
        "_after_receipt_insert",
        "_after_native_source_insert",
        "_after_native_receipt_insert",
    ],
)
def test_postgres_complete_rollback_at_actual_hooks(pg, mode, hook):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root, mode=mode)
    before = snapshot(pg)
    fired = []

    def fail():
        fired.append(True)
        raise RuntimeError("actual transaction fault")

    setattr(repo, hook, fail)
    with pytest.raises(RuntimeError, match="actual transaction fault"):
        publish(repo, domain, profile, request)
    assert fired
    assert snapshot(pg) == before


def test_postgres_lost_ack_and_same_request_race(pg):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    fired = []

    def fail():
        fired.append(True)
        raise RuntimeError("lost commit acknowledgement")

    repo._after_native_publication_commit = fail
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        publish(repo, domain, profile, request)
    assert fired
    receipt = recover(repo, domain, profile, request)
    before = snapshot(pg)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: publish(
                    PostgresNativeSourceEvidenceRepository(pg.database), domain, profile, request
                ),
                range(2),
            )
        )
    assert results == [receipt, receipt]
    assert snapshot(pg) == before


def test_postgres_competing_actual_writers_have_one_winner(pg):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    requests = [
        request_for(repo, domain, profile, root, operation="composed:" + str(i)) for i in range(2)
    ]

    def commit(request):
        try:
            return publish(
                PostgresNativeSourceEvidenceRepository(pg.database), domain, profile, request
            )
        except KnowledgeStaleParentRevisionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(commit, requests))
    assert sum(r is not None for r in results) == 1


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_postgres_withdrawal_wins_before_publication_lock(pg, mode):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root, mode=mode)
    # A separate real repository commits withdrawal after preparation, before
    # the publication attempts its owning source-epoch lock.
    PostgresNativeSourceEvidenceRepository(pg.database).withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    before = snapshot(pg)
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, request)
    assert snapshot(pg) == before


@pytest.mark.parametrize("change", REFUSALS)
def test_postgres_closed_refusals_have_no_residue(pg, change):
    exercise_refusal(PostgresNativeSourceEvidenceRepository(pg.database), change)


def test_postgres_reopened_origin_discovery_and_reuse_all_families(pg):
    # No remembered caller receipts; repository instance and DB indexes own discovery.
    exercise_all_origin_lookups(PostgresNativeSourceEvidenceRepository(pg.database))


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_postgres_authorized_alias_search_and_withdrawal(pg, mode):
    exercise_authorized_reads(PostgresNativeSourceEvidenceRepository(pg.database), mode)


def test_postgres_crossfamily_operation_ids(pg):
    exercise_crossfamily_id_conflicts(PostgresNativeSourceEvidenceRepository(pg.database))


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_postgres_metadata_recovery_descendant_no_mutable_opens(pg, mode, monkeypatch):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, root, request, receipt = exercise_success(repo, mode)
    advance_head(repo, request, receipt)
    repo.withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    before = snapshot(pg)

    def forbidden(*a, **k):
        raise AssertionError("mutable read/write during recovery")

    for name in (
        "get_head",
        "open_native_source_view",
        "publish_governed_native_source_publication",
        "publish_revision",
        "publish_publication",
    ):
        monkeypatch.setattr(repo, name, forbidden)
    assert recover(repo, domain, profile, request) == receipt
    assert snapshot(pg) == before


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_postgres_lock_held_publication_excludes_actual_withdrawal(pg, mode):
    from concurrent.futures import TimeoutError
    from threading import Event

    entered, release, withdraw_started = Event(), Event(), Event()
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root, mode=mode)

    def hold_real_transaction():
        entered.set()
        assert release.wait(10), "lock-held test release timeout"

    repo._after_revision_insert = hold_real_transaction

    def withdraw():
        withdraw_started.set()
        return PostgresNativeSourceEvidenceRepository(pg.database).withdraw_native_source(
            space_id=root.space_id,
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication = pool.submit(publish, repo, domain, profile, request)
        try:
            assert entered.wait(10), "publisher did not reach actual transaction hook"
            withdrawal = pool.submit(withdraw)
            assert withdraw_started.wait(5)
            # This is synchronization proof, not a performance measurement.
            with pytest.raises(TimeoutError):
                withdrawal.result(timeout=0.1)
            with pg.database.transaction() as conn:
                blocked = conn.execute(
                    "SELECT count(*) AS n FROM pg_stat_activity WHERE "
                    "datname=current_database() AND wait_event_type='Lock' AND "
                    "cardinality(pg_blocking_pids(pid))>0"
                ).fetchone()["n"]
            assert blocked >= 1, "withdrawal must actually wait on held source lock"
        finally:
            release.set()
        receipt = publication.result(timeout=10)
        epoch = withdrawal.result(timeout=10)
    assert epoch == receipt.source_authority_epoch_after + 1
    assert (
        recover(PostgresNativeSourceEvidenceRepository(pg.database), domain, profile, request)
        == receipt
    )
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, request)


@pytest.mark.parametrize("damage", ["result", "proof", "alias", "missing_receipt"])
def test_postgres_immutable_recovery_tamper_zero_write(pg, damage):
    from psycopg.types.json import Jsonb

    from dungeonmind.domain.canonical import canonical_sha256
    from dungeonmind.domain.errors import PersistenceIntegrityError

    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, root, request, receipt = exercise_success(repo, "new_intervals")
    with pg.database.transaction() as conn:
        if damage == "missing_receipt":
            conn.execute(
                "DELETE FROM dungeonmind.knowledge_native_source_publications WHERE "
                "space_id=%s AND publication_id=%s",
                (root.space_id, request.publication_id),
            )
        elif damage == "alias":
            row = conn.execute(
                "SELECT graph_payload FROM dungeonmind.knowledge_revisions WHERE space_id=%s "
                "AND revision_id=%s",
                (root.space_id, receipt.publication_receipt.published_revision_id),
            ).fetchone()
            payload = row["graph_payload"]
            payload["aliases"][0]["alias_text"] = "corrupted"
            conn.execute(
                "UPDATE dungeonmind.knowledge_revisions SET graph_payload=%s WHERE "
                "space_id=%s AND revision_id=%s",
                (Jsonb(payload), root.space_id, receipt.publication_receipt.published_revision_id),
            )
        else:
            wire = receipt.model_dump(mode="json")
            if damage == "result":
                wire["result_bindings"][0]["durable_id"] = "ent:wrong"
            else:
                wire["proofs"][0]["slice_sha256"] = "0" * 64
            conn.execute(
                "UPDATE dungeonmind.knowledge_native_source_publications SET "
                "receipt_payload=%s, record_fingerprint=%s WHERE space_id=%s AND "
                "publication_id=%s",
                (Jsonb(wire), canonical_sha256(wire), root.space_id, request.publication_id),
            )
    before = snapshot(pg)
    with pytest.raises(PersistenceIntegrityError):
        recover(repo, domain, profile, request)
    assert snapshot(pg) == before


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
@pytest.mark.parametrize(
    "kind", ["retract_assertion", "supersede_assertion", "propose_identity_decision"]
)
def test_postgres_destructive_governance_no_mutation(pg, mode, kind):
    from pydantic import ValidationError

    from dungeonmind.contracts.vnext.native_source_publication import (
        GovernedNativeSourcePublicationV1,
    )
    from tests.unit.test_vnext_native_source_publication import destructive_request

    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    _, _, _, data = destructive_request(repo, mode, kind)
    before = snapshot(pg)
    with pytest.raises(ValidationError, match="create-only"):
        GovernedNativeSourcePublicationV1.model_validate(data)
    assert snapshot(pg) == before


@pytest.mark.parametrize("substitute", ["root", "extension", "publication"])
def test_postgres_valid_wrong_revision_substitution(pg, substitute):
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from tests.unit.test_vnext_native_source_evidence_extension import extension
    from tests.unit.test_vnext_native_source_evidence_extension import publish as publish_extension
    from tests.unit.test_vnext_native_source_publication import support_ref

    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile, _, root = setup_source(repo)
    intermediate = extension(repo, root, operation="intermediate:extension", start=9, end=10)
    introduced = publish_extension(repo, domain, profile, intermediate)
    first_request = request_for(repo, domain, profile, root)
    first = publish(repo, domain, profile, first_request)
    if substitute == "root":
        request, result, target = first_request, first, root.published_revision_id
    else:
        original = introduced if substitute == "extension" else first
        request = request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            operation="reuse:target",
            support=[support_ref(original, original.proofs[0], substitute)],
        )
        result = publish(repo, domain, profile, request)
        target = original.publication_receipt.published_revision_id
    wrong = repo.get_revision(root.space_id, result.publication_receipt.published_revision_id)

    class WrongValidRow:
        def __getattr__(self, name):
            return getattr(repo, name)

        def get_revision(self, space, revision):
            return wrong if revision == target else repo.get_revision(space, revision)

    before = snapshot(pg)
    with pytest.raises(PersistenceIntegrityError):
        recover(WrongValidRow(), domain, profile, request)
    assert snapshot(pg) == before


def test_new_migration_refuses_populated_downgrade(pg):
    import subprocess
    import sys
    from pathlib import Path

    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    exercise_success(repo, "new_intervals")
    before = snapshot(pg)
    # Fixture is an isolated disposable DB; never target a caller/live database.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0022_native_read_artifacts"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "cannot downgrade populated native source publications" in result.stderr
    assert snapshot(pg) == before
