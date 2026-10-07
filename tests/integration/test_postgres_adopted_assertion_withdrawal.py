from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
)
from dungeonmind.contracts.adopted_assertion_withdrawal import (
    AdoptedAssertionWithdrawalCommandV1,
    AdoptedAssertionWithdrawalCommandV2,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.postgres.existing_world_adoption import (
    PostgresExistingWorldAdoptionRepository,
)
from tests.integration.test_migrations import REPO_ROOT
from tests.unit.test_adopted_assertion_withdrawal import _add_three_pc_commands, _drift_parent
from tests.unit.test_existing_world_adoption import (
    ART_A,
    ART_B,
    NOW,
    REV_A,
    REV_B,
    WORLD_ID,
    _artifact,
    _revision,
    graph_reader,
    v2_bundle_bytes,
)
from tests.unit.test_existing_world_adoption_repair import (
    REPAIRED_AT,
    _intent,
    _repairable_bundle,
)

pytestmark = pytest.mark.integration


def _prepared(pg, *, evidence_span: str = "span:postgres-a", version=1, repair=True):
    bundle = _repairable_bundle()
    graph_payload = copy.deepcopy(bundle.graph_payload)
    for evidence in graph_payload["evidence_refs"]:
        if evidence["evidence_ref_id"] == "ev:a":
            evidence.update(
                {
                    "source_span_ref_id": evidence_span,
                    "source_locator": None if version == 2 else "fixture://notes-a#paragraph-17",
                    "can_highlight_span": True,
                }
            )
    _add_three_pc_commands(graph_payload)
    bundle = bundle.model_copy(update={"graph_payload": graph_payload})
    raw = v2_bundle_bytes(bundle)
    adoption = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=graph_reader(),
    )
    if repair:
        repair_existing_world_adoption_source_classification(
            raw,
            repair_intent=_intent(bundle),
            repaired_at=REPAIRED_AT,
            adoption_repository=pg.existing_world_adoptions,
            graph_reader=graph_reader(),
        )
    head = pg.world_graph.get_head(WORLD_ID)
    assert head is not None
    parent = pg.world_graph.get_revision(WORLD_ID, head.head_revision_id)
    assert parent is not None
    command_type = (
        AdoptedAssertionWithdrawalCommandV2 if version == 2 else AdoptedAssertionWithdrawalCommandV1
    )
    command = command_type.model_validate(
        dict(
            operation_id="withdrawal:postgres-1",
            world_id=WORLD_ID,
            adoption_id=adoption.adoption_id,
            expected_parent_revision_id=head.head_revision_id,
            relationship_id="rel:leads",
            assertion_id="asrt:leads",
            subject_object_id="obj:headmaster",
            predicate="test:leads",
            object_object_id="obj:college",
            evidence_ref_id="ev:a",
            source_artifact_id=ART_A,
            source_revision_id=REV_A,
            source_span_ref_id=evidence_span,
            source_locator=None if version == 2 else "fixture://notes-a#paragraph-17",
            parent_payload_sha256=canonical_sha256(parent.graph_payload),
            actor="reviewer:postgres-test",
            requested_at=NOW,
        )
    )
    return command, parent


def _counts(pg, world_id: str) -> tuple[int, int, int]:
    with pg.database.connect() as conn:
        revisions = conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.graph_revisions WHERE world_id = %s",
            (world_id,),
        ).fetchone()["n"]
        events = conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.world_graph_head_events WHERE world_id = %s",
            (world_id,),
        ).fetchone()["n"]
        receipts = conn.execute(
            "SELECT COUNT(*) AS n FROM "
            "dungeonmind.adopted_assertion_withdrawals WHERE world_id = %s",
            (world_id,),
        ).fetchone()["n"]
    return revisions, events, receipts


def test_postgres_withdrawal_is_atomic_idempotent_and_receipt_survives_descendant(
    pg, withdrawal_version
) -> None:
    command, parent = _prepared(pg, version=withdrawal_version)
    receipt = pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    child = pg.world_graph.get_revision(command.world_id, receipt.published_revision_id)
    assert child is not None
    expected = copy.deepcopy(parent.graph_payload)
    expected["relationships"] = [
        item
        for item in expected["relationships"]
        if item["relationship_id"] != command.relationship_id
    ]
    assert child.graph_payload == expected
    assert {
        edge["relationship_id"]
        for edge in child.graph_payload["relationships"]
        if edge["predicate"] == "test:commands"
    } == {f"rel:pc-command-{suffix}" for suffix in ("alpha", "beta", "gamma")}
    assert (
        pg.world_graph.get_revision(command.world_id, command.expected_parent_revision_id) == parent
    )
    first_counts = _counts(pg, command.world_id)
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
    assert _counts(pg, command.world_id) == first_counts

    other_type = (
        AdoptedAssertionWithdrawalCommandV1
        if withdrawal_version == 2
        else AdoptedAssertionWithdrawalCommandV2
    )
    other_payload = command.model_dump(mode="json")
    other_payload["schema_version"] = other_type.model_fields["schema_version"].default
    other_payload["source_locator"] = "fixture://other-version" if withdrawal_version == 2 else None
    with pytest.raises(IdempotencyConflictError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(
            other_type.model_validate(other_payload)
        )
    assert _counts(pg, command.world_id) == first_counts
    conflict = command.model_copy(update={"actor": "reviewer:changed"})
    with pytest.raises(IdempotencyConflictError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(conflict)
    assert _counts(pg, command.world_id) == first_counts

    # Move the head to a later child; the old operation receipt remains replayable.
    descendant = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["withdrawal-test:descendant"],
            graph_schema=child.revision.graph_schema,
            graph_payload=child.graph_payload,
            created_at=NOW,
        )
    )
    assert pg.world_graph.get_head(command.world_id).head_revision_id == descendant.revision_id
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt


@pytest.mark.parametrize("stage", ["withdrawal_graph", "withdrawal_receipt"])
def test_postgres_withdrawal_failure_rolls_back_graph_and_receipt(
    pg,
    withdrawal_version,
    stage,
) -> None:
    command, _ = _prepared(pg, version=withdrawal_version)
    before_counts = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)

    def fail(stage: str) -> None:
        if stage == failure_stage:
            raise RuntimeError("injected withdrawal failure")

    failure_stage = stage
    repository = PostgresExistingWorldAdoptionRepository(pg.database, failure_hook=fail)
    with pytest.raises(RuntimeError, match="injected withdrawal failure"):
        repository.withdraw_adopted_assertion(command)
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_concurrent_withdrawals_have_one_cas_winner(pg, withdrawal_version) -> None:
    command, _ = _prepared(pg, version=withdrawal_version)
    competing = command.model_copy(update={"operation_id": "withdrawal:postgres-2"})

    def attempt(item):
        try:
            return pg.existing_world_adoptions.withdraw_adopted_assertion(item)
        except StaleParentRevisionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (command, competing)))
    assert sum(not isinstance(item, StaleParentRevisionError) for item in outcomes) == 1
    assert sum(isinstance(item, StaleParentRevisionError) for item in outcomes) == 1
    counts = _counts(pg, command.world_id)
    assert counts[2] == 1
    assert counts[0] == 2
    assert counts[1] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"adoption_id": "adopt:not-persisted"},
        {"predicate": "test:forged"},
        {"evidence_ref_id": "ev:not-adopted"},
        {"source_artifact_id": "src:not-adopted"},
        {"source_revision_id": "srcrev:not-adopted"},
        {"source_span_ref_id": "span:forged"},
        {"source_locator": "fixture://forged"},
        {"parent_payload_sha256": "f" * 64},
    ],
)
def test_postgres_forged_bindings_fail_before_mutation(pg, changes, withdrawal_version) -> None:
    command, _ = _prepared(pg, version=withdrawal_version)
    before_counts = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises((PersistenceIntegrityError, ValidationError)):
        pg.existing_world_adoptions.withdraw_adopted_assertion(command.model_copy(update=changes))
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_profile_drift_fails_before_withdrawal_mutation(pg, withdrawal_version) -> None:
    command, parent = _prepared(pg, version=withdrawal_version)
    changed = copy.deepcopy(parent.graph_payload)
    changed["semantic_profile"]["descriptor_sha256"] = "f" * 64
    alternate = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            operation_ids=["withdrawal-test:profile-drift"],
            graph_schema="dm_union_graph_v6",
            graph_payload=changed,
            created_at=NOW,
        )
    )
    before_counts = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    forged = command.model_copy(
        update={
            "expected_parent_revision_id": alternate.revision_id,
            "parent_payload_sha256": canonical_sha256(changed),
        }
    )
    with pytest.raises((PersistenceIntegrityError, ValidationError)):
        pg.existing_world_adoptions.withdraw_adopted_assertion(forged)
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head


@pytest.fixture(params=[1, 2])
def withdrawal_version(request):
    return request.param


@pytest.mark.parametrize("binding", ["different_artifact", "outside_membership"])
def test_postgres_persisted_unbound_source_revision_is_rejected(pg, withdrawal_version, binding):
    command, _parent = _prepared(pg, version=withdrawal_version)
    if binding == "different_artifact":
        assert pg.sources.get_revision(REV_B).source_artifact_id == ART_B
        changes = {"source_revision_id": REV_B}
    else:
        pg.sources.put_artifact(_artifact("src:outside-adoption", "srcrev:outside-adoption"))
        pg.sources.put_revision(
            _revision("srcrev:outside-adoption", "src:outside-adoption", "a" * 64)
        )
        changes = {
            "source_artifact_id": "src:outside-adoption",
            "source_revision_id": "srcrev:outside-adoption",
        }
    before = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(command.model_copy(update=changes))
    assert _counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == before_head


@pytest.mark.parametrize(
    "drift", ["locator", "span", "revision", "profile", "duplicate", "assertion", "evidence"]
)
def test_postgres_v2_parent_drift_leaves_zero_partial_state(pg, drift):
    command, parent = _prepared(pg, version=2)
    payload = _drift_parent(copy.deepcopy(parent.graph_payload), command, drift)
    changed = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            operation_ids=[f"test-parent-drift:{drift}"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=NOW,
        )
    )
    changed_command = command.model_copy(
        update={
            "expected_parent_revision_id": changed.revision_id,
            "parent_payload_sha256": canonical_sha256(payload),
        }
    )
    before = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(changed_command)
    assert _counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_requires_durable_v4_receipt(pg, withdrawal_version):
    command, _parent = _prepared(pg, version=withdrawal_version, repair=False)
    before = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    assert _counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_v2_cannot_withdraw_locator_bearing_adopted_evidence(pg):
    v1, _parent = _prepared(pg, version=1)
    payload = v1.model_dump(mode="json")
    payload.update(schema_version="dm_adopted_assertion_withdrawal_command_v2", source_locator=None)
    command = AdoptedAssertionWithdrawalCommandV2.model_validate(payload)
    before = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    assert _counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == before_head


def _alembic(database_url, *args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "DUNGEONMIND_DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )


def test_migration_couples_locator_version_and_preserves_append_only_receipts(
    pg,
    database_url,
    withdrawal_version,
):
    from psycopg.errors import CheckViolation, RaiseException

    command, _parent = _prepared(pg, version=withdrawal_version)
    receipt = pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    before = _counts(pg, command.world_id)
    wrong_locator = None if withdrawal_version == 1 else "fixture://forged"
    with pytest.raises(CheckViolation), pg.database.connect() as conn:
        conn.execute(
            "INSERT INTO dungeonmind.adopted_assertion_withdrawals "
            "SELECT (jsonb_populate_record(NULL::dungeonmind.adopted_assertion_withdrawals, "
            "to_jsonb(w) || %s::jsonb)).* FROM dungeonmind.adopted_assertion_withdrawals w "
            "WHERE operation_id = %s",
            (
                json.dumps(
                    {"operation_id": "withdrawal:invalid-locator", "source_locator": wrong_locator}
                ),
                command.operation_id,
            ),
        )
    for action in (
        "UPDATE dungeonmind.adopted_assertion_withdrawals SET actor = 'forged'",
        "DELETE FROM dungeonmind.adopted_assertion_withdrawals",
    ):
        with pytest.raises(RaiseException, match="append-only"), pg.database.connect() as conn:
            conn.execute(action)
    try:
        result = _alembic(database_url, "downgrade", "0013_adopted_withdrawal_v1")
        if withdrawal_version == 2:
            assert result.returncode != 0
            assert "cannot downgrade while V2 withdrawal receipts exist" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
            assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
            with pg.database.connect() as conn:
                locator = conn.execute(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema = 'dungeonmind' "
                    "AND table_name = 'adopted_assertion_withdrawals' "
                    "AND column_name = 'source_locator'"
                ).fetchone()
                assert locator["is_nullable"] == "NO"
    finally:
        result = _alembic(database_url, "upgrade", "head")
        assert result.returncode == 0, result.stderr
    assert _counts(pg, command.world_id) == before
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
