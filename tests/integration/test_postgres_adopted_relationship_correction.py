"""Actual correction UoW, rollback, replay and writer-fence witnesses."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import IsolationLevel
from psycopg.errors import RaiseException

import tests.integration.test_postgres_adopted_assertion_withdrawal as existing
from dungeonmind.application.adopted_relationship_correction import (
    RelationshipCorrectionRuleRegistry,
)
from dungeonmind.domain.errors import PersistenceIntegrityError, StaleParentRevisionError
from dungeonmind.infrastructure.postgres import PostgresDatabase
from dungeonmind.infrastructure.postgres.existing_world_adoption import (
    PostgresExistingWorldAdoptionRepository,
)
from tests.unit.test_adopted_relationship_correction import (
    command_for,
    repairable_bundle,
    rules_for,
)

pytestmark = pytest.mark.integration


def prepared(pg, monkeypatch, failure_hook=None):
    original = existing._repairable_bundle
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: repairable_bundle(original()))
    legacy, parent = existing._prepared(pg, version=2)
    registry = RelationshipCorrectionRuleRegistry([rules_for(parent.graph_payload)])
    pg.existing_world_adoptions = PostgresExistingWorldAdoptionRepository(
        pg.database, correction_rule_registry=registry, failure_hook=failure_hook
    )
    return command_for(legacy, parent), parent, registry


def count_receipts(pg):
    with pg.database.connect() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM dungeonmind.adopted_relationship_corrections"
        ).fetchone()["n"]


def test_pg_atomic_correction_and_authenticated_replay(pg, monkeypatch):
    command, parent, _ = prepared(pg, monkeypatch)
    receipt = pg.existing_world_adoptions.correct_adopted_relationship(command)
    assert pg.existing_world_adoptions.correct_adopted_relationship(command) == receipt
    child = pg.world_graph.get_revision(command.world_id, receipt.published_revision_id)
    assert child.graph_payload["objects"] == parent.graph_payload["objects"]
    assert child.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]
    assert pg.world_graph.get_revision(command.world_id, parent.revision.revision_id) == parent
    assert count_receipts(pg) == 1


@pytest.mark.parametrize("stage", ["correction_graph", "correction_receipt"])
def test_pg_correction_failure_rolls_back_graph_head_event_and_receipt(pg, monkeypatch, stage):
    def fail(phase):
        if phase == stage:
            raise RuntimeError("injected correction failure")

    command, parent, _ = prepared(pg, monkeypatch, fail)
    before = existing._counts(pg, command.world_id)
    with pytest.raises(RuntimeError, match="injected"):
        pg.existing_world_adoptions.correct_adopted_relationship(command)
    assert existing._counts(pg, command.world_id) == before
    assert count_receipts(pg) == 0
    assert pg.world_graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


def test_pg_correction_parent_cas_has_exactly_one_winner(pg, monkeypatch):
    command, _, _ = prepared(pg, monkeypatch)
    competing = command.model_copy(update={"operation_id": "correction:competing"})

    def attempt(request):
        try:
            return pg.existing_world_adoptions.correct_adopted_relationship(request)
        except StaleParentRevisionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [command, competing]))
    assert sum(isinstance(r, StaleParentRevisionError) for r in results) == 1
    assert count_receipts(pg) == 1
    assert existing._counts(pg, command.world_id)[:2] == (2, 2)


def test_pg_correction_receipts_are_append_only_and_block_destructive_downgrade(
    pg, monkeypatch, database_url
):
    command, _, _ = prepared(pg, monkeypatch)
    pg.existing_world_adoptions.correct_adopted_relationship(command)
    for query in [
        "DELETE FROM dungeonmind.adopted_relationship_corrections",
        "UPDATE dungeonmind.adopted_relationship_corrections SET request_sha256='forged'",
    ]:
        with pytest.raises(RaiseException, match="append-only"), pg.database.connect() as conn:
            conn.execute(query)
    result = existing._alembic(database_url, "downgrade", "0019_complete_object_evidence")
    assert result.returncode != 0
    assert "cannot downgrade populated adopted relationship corrections" in result.stderr
    assert count_receipts(pg) == 1


def test_pg_missing_rule_authority_fails_closed(pg, monkeypatch):
    command, parent, _ = prepared(pg, monkeypatch)
    repository = PostgresExistingWorldAdoptionRepository(pg.database)
    with pytest.raises(PersistenceIntegrityError, match="rules unavailable"):
        repository.correct_adopted_relationship(command)
    assert count_receipts(pg) == 0
    assert pg.world_graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


def test_pg_repeatable_snapshot_cannot_hide_pre_fence_identity_writer(pg, monkeypatch):
    command, parent, registry = prepared(pg, monkeypatch)

    class RepeatableDatabase(PostgresDatabase):
        def connect(self):
            conn = super().connect()
            conn.isolation_level = IsolationLevel.REPEATABLE_READ
            return conn

    repository = PostgresExistingWorldAdoptionRepository(
        RepeatableDatabase(pg.database._database_url), correction_rule_registry=registry
    )
    with pytest.raises(PersistenceIntegrityError, match="read-committed"):
        repository.correct_adopted_relationship(command)
    assert count_receipts(pg) == 0
    assert pg.world_graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


def test_pg_current_endpoint_fingerprint_is_checked_after_adoption(pg, monkeypatch):
    import copy

    from dungeonmind.contracts.graph import PublishRevisionCommand
    from dungeonmind.domain.canonical import canonical_sha256

    command, parent, _ = prepared(pg, monkeypatch)
    payload = copy.deepcopy(parent.graph_payload)
    next(o for o in payload["objects"] if o["object_id"] == command.replacement_source_object_id)[
        "label"
    ] = "Changed after preparation"
    changed = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=parent.revision.revision_id,
            expected_parent_revision_id=parent.revision.revision_id,
            operation_ids=["test:correction-endpoint-change"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=command.requested_at,
        )
    )
    request = command.model_copy(
        update={
            "expected_parent_revision_id": changed.revision_id,
            "parent_payload_sha256": canonical_sha256(payload),
        }
    )
    before = existing._counts(pg, command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.correct_adopted_relationship(request)
    assert existing._counts(pg, command.world_id) == before
    assert count_receipts(pg) == 0


def test_pg_identity_writer_waits_for_publication_and_replay_uses_captured_history(pg, monkeypatch):
    import threading
    import time

    from dungeonmind.contracts.identity import IdentityDecisionRecordV2

    validated, release, writer_started, writer_done = (threading.Event() for _ in range(4))
    errors, receipts = [], []

    def pause(phase):
        if phase == "correction_graph":
            validated.set()
            assert release.wait(5), "publisher release deadline"

    command, _, _ = prepared(pg, monkeypatch, pause)

    def publish():
        try:
            receipts.append(pg.existing_world_adoptions.correct_adopted_relationship(command))
        except Exception as exc:
            errors.append(exc)

    def write():
        writer_started.set()
        try:
            pg.identity_decisions.append(
                IdentityDecisionRecordV2(
                    decision_id="decision:after-correction",
                    world_id=command.world_id,
                    decision_kind="merge",
                    subject_object_ids=[command.replacement_source_object_id, "obj:pc-beta"],
                    target_object_ids=["obj:pc-beta"],
                    merge_side_effects={},
                    actor="reviewer:synthetic",
                    created_at=command.requested_at,
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            writer_done.set()

    publisher, writer = threading.Thread(target=publish), threading.Thread(target=write)
    publisher.start()
    try:
        assert validated.wait(5)
        writer.start()
        assert writer_started.wait(5)
        observed_waiter = False
        for _ in range(100):
            with pg.database.connect() as conn:
                observed_waiter = conn.execute(
                    """SELECT EXISTS(SELECT 1 FROM pg_stat_activity
                    WHERE datname=current_database() AND wait_event_type='Lock'
                    AND cardinality(pg_blocking_pids(pid)) > 0) AS waiting"""
                ).fetchone()["waiting"]
            if observed_waiter:
                break
            time.sleep(0.01)
        assert observed_waiter, "typed identity writer did not visibly wait on World fence"
        assert not writer_done.is_set()
    finally:
        release.set()
        publisher.join(5)
        if writer.ident is not None:
            writer.join(5)
    assert not publisher.is_alive() and not writer.is_alive()
    assert not errors, errors
    assert len(receipts) == 1
    pg.existing_world_adoptions._failure_hook = None
    assert pg.existing_world_adoptions.correct_adopted_relationship(command) == receipts[0]
