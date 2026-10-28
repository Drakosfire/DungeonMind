"""Owning transaction proofs for complete-source object repair."""

import copy

import pytest
from psycopg.errors import CheckViolation, RaiseException

import tests.integration.test_postgres_adopted_assertion_withdrawal as existing
from dungeonmind.contracts.adopted_assertion_withdrawal import AdoptedAssertionWithdrawalCommandV4
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.existing_world_adoption import (
    PostgresExistingWorldAdoptionRepository,
)
from tests.unit.test_adopted_object_withdrawal import OBJECT_ID
from tests.unit.test_complete_evidence_object_withdrawal import complete_bundle, complete_command

pytestmark = pytest.mark.integration


def prepared(pg, monkeypatch):
    original = existing._repairable_bundle
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: complete_bundle(original()))
    command, parent = existing._prepared(pg, version=2)
    return complete_command(command, parent), parent


def test_complete_cross_source_pg_withdrawal_reconstructs_receipt_and_replays(pg, monkeypatch):
    command, parent = prepared(pg, monkeypatch)
    receipt = pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    assert receipt.evidence_bindings == command.evidence_bindings
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
    expected = copy.deepcopy(parent.graph_payload)
    expected["objects"] = [o for o in expected["objects"] if o["object_id"] != OBJECT_ID]
    child = pg.world_graph.get_revision(command.world_id, receipt.published_revision_id)
    assert child.graph_payload == expected
    assert pg.world_graph.get_revision(command.world_id, parent.revision.revision_id) == parent


@pytest.mark.parametrize("change", ["omit", "reorder", "artifact", "revision", "span", "locator"])
def test_complete_pg_refuses_nonprimary_binding_drift_atomically(pg, monkeypatch, change):
    command, parent = prepared(pg, monkeypatch)
    data = command.model_dump(mode="json")
    bindings = data["evidence_bindings"]
    if change == "omit":
        bindings.pop(1)
    elif change == "reorder":
        bindings[1], bindings[2] = bindings[2], bindings[1]
    else:
        field = {
            "artifact": "source_artifact_id",
            "revision": "source_revision_id",
            "span": "source_span_ref_id",
            "locator": "source_locator",
        }[change]
        bindings[1][field] = "forged"
    request = AdoptedAssertionWithdrawalCommandV4.model_validate(data)
    before = existing._counts(pg, command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(request)
    assert existing._counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


@pytest.mark.parametrize("stage", ["withdrawal_graph", "withdrawal_receipt"])
def test_complete_pg_rolls_back_each_publication_stage(pg, monkeypatch, stage):
    command, parent = prepared(pg, monkeypatch)
    before = existing._counts(pg, command.world_id)

    def fail(phase):
        if phase == stage:
            raise RuntimeError("injected complete-evidence failure")

    repository = PostgresExistingWorldAdoptionRepository(pg.database, failure_hook=fail)
    with pytest.raises(RuntimeError, match="injected"):
        repository.withdraw_adopted_assertion(command)
    assert existing._counts(pg, command.world_id) == before
    assert pg.world_graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


def test_complete_pg_receipt_cannot_drop_full_set_and_remains_append_only(pg, monkeypatch):
    command, _ = prepared(pg, monkeypatch)
    pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    with pytest.raises(CheckViolation), pg.database.connect() as conn:
        conn.execute(
            "INSERT INTO dungeonmind.adopted_assertion_withdrawals "
            "SELECT (jsonb_populate_record(NULL::dungeonmind.adopted_assertion_withdrawals, "
            "to_jsonb(w) || jsonb_build_object('operation_id', 'invalid:missing-set', "
            "'payload', w.payload - 'evidence_bindings'))).* "
            "FROM dungeonmind.adopted_assertion_withdrawals w WHERE operation_id=%s",
            (command.operation_id,),
        )
    with pytest.raises(RaiseException, match="append-only"), pg.database.connect() as conn:
        conn.execute("DELETE FROM dungeonmind.adopted_assertion_withdrawals")


def test_complete_pg_downgrade_refuses_populated_v4_receipts(pg, monkeypatch, database_url):
    command, _ = prepared(pg, monkeypatch)
    pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    result = existing._alembic(database_url, "downgrade", "0018_adopted_object_withdrawal")
    assert result.returncode != 0
    assert "cannot downgrade populated complete-evidence withdrawal receipts" in result.stderr
    assert (
        pg.existing_world_adoptions.withdraw_adopted_assertion(command).evidence_bindings
        == command.evidence_bindings
    )
