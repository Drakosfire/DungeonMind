"""Graph revision / head guarantees, proven against the in-memory adapter.

These tests pin the semantics the PostgreSQL adapter must reproduce (PR B):
immutable content-addressed revisions, atomic head publication, stale-parent
rejection, failed publishes leaving the old head readable, auditable rollback.
"""

import pytest

from dungeonmind.domain import canonical_sha256
from dungeonmind.domain.errors import RevisionNotFoundError, StaleParentRevisionError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository

from ..conftest import FIXED_LATER, FIXED_NOW, WORLD_ID, make_publish


@pytest.fixture
def repo() -> InMemoryWorldGraphRepository:
    return InMemoryWorldGraphRepository()


def test_first_publish_advances_head_and_preserves_hash(repo: InMemoryWorldGraphRepository) -> None:
    payload = {"world_id": WORLD_ID, "nodes": [{"object_id": "obj:1"}]}
    envelope = repo.publish_revision(make_publish(payload=payload))

    assert envelope.revision_id.startswith("rev:")
    assert envelope.graph_payload_sha256 == canonical_sha256(payload)

    head = repo.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == envelope.revision_id

    stored = repo.get_revision(WORLD_ID, envelope.revision_id)
    assert stored is not None
    assert stored.graph_payload == payload
    assert stored.revision.graph_payload_sha256 == envelope.graph_payload_sha256


def test_linear_history_publishes(repo: InMemoryWorldGraphRepository) -> None:
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    rev2 = repo.publish_revision(
        make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    )
    assert rev2.parent_revision_id == rev1.revision_id
    assert repo.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]


def test_stale_parent_rejected_and_old_head_survives(repo: InMemoryWorldGraphRepository) -> None:
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    repo.publish_revision(
        make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    )

    with pytest.raises(StaleParentRevisionError) as excinfo:
        repo.publish_revision(make_publish(parent=None, expected=None, payload={"v": 3}))
    assert excinfo.value.details["actual_head_revision_id"] != rev1.revision_id

    head = repo.get_head(WORLD_ID)
    assert head is not None
    assert repo.get_revision(WORLD_ID, head.head_revision_id) is not None


def test_concurrent_publish_second_loses(repo: InMemoryWorldGraphRepository) -> None:
    first = repo.publish_revision(make_publish(payload={"race": 1}))
    with pytest.raises(StaleParentRevisionError):
        repo.publish_revision(make_publish(payload={"race": 2}))
    assert repo.get_head(WORLD_ID).head_revision_id == first.revision_id  # type: ignore[union-attr]


def test_republish_after_rollback_is_idempotent(repo: InMemoryWorldGraphRepository) -> None:
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    command_v2 = make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    rev2 = repo.publish_revision(command_v2)

    repo.rollback_head(WORLD_ID, rev1.revision_id, updated_at=FIXED_LATER)
    assert repo.get_head(WORLD_ID).head_revision_id == rev1.revision_id  # type: ignore[union-attr]

    replayed = repo.publish_revision(command_v2)
    assert replayed.revision_id == rev2.revision_id
    assert repo.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]


def test_rollback_to_missing_revision_fails(repo: InMemoryWorldGraphRepository) -> None:
    repo.publish_revision(make_publish())
    with pytest.raises(RevisionNotFoundError):
        repo.rollback_head(WORLD_ID, "rev:does-not-exist", updated_at=FIXED_NOW)


def test_failed_publish_never_creates_revision(repo: InMemoryWorldGraphRepository) -> None:
    with pytest.raises(StaleParentRevisionError):
        repo.publish_revision(make_publish(world_id="world:ghost", expected="rev:imagined"))
    assert repo.get_head("world:ghost") is None


def test_timestamp_is_never_head_authority(repo: InMemoryWorldGraphRepository) -> None:
    """A later wall-clock must not beat the CAS parent check."""
    rev1 = repo.publish_revision(make_publish(payload={"v": 1}))
    rev2 = repo.publish_revision(make_publish(parent=rev1.revision_id, payload={"v": 2}))
    assert repo.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]
    repo.rollback_head(WORLD_ID, rev1.revision_id, updated_at=FIXED_LATER)
    head = repo.get_head(WORLD_ID)
    assert head.head_revision_id == rev1.revision_id  # type: ignore[union-attr]
