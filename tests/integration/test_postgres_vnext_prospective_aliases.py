"""Real atomicity and replay of entity creation with evidence-bearing aliases."""

from __future__ import annotations

import threading

import pytest

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    ProspectivePublicationIntegrityError,
)
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.vnext_knowledge import PostgresKnowledgeRevisionRepository
from tests.integration.test_postgres_vnext_prospective_publication import _counts, _repo, _setup
from tests.unit.test_vnext_cas_publication import SPACE
from tests.unit.test_vnext_prospective_aliases import alias_request, publish_alias

pytestmark = pytest.mark.integration


def test_atomic_alias_content_replay_and_changed_alias_conflict(migrated_database, pg):
    repo, parent = _setup(migrated_database)
    result = publish_alias(repo, parent)
    assert publish_alias(repo, parent) == result
    stored = repo.get_revision(SPACE, result.publication_receipt.published_revision_id)
    target = next(
        b.durable_id for b in result.prospective_result.results if b.result_kind == "entity"
    )
    assert stored.graph_payload["aliases"][0] == {
        "schema_version": "dm_identity_alias_v1",
        "alias_id": "alias:one",
        "entity_id": target,
        "alias_text": "  Exact Alias  ",
        "evidence_ref_ids": ["ev:lab"],
        "standing": "established",
    }
    before = _counts(migrated_database)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_alias(repo, parent, alias_request("changed"))
    assert _counts(migrated_database) == before == (2, 2, 1, 1)


@pytest.mark.parametrize("conflicting", [False, True])
def test_concurrent_same_publication_preserves_alias_replay(migrated_database, pg, conflicting):
    _, parent = _setup(migrated_database)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def publish(index):
        try:
            barrier.wait(timeout=10)
            results.append(
                publish_alias(
                    _repo(migrated_database),
                    parent,
                    alias_request(str(index) if conflicting else "same"),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(i,)) for i in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert all(not thread.is_alive() for thread in threads)
    if conflicting:
        assert len(results) == len(errors) == 1
        assert isinstance(errors[0], KnowledgePublicationIdempotencyConflictError)
    else:
        assert not errors and len(results) == 2 and results[0] == results[1]
    assert _counts(migrated_database) == (2, 2, 1, 1)


def test_alias_transaction_rolls_back_revision_head_event_receipt_and_result(migrated_database, pg):
    real, parent = _setup(migrated_database)

    def fail():
        raise RuntimeError("injected after result insert")

    repo = PostgresKnowledgeRevisionRepository(
        PostgresDatabase(migrated_database), after_prospective_result_insert=fail
    )
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        publish_alias(repo, parent)
    assert _counts(migrated_database) == (1, 1, 0, 0)
    assert real.get_head(SPACE).head_revision_id == parent.revision_id


def test_alias_response_loss_recovers_and_stale_parent_never_advances(migrated_database, pg):
    real, parent = _setup(migrated_database)

    class LostResponse:
        def __getattr__(self, name):
            return getattr(real, name)

        def publish_prospective_publication(self, *args):
            real.publish_prospective_publication(*args)
            raise RuntimeError("lost committed response")

    first = publish_alias(LostResponse(), parent)
    assert publish_alias(real, parent) == first
    before = _counts(migrated_database)
    with pytest.raises(KnowledgeStaleParentRevisionError):
        publish_alias(real, parent, alias_request("other"), publication_id="prepared:stale")
    assert _counts(migrated_database) == before


def test_absent_alias_evidence_rejects_before_any_sql_mutation(migrated_database, pg):
    repo, parent = _setup(migrated_database)
    request = alias_request()
    request.aliases[0].evidence_ref_ids = ["ev:other-space"]
    with pytest.raises(ProspectivePublicationIntegrityError):
        publish_alias(repo, parent, request)
    assert _counts(migrated_database) == (1, 1, 0, 0)
    assert repo.get_head(SPACE).head_revision_id == parent.revision_id
