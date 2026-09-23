"""PostgreSQL authority proofs for V5.4 prospective publication."""

from __future__ import annotations

import threading
from typing import Any, cast

import pytest
from psycopg.errors import ForeignKeyViolation

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.materialization import materialize_governed_revision
from dungeonmind.application.vnext.prospective import (
    publish_prospective_contribution,
    resolve_prospective_contribution,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
)
from tests.unit.test_vnext_cas_publication import SPACE, _parsed_parent, genesis_command
from tests.unit.test_vnext_governed_materialization import _lab_descriptors
from tests.unit.test_vnext_prospective_publication import (
    _accepted,
    _contribution,
    _entity,
    _publication,
)

pytestmark = pytest.mark.integration


def _repo(database_url: str) -> PostgresKnowledgeRevisionRepository:
    return PostgresKnowledgeRevisionRepository(PostgresDatabase(database_url))


def _setup(database_url: str):
    repo = _repo(database_url)
    repo.publish_revision(genesis_command())
    return repo, _parsed_parent(cast(Any, repo))


def _publish(repo, parent, contribution, publication_id):
    contract, profile = _lab_descriptors()
    return publish_prospective_contribution(
        parent=parent,
        prospective_contribution=contribution,
        dispositions=_accepted(*(item.item_id for item in contribution.items)),
        publication=_publication(parent.revision_id),
        publication_id=publication_id,
        domain_contract=contract,
        semantic_profile=profile,
        repository=repo,
    )


def _counts(database_url: str) -> tuple[int, int, int, int]:
    with PostgresDatabase(database_url).connect() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM dungeonmind.knowledge_revisions
                 WHERE space_id = %s) AS revisions,
              (SELECT COUNT(*) FROM dungeonmind.knowledge_head_events
                 WHERE space_id = %s) AS events,
              (SELECT COUNT(*) FROM dungeonmind.knowledge_publication_receipts
                 WHERE space_id = %s) AS receipts,
              (SELECT COUNT(*)
                 FROM dungeonmind.knowledge_prospective_publication_results
                 WHERE space_id = %s) AS results
            """,
            (SPACE, SPACE, SPACE, SPACE),
        ).fetchone()
    assert row is not None
    return tuple(int(row[key]) for key in ("revisions", "events", "receipts", "results"))  # type: ignore[return-value]


def test_fresh_exact_replay_and_replay_after_descendant(migrated_database: str, pg) -> None:
    del pg
    repo, parent = _setup(migrated_database)
    contribution = _contribution([_entity()])
    first = _publish(repo, parent, contribution, "prepared:replay")
    replay = _publish(repo, parent, contribution, "prepared:replay")
    assert replay == first
    first_revision_id = first.publication_receipt.published_revision_id
    descendant = genesis_command(
        parent_revision_id=first_revision_id,
        expected_parent_revision_id=first_revision_id,
        operation_ids=["op:descendant"],
        payload={"descendant": True},
    )
    descendant_receipt = repo.publish_publication(descendant, "prepared:descendant")
    replay_after_descendant = _publish(repo, parent, contribution, "prepared:replay")
    assert replay_after_descendant == first
    assert repo.get_head(SPACE).head_revision_id == descendant_receipt.published_revision_id  # type: ignore[union-attr]
    assert _counts(migrated_database) == (3, 3, 2, 1)


def test_changed_request_conflicts(migrated_database: str, pg) -> None:
    del pg
    repo, parent = _setup(migrated_database)
    first = _contribution([_entity(client_op_id="first")])
    _publish(repo, parent, first, "prepared:claimed")
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _publish(
            repo,
            parent,
            _contribution([_entity(client_op_id="changed")]),
            "prepared:claimed",
        )



def test_plain_v53_claim_conflicts(migrated_database: str, pg) -> None:
    del pg
    plain_repo, plain_parent = _setup(migrated_database)
    contribution = _contribution([_entity()])
    resolved = resolve_prospective_contribution(
        prospective_contribution=contribution,
        dispositions=_accepted("create-1"),
        publication_id="prepared:plain",
        publication=_publication(plain_parent.revision_id),
        parent=plain_parent,
    )
    contract, profile = _lab_descriptors()
    materialized = materialize_governed_revision(
        parent=plain_parent,
        contribution=resolved.canonical_contribution,
        dispositions=_accepted("create-1"),
        publication=_publication(plain_parent.revision_id),
        domain_contract=contract,
        semantic_profile=profile,
    )
    plain_repo.publish_publication(materialized.command, "prepared:plain")
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _publish(plain_repo, plain_parent, contribution, "prepared:plain")


def test_same_id_same_request_concurrently_converges(migrated_database: str, pg) -> None:
    del pg
    _setup_repo, parent = _setup(migrated_database)
    contribution = _contribution([_entity()])
    barrier = threading.Barrier(2)
    results = []
    errors: list[BaseException] = []

    def publish() -> None:
        try:
            barrier.wait(timeout=5)
            results.append(
                _publish(
                    _repo(migrated_database),
                    parent,
                    contribution,
                    "prepared:concurrent-same",
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 2 and results[0] == results[1]
    assert _counts(migrated_database) == (2, 2, 1, 1)


def test_same_id_changed_requests_concurrently_conflict(migrated_database: str, pg) -> None:
    del pg
    _setup_repo, parent = _setup(migrated_database)
    contributions = [
        _contribution([_entity(client_op_id=f"entity-{side}")])
        for side in ("left", "right")
    ]
    barrier = threading.Barrier(2)
    results = []
    errors: list[BaseException] = []

    def publish(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(
                _publish(
                    _repo(migrated_database),
                    parent,
                    contributions[index],
                    "prepared:concurrent-changed",
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(index,)) for index in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], KnowledgePublicationIdempotencyConflictError)
    assert _counts(migrated_database) == (2, 2, 1, 1)


def test_different_ids_same_parent_preserve_cas(migrated_database: str, pg) -> None:
    del pg
    _setup_repo, parent = _setup(migrated_database)
    barrier = threading.Barrier(2)
    results = []
    errors: list[BaseException] = []

    def publish(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(
                _publish(
                    _repo(migrated_database),
                    parent,
                    _contribution([_entity(client_op_id=f"entity-{index}")]),
                    f"prepared:different:{index}",
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(index,)) for index in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], KnowledgeStaleParentRevisionError)
    assert _counts(migrated_database) == (2, 2, 1, 1)


def test_failure_after_result_insert_rolls_back_everything(migrated_database: str, pg) -> None:
    del pg
    setup, parent = _setup(migrated_database)

    def boom() -> None:
        raise RuntimeError("after result insert")

    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database), after_prospective_result_insert=boom
    )
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        _publish(
            repo,
            parent,
            _contribution([_entity()]),
            "prepared:rollback",
        )
    assert setup.get_head(SPACE).head_revision_id == parent.revision_id  # type: ignore[union-attr]
    assert _counts(migrated_database) == (1, 1, 0, 0)


def test_post_commit_response_loss_recovers_mapping(migrated_database: str, pg) -> None:
    del pg
    real, parent = _setup(migrated_database)

    class ResponseLoss:
        def publish_prospective_publication(self, *args):
            real.publish_prospective_publication(*args)
            raise RuntimeError("response lost")

        def get_prospective_publication(self, *args):
            return real.get_prospective_publication(*args)

        def get_publication_receipt(self, *args):
            return real.get_publication_receipt(*args)

        def get_revision(self, *args):
            return real.get_revision(*args)

    result = _publish(
        ResponseLoss(),
        parent,
        _contribution([_entity()]),
        "prepared:response-loss",
    )
    assert result.prospective_result.results[0].client_op_id == "entity-op"
    assert _counts(migrated_database) == (2, 2, 1, 1)


def test_corrupt_result_fails_closed_and_fk_prevents_orphan(
    migrated_database: str, pg
) -> None:
    del pg
    repo, parent = _setup(migrated_database)
    _publish(repo, parent, _contribution([_entity()]), "prepared:corrupt")
    database = PostgresDatabase(migrated_database)
    with database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.knowledge_prospective_publication_results
            SET record_fingerprint = 'tampered'
            WHERE space_id = %s AND publication_id = %s
            """,
            (SPACE, "prepared:corrupt"),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError, match="fingerprint"):
        repo.get_prospective_publication(SPACE, "prepared:corrupt")

    with database.connect() as conn, pytest.raises(ForeignKeyViolation):
        conn.execute(
            """
                INSERT INTO dungeonmind.knowledge_prospective_publication_results (
                    schema_version, space_id, publication_id,
                    prospective_request_sha256, published_revision_id,
                    result_bindings, status, record_fingerprint
                ) VALUES (%s, %s, %s, %s, %s, '[]'::jsonb, 'published', %s)
                """,
            (
                "dm_knowledge_prospective_publication_result_v1",
                SPACE,
                "prepared:orphan",
                "0" * 64,
                parent.revision_id,
                "0" * 64,
            ),
        )
