import copy

import pytest

import tests.integration.test_postgres_adopted_assertion_withdrawal as existing
from dungeonmind.contracts.adopted_assertion_withdrawal import AdoptedAssertionWithdrawalCommandV3
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.existing_world_adoption import (
    PostgresExistingWorldAdoptionRepository,
)
from tests.unit.test_adopted_object_withdrawal import OBJECT_ID, object_command, orphan_bundle

pytestmark = pytest.mark.integration


def prepared(pg, monkeypatch):
    original = existing._repairable_bundle
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: orphan_bundle(original()))
    command, parent = existing._prepared(pg, version=2)
    return object_command(command), parent


def test_postgres_object_withdrawal_is_atomic_and_replay_verified(pg, monkeypatch):
    command, parent = prepared(pg, monkeypatch)
    receipt = pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    child = pg.world_graph.get_revision(command.world_id, receipt.published_revision_id)
    expected = copy.deepcopy(parent.graph_payload)
    expected["objects"] = [o for o in expected["objects"] if o["object_id"] != OBJECT_ID]
    assert child.graph_payload == expected
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
    assert pg.world_graph.get_revision(command.world_id, parent.revision.revision_id) == parent
    assert existing._counts(pg, command.world_id)[2] == 1


@pytest.mark.parametrize("stage", ["withdrawal_graph", "withdrawal_receipt"])
def test_postgres_object_withdrawal_rolls_back_graph_and_receipt(pg, monkeypatch, stage):
    command, _ = prepared(pg, monkeypatch)
    before = existing._counts(pg, command.world_id)
    head = pg.world_graph.get_head(command.world_id)

    def fail(phase):
        if phase == stage:
            raise RuntimeError("injected object withdrawal failure")

    repository = PostgresExistingWorldAdoptionRepository(pg.database, failure_hook=fail)
    with pytest.raises(RuntimeError, match="injected"):
        repository.withdraw_adopted_assertion(command)
    assert existing._counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == head


def test_postgres_object_withdrawal_refuses_dependencies(pg, monkeypatch):
    command, _ = prepared(pg, monkeypatch)
    request = AdoptedAssertionWithdrawalCommandV3.model_validate(
        command.model_dump(mode="json")
        | {"subject_object_id": "obj:headmaster", "assertion_id": "asrt:headmaster-exists"}
    )
    before = existing._counts(pg, command.world_id)
    with pytest.raises(PersistenceIntegrityError, match="incident relationships"):
        pg.existing_world_adoptions.withdraw_adopted_assertion(request)
    assert existing._counts(pg, command.world_id) == before


@pytest.mark.parametrize("bind_new_parent", [False, True])
def test_postgres_object_withdrawal_refuses_stale_or_changed_target(
    pg, monkeypatch, bind_new_parent
):
    from dungeonmind.contracts.graph import PublishRevisionCommand
    from dungeonmind.domain.canonical import canonical_sha256
    from dungeonmind.domain.errors import DungeonMindError

    command, parent = prepared(pg, monkeypatch)
    payload = copy.deepcopy(parent.graph_payload)
    target = next(o for o in payload["objects"] if o["object_id"] == OBJECT_ID)
    target["label"] = "Changed after adoption"
    revision = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            operation_ids=["test-object-target-drift"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=existing.NOW,
        )
    )
    if bind_new_parent:
        command = command.model_copy(
            update={
                "expected_parent_revision_id": revision.revision_id,
                "parent_payload_sha256": canonical_sha256(payload),
            }
        )
    before = existing._counts(pg, command.world_id)
    head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(DungeonMindError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    assert existing._counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id) == head


@pytest.mark.parametrize("field", ["relationship_id", "predicate", "object_object_id"])
def test_postgres_object_receipt_rejects_relationship_columns(pg, monkeypatch, field):
    import json

    from psycopg.errors import CheckViolation

    command, _ = prepared(pg, monkeypatch)
    pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    before = existing._counts(pg, command.world_id)
    with pytest.raises(CheckViolation), pg.database.connect() as conn:
        conn.execute(
            "INSERT INTO dungeonmind.adopted_assertion_withdrawals "
            "SELECT (jsonb_populate_record(NULL::dungeonmind.adopted_assertion_withdrawals, "
            "to_jsonb(w) || %s::jsonb)).* FROM dungeonmind.adopted_assertion_withdrawals w "
            "WHERE operation_id = %s",
            (
                json.dumps({"operation_id": "withdrawal:invalid-target", field: "forged"}),
                command.operation_id,
            ),
        )
    assert existing._counts(pg, command.world_id) == before
