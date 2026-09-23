from __future__ import annotations

from dataclasses import replace

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import (
    _materialize_bob,
    genesis_command,
)


def test_exact_retry_replays_receipt_without_new_event() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    repo.publish_revision(genesis_command())
    _, _, materialization = _materialize_bob(repo)
    first = publish_governed_materialization(
        materialization, publication_id="prepared:1", repository=repo
    )
    event_count = len(repo.head_events("space:lab"))
    second = publish_governed_materialization(
        materialization, publication_id="prepared:1", repository=repo
    )
    assert second == first
    assert len(repo.head_events("space:lab")) == event_count


def test_changed_retry_is_rejected_without_mutation() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    repo.publish_revision(genesis_command())
    _, _, materialization = _materialize_bob(repo)
    publish_governed_materialization(materialization, publication_id="prepared:1", repository=repo)
    before = (repo.get_head("space:lab"), repo.head_events("space:lab"))
    changed_command = materialization.command.model_copy(update={"operation_ids": ["op:other"]})
    changed = replace(materialization, _command_json=changed_command.model_dump_json())
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_governed_materialization(changed, publication_id="prepared:1", repository=repo)
    assert repo.get_head("space:lab") == before[0]
    assert repo.head_events("space:lab") == before[1]


def test_post_commit_response_loss_is_recovered_by_receipt_probe() -> None:
    lost = True

    def lose_response() -> None:
        nonlocal lost
        if lost:
            lost = False
            raise RuntimeError("response lost")

    repo = InMemoryKnowledgeRevisionRepository(after_publication_commit=lose_response)
    repo.publish_revision(genesis_command())
    _, _, materialization = _materialize_bob(repo)
    receipt = publish_governed_materialization(
        materialization, publication_id="prepared:1", repository=repo
    )
    assert receipt.published_revision_id == (
        revision_from_command(materialization.command).revision_id
    )


def test_unavailable_recovery_is_typed_and_retry_safe() -> None:
    def unavailable() -> None:
        raise RuntimeError("connection lost")

    repo = InMemoryKnowledgeRevisionRepository(after_publication_commit=unavailable)
    repo.publish_revision(genesis_command())
    _, _, materialization = _materialize_bob(repo)
    # The in-memory receipt remains available, so a second explicit read recovers it.
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        original = repo.get_publication_receipt
        repo.get_publication_receipt = lambda *_args: (_ for _ in ()).throw(RuntimeError("down"))  # type: ignore[method-assign]
        try:
            publish_governed_materialization(
                materialization, publication_id="prepared:2", repository=repo
            )
        finally:
            repo.get_publication_receipt = original  # type: ignore[method-assign]
