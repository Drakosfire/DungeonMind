"""PostgreSQL expected-parent CAS for native knowledge authority."""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.application.vnext.records import StoredKnowledgeRevision
from dungeonmind.domain.errors import (
    ImmutableRevisionConflictError,
    PersistenceIntegrityError,
)
from dungeonmind.infrastructure.postgres.database import PostgresDatabase, jsonb
from dungeonmind.infrastructure.postgres.vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
    _insert_revision,
    _lock_space,
)
from tests.unit.test_vnext_cas_publication import (
    LATER,
    SPACE,
    _materialize_bob,
    genesis_command,
)

pytestmark = pytest.mark.integration


def test_postgres_source_has_no_legacy_authority_vocabulary() -> None:
    banned = re.compile(
        r"\b(world_id|GM|PLAYER|campaign_id|ContributionReview|"
        r"FinalizedReviewPublication|review_materialization)\b"
    )
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "src/dungeonmind/infrastructure/postgres/vnext_knowledge.py",
        "migrations/versions/0008_vnext_knowledge_authority.py",
        "migrations/versions/0009_vnext_publication_receipts.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert banned.search(text) is None, relative


def _repo(database_url: str) -> PostgresKnowledgeRevisionRepository:
    return PostgresKnowledgeRevisionRepository(PostgresDatabase(database_url))


def _counts(database_url: str) -> tuple[int, int]:
    with PostgresDatabase(database_url).connect() as conn:
        revisions = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.knowledge_revisions
            WHERE space_id = %s
            """,
            (SPACE,),
        ).fetchone()
        events = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.knowledge_head_events
            WHERE space_id = %s
            """,
            (SPACE,),
        ).fetchone()
    assert revisions is not None and events is not None
    return int(revisions["n"]), int(events["n"])


def _receipt_count(database_url: str) -> int:
    with PostgresDatabase(database_url).connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.knowledge_publication_receipts
            WHERE space_id = %s
            """,
            (SPACE,),
        ).fetchone()
    assert row is not None
    return int(row["n"])


def test_genesis_child_reconstruction_and_refs(migrated_database: str, pg) -> None:
    del pg
    repo = _repo(migrated_database)
    genesis = repo.publish_revision(genesis_command(origin=None))
    _contribution, _dispositions, materialization = _materialize_bob(repo)
    receipt = publish_governed_materialization(
        materialization, publication_id="publication:integration", repository=repo
    )
    published = repo.get_revision(SPACE, receipt.published_revision_id)
    assert published is not None

    stored = repo.get_revision(SPACE, published.revision.revision_id)
    head = repo.get_head(SPACE)
    events = repo.head_events(SPACE)
    assert stored is not None
    assert stored.revision.model_dump(mode="json") == published.revision.model_dump(mode="json")
    assert stored.graph_payload_sha256 == materialization.graph_payload_sha256
    assert stored.graph_payload == materialization.graph_payload
    assert stored.revision.domain_contract_ref == materialization.command.domain_contract_ref
    assert stored.revision.semantic_profile_ref == materialization.command.semantic_profile_ref
    assert stored.revision.migration_origin_ref is None
    assert head is not None
    assert head.head_revision_id == published.revision.revision_id
    assert [(event.previous_revision_id, event.target_revision_id) for event in events] == [
        (None, genesis.revision.revision_id),
        (genesis.revision.revision_id, published.revision.revision_id),
    ]
    assert _counts(migrated_database) == (2, 2)


def test_stale_parent_leaves_no_child(migrated_database: str, pg) -> None:
    del pg
    repo = _repo(migrated_database)
    genesis = repo.publish_revision(genesis_command())
    stale = genesis_command(
        parent_revision_id="rev:missing",
        expected_parent_revision_id="rev:missing",
        operation_ids=["op:stale"],
        payload={"n": "stale"},
    )
    with pytest.raises(KnowledgeStaleParentRevisionError):
        repo.publish_revision(stale)
    assert repo.get_head(SPACE).head_revision_id == genesis.revision.revision_id  # type: ignore[union-attr]
    assert repo.get_revision(SPACE, revision_from_command(stale).revision_id) is None
    assert _counts(migrated_database) == (1, 1)


def test_same_parent_race_leaves_no_orphan(migrated_database: str, pg) -> None:
    del pg
    setup = _repo(migrated_database)
    genesis = setup.publish_revision(genesis_command())
    parent_id = genesis.revision.revision_id
    left = genesis_command(
        parent_revision_id=parent_id,
        expected_parent_revision_id=parent_id,
        operation_ids=["op:left"],
        payload={"n": "left"},
    )
    right = genesis_command(
        parent_revision_id=parent_id,
        expected_parent_revision_id=parent_id,
        operation_ids=["op:right"],
        payload={"n": "right"},
    )
    left_id = revision_from_command(left).revision_id
    right_id = revision_from_command(right).revision_id
    writers = (_repo(migrated_database), _repo(migrated_database))
    barrier = threading.Barrier(2)
    winners: list[str] = []
    errors: list[BaseException] = []

    def publish(index: int) -> None:
        command = left if index == 0 else right
        try:
            barrier.wait(timeout=5)
            stored = writers[index].publish_revision(command)
        except BaseException as exc:
            errors.append(exc)
        else:
            winners.append(stored.revision.revision_id)

    threads = [threading.Thread(target=publish, args=(index,)) for index in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert len(winners) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], KnowledgeStaleParentRevisionError)
    loser_id = right_id if winners[0] == left_id else left_id
    assert _repo(migrated_database).get_head(SPACE).head_revision_id == winners[0]  # type: ignore[union-attr]
    assert _repo(migrated_database).get_revision(SPACE, loser_id) is None
    assert _counts(migrated_database) == (2, 2)


def test_injected_failure_rolls_back_transaction(migrated_database: str, pg) -> None:
    del pg

    def boom() -> None:
        raise RuntimeError("injected")

    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database), after_revision_insert=boom
    )
    command = genesis_command()
    with pytest.raises(RuntimeError, match="injected"):
        repo.publish_revision(command)
    assert repo.get_head(SPACE) is None
    assert repo.get_revision(SPACE, revision_from_command(command).revision_id) is None
    assert repo.head_events(SPACE) == ()
    assert _counts(migrated_database) == (0, 0)


def test_exact_replay_and_changed_retry_are_receipt_first(
    migrated_database: str, pg
) -> None:
    del pg
    repo = _repo(migrated_database)
    genesis = repo.publish_revision(genesis_command())
    command = genesis_command(
        parent_revision_id=genesis.revision.revision_id,
        expected_parent_revision_id=genesis.revision.revision_id,
        operation_ids=["op:receipt"],
    )
    first = repo.publish_publication(command, "publication:exact")
    events_before = len(repo.head_events(SPACE))
    second = repo.publish_publication(command, "publication:exact")
    assert second == first
    assert len(repo.head_events(SPACE)) == events_before
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        repo.publish_publication(
            command.model_copy(update={"operation_ids": ["op:changed"]}),
            "publication:exact",
        )
    assert _receipt_count(migrated_database) == 1


def test_same_parent_different_publication_ids_have_one_cas_winner(
    migrated_database: str, pg
) -> None:
    del pg
    setup = _repo(migrated_database)
    genesis = setup.publish_revision(genesis_command())
    parent_id = genesis.revision.revision_id
    commands = [
        genesis_command(
            parent_revision_id=parent_id,
            expected_parent_revision_id=parent_id,
            operation_ids=[f"op:race:{side}"],
            payload={"side": side},
        )
        for side in ("left", "right")
    ]
    barrier = threading.Barrier(2)
    winners: list[str] = []
    errors: list[BaseException] = []

    def publish(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            receipt = _repo(migrated_database).publish_publication(
                commands[index], f"publication:race:{index}"
            )
        except BaseException as exc:
            errors.append(exc)
        else:
            winners.append(receipt.published_revision_id)

    threads = [threading.Thread(target=publish, args=(index,)) for index in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert len(winners) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], KnowledgeStaleParentRevisionError)
    assert _receipt_count(migrated_database) == 1


def test_receipt_corruption_fails_closed(migrated_database: str, pg) -> None:
    del pg
    repo = _repo(migrated_database)
    receipt = repo.publish_publication(genesis_command(), "publication:corrupt")
    with PostgresDatabase(migrated_database).connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.knowledge_publication_receipts
            SET record_fingerprint = 'tampered'
            WHERE space_id = %s AND publication_id = %s
            """,
            (SPACE, "publication:corrupt"),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="receipt fingerprint"):
        repo.get_publication_receipt(SPACE, receipt.publication_id)


def test_post_commit_response_loss_recovers_by_receipt(
    migrated_database: str, pg
) -> None:
    del pg
    real = _repo(migrated_database)
    real.publish_revision(genesis_command())
    _contribution, _dispositions, materialization = _materialize_bob(real)

    class ResponseLoss:
        def publish_publication(self, command, publication_id):
            real.publish_publication(command, publication_id)
            raise RuntimeError("response lost after commit")

        def get_publication_receipt(self, space_id, publication_id):
            return real.get_publication_receipt(space_id, publication_id)

        def get_revision(self, space_id, revision_id):
            return real.get_revision(space_id, revision_id)

    receipt = publish_governed_materialization(
        materialization,
        publication_id="publication:response-loss",
        repository=ResponseLoss(),
    )
    assert receipt.publication_id == "publication:response-loss"
    assert _receipt_count(migrated_database) == 2


def test_conflicting_envelope_and_corrupt_rows_fail_closed(migrated_database: str, pg) -> None:
    del pg
    command = genesis_command()
    expected = revision_from_command(command)
    planted = expected.model_copy(update={"created_at": LATER})
    database = PostgresDatabase(migrated_database)
    with database.transaction() as conn:
        _lock_space(conn, SPACE, created_at=LATER)
        _insert_revision(conn, StoredKnowledgeRevision.seal(planted, command.graph_payload))
    repo = _repo(migrated_database)
    with pytest.raises(ImmutableRevisionConflictError):
        repo.publish_revision(command)
    stored = repo.get_revision(SPACE, expected.revision_id)
    assert stored is not None
    assert stored.revision.created_at == LATER
    assert repo.get_head(SPACE) is None
    assert _counts(migrated_database) == (1, 0)

    published = repo.publish_revision(genesis_command(operation_ids=["op:clean"]))
    with database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.knowledge_revisions
            SET record_fingerprint = 'tampered'
            WHERE space_id = %s AND revision_id = %s
            """,
            (SPACE, published.revision.revision_id),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="record_fingerprint"):
        repo.get_revision(SPACE, published.revision.revision_id)

    with database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.knowledge_revisions
            SET graph_payload = %s
            WHERE space_id = %s AND revision_id = %s
            """,
            (jsonb({"tampered": True}), SPACE, expected.revision_id),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError):
        repo.get_revision(SPACE, expected.revision_id)
