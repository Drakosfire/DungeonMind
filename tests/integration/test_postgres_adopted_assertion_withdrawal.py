from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor

import pytest

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
)
from dungeonmind.contracts.adopted_assertion_withdrawal import (
    AdoptedAssertionWithdrawalCommandV1,
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
from tests.unit.test_existing_world_adoption import (
    ART_A,
    NOW,
    REV_A,
    WORLD_ID,
    graph_reader,
    v2_bundle_bytes,
)
from tests.unit.test_existing_world_adoption_repair import (
    REPAIRED_AT,
    _intent,
    _repairable_bundle,
)

pytestmark = pytest.mark.integration


def _prepared(pg, *, evidence_span: str = "span:postgres-a"):
    bundle = _repairable_bundle()
    graph_payload = copy.deepcopy(bundle.graph_payload)
    for evidence in graph_payload["evidence_refs"]:
        if evidence["evidence_ref_id"] == "ev:a":
            evidence.update(
                {
                    "source_span_ref_id": evidence_span,
                    "source_locator": "fixture://notes-a#paragraph-17",
                    "can_highlight_span": True,
                }
            )
    bundle = bundle.model_copy(update={"graph_payload": graph_payload})
    raw = v2_bundle_bytes(bundle)
    adoption = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=graph_reader(),
    )
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
    command = AdoptedAssertionWithdrawalCommandV1(
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
        source_locator="fixture://notes-a#paragraph-17",
        parent_payload_sha256=canonical_sha256(parent.graph_payload),
        actor="reviewer:postgres-test",
        requested_at=NOW,
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


def test_postgres_withdrawal_is_atomic_idempotent_and_receipt_survives_descendant(pg) -> None:
    command, parent = _prepared(pg)
    receipt = pg.existing_world_adoptions.withdraw_adopted_assertion(command)
    child = pg.world_graph.get_revision(command.world_id, receipt.published_revision_id)
    assert child is not None
    expected = copy.deepcopy(parent.graph_payload)
    expected["relationships"] = [
        item for item in expected["relationships"]
        if item["relationship_id"] != command.relationship_id
    ]
    assert child.graph_payload == expected
    assert (
        pg.world_graph.get_revision(command.world_id, command.expected_parent_revision_id)
        == parent
    )
    first_counts = _counts(pg, command.world_id)
    assert pg.existing_world_adoptions.withdraw_adopted_assertion(command) == receipt
    assert _counts(pg, command.world_id) == first_counts
    conflict = command.model_copy(update={"source_locator": "fixture://forged"})
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


def test_postgres_withdrawal_failure_rolls_back_graph_and_receipt(pg) -> None:
    command, _ = _prepared(pg)
    before_counts = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)

    def fail(stage: str) -> None:
        if stage == "withdrawal_receipt":
            raise RuntimeError("injected after receipt insert")

    repository = PostgresExistingWorldAdoptionRepository(pg.database, failure_hook=fail)
    with pytest.raises(RuntimeError, match="injected after receipt insert"):
        repository.withdraw_adopted_assertion(command)
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_concurrent_withdrawals_have_one_cas_winner(pg) -> None:
    command, _ = _prepared(pg)
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
def test_postgres_forged_bindings_fail_before_mutation(pg, changes) -> None:
    command, _ = _prepared(pg)
    before_counts = _counts(pg, command.world_id)
    before_head = pg.world_graph.get_head(command.world_id)
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(
            command.model_copy(update=changes)
        )
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head


def test_postgres_profile_drift_fails_before_withdrawal_mutation(pg) -> None:
    command, parent = _prepared(pg)
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
    with pytest.raises(PersistenceIntegrityError):
        pg.existing_world_adoptions.withdraw_adopted_assertion(forged)
    assert _counts(pg, command.world_id) == before_counts
    assert pg.world_graph.get_head(command.world_id) == before_head
