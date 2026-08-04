"""Owning-boundary proofs for finalized-review CAS publication."""

from __future__ import annotations

import copy
import inspect
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application import (
    FinalizedReviewPublication,
    publish_finalized_review,
)
from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.contribution_review import ContributionReviewState
from dungeonmind.contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ContributionMaterializationError,
    ContributionReviewNotFoundError,
    HeadNotFoundError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GRAPH_FIXTURE = FIXTURES / "dungeonmind_dnd/gatewatch-world-graph-v3.json"
PROFILE_DESCRIPTOR = (
    Path(__file__).resolve().parents[2] / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
)
STATE_FIXTURE = FIXTURES / "contribution_reviews/tripod-null-calf-finalized-review-state-v1.json"
MATERIALIZED_FIXTURE = (
    FIXTURES / "contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json"
)
WORLD_ID = "world:synthetic-gatewatch"
REVIEW_ID = "review:cff0162637b428e634e8cccaa9958dc2"
PARENT_REVISION_ID = "rev:f2d5164c176289c5f3df7e68b4f0e46d"
PUBLISHED_REVISION_ID = "rev:6e02bd224f6b5616534f10026c8b9679"
PAYLOAD_SHA256 = "75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5"
PUBLISHED_AT = datetime(2026, 8, 3, 23, 0, tzinfo=UTC)


def _parent_inputs() -> tuple[StoredGraphRevision, UnionGraphV3SnapshotReader]:
    graph = json.loads(GRAPH_FIXTURE.read_text(encoding="utf-8"))
    payload = graph["graph_payload"]
    metadata = graph["revision_metadata"]
    digest = canonical_sha256(payload)
    revision = WorldGraphRevision(
        world_id=graph["world_id"],
        revision_id=compute_revision_id(
            world_id=graph["world_id"],
            parent_revision_id=metadata["parent_revision_id"],
            operation_ids=metadata["operation_ids"],
            graph_schema=graph["graph_schema"],
            graph_payload_sha256=digest,
        ),
        parent_revision_id=metadata["parent_revision_id"],
        created_at=metadata["created_at"],
        operation_ids=metadata["operation_ids"],
        graph_schema=graph["graph_schema"],
        graph_payload_sha256=digest,
    )
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(PROFILE_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    reader = UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    return StoredGraphRevision(revision=revision, graph_payload=payload), reader


def _state() -> ContributionReviewState:
    return ContributionReviewState.model_validate(
        json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    )


def _seed_graph(
    repository: InMemoryWorldGraphRepository,
) -> tuple[StoredGraphRevision, UnionGraphV3SnapshotReader]:
    parent, reader = _parent_inputs()
    repository.publish_revision(
        PublishRevisionCommand(
            world_id=parent.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=list(parent.revision.operation_ids),
            graph_schema=parent.revision.graph_schema,
            graph_payload=copy.deepcopy(parent.graph_payload),
            created_at=parent.revision.created_at,
        )
    )
    return parent, reader


def _seed_review() -> tuple[
    InMemoryContributionReviewRepository, ContributionReviewState
]:
    contributions = InMemoryContributionRepository()
    reviews = InMemoryContributionReviewRepository(contributions)
    state = _state()
    persisted = reviews.finalize(state)
    return reviews, persisted


class _SpyWorldGraphRepository:
    def __init__(
        self,
        inner: InMemoryWorldGraphRepository,
        *,
        before_publish: Callable[[], None] | None = None,
        alter_return: Callable[[WorldGraphRevision], WorldGraphRevision] | None = None,
        raise_after_publish: bool = False,
    ) -> None:
        self.inner = inner
        self.get_head_calls = 0
        self.get_revision_calls = 0
        self.publish_calls = 0
        self.before_publish = before_publish
        self.alter_return = alter_return
        self.raise_after_publish = raise_after_publish

    def get_head(self, world_id: str):
        self.get_head_calls += 1
        return self.inner.get_head(world_id)

    def get_revision(self, world_id: str, revision_id: str):
        self.get_revision_calls += 1
        return self.inner.get_revision(world_id, revision_id)

    def publish_revision(self, command: PublishRevisionCommand):
        self.publish_calls += 1
        if self.before_publish is not None:
            hook = self.before_publish
            self.before_publish = None
            hook()
        revision = self.inner.publish_revision(command)
        if self.raise_after_publish:
            raise RuntimeError("synthetic response loss")
        if self.alter_return is not None:
            return self.alter_return(revision)
        return revision


class _HeadBarrierWorldGraphRepository(_SpyWorldGraphRepository):
    def __init__(
        self,
        inner: InMemoryWorldGraphRepository,
        barrier: threading.Barrier,
    ) -> None:
        super().__init__(inner)
        self._barrier = barrier
        self._head_observations = 0
        self._head_lock = threading.Lock()

    def get_head(self, world_id: str):
        with self._head_lock:
            self._head_observations += 1
            observation = self._head_observations
        if observation <= 2:
            self._barrier.wait(timeout=5)
        return super().get_head(world_id)


class _RejectingReader:
    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]):
        del graph_schema, graph_payload
        raise ValueError("synthetic reader rejection")


class _CorruptReviewRepository:
    def get(self, world_id: str, review_id: str):
        del world_id, review_id
        return object()


class _MissingParentWorldGraphRepository:
    def __init__(self, head_revision_id: str) -> None:
        self.head = WorldGraphHead(
            world_id=WORLD_ID,
            head_revision_id=head_revision_id,
            updated_at=PUBLISHED_AT,
        )
        self.publish_calls = 0

    def get_head(self, world_id: str):
        assert world_id == WORLD_ID
        return self.head.model_copy(deep=True)

    def get_revision(self, world_id: str, revision_id: str):
        assert world_id == WORLD_ID
        assert revision_id == self.head.head_revision_id
        return None

    def publish_revision(self, command: PublishRevisionCommand):
        del command
        self.publish_calls += 1
        raise AssertionError("publish must not be reached")


def _publish(
    reviews: Any,
    repository: InMemoryWorldGraphRepository | _SpyWorldGraphRepository,
    reader: Any,
    *,
    published_at: datetime = PUBLISHED_AT,
    review_id: str = REVIEW_ID,
) -> FinalizedReviewPublication:
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=published_at,
        review_repository=reviews,
        world_graph_repository=repository,
        graph_reader=reader,
    )


@pytest.mark.conformance
def test_exact_tripod_publication_maps_one_review_to_one_revision() -> None:
    graph = InMemoryWorldGraphRepository()
    parent, reader = _seed_graph(graph)
    reviews, state = _seed_review()
    before_review = reviews.get(WORLD_ID, REVIEW_ID)
    assert before_review is not None

    result = _publish(reviews, graph, reader)

    assert result == FinalizedReviewPublication(
        world_id=WORLD_ID,
        review_id=REVIEW_ID,
        reviewed_contribution_id="contrib:65cdb14d13c40e5b8725fd5111509854",
        review_intent_sha256=state.record.review_intent_sha256,
        confirmation_id="confirm:fa0d200c9922caf3c7e925b320cf9dae",
        operation_id="reviewop:11111111111111111111111111111111",
        expected_parent_revision_id=PARENT_REVISION_ID,
        published_revision_id=PUBLISHED_REVISION_ID,
        graph_schema="dm_union_graph_v3",
        graph_payload_sha256=PAYLOAD_SHA256,
        published_at=PUBLISHED_AT,
    )
    published = graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert published is not None
    assert published.graph_payload == json.loads(
        MATERIALIZED_FIXTURE.read_text(encoding="utf-8")
    )
    assert published.revision.parent_revision_id == PARENT_REVISION_ID
    assert published.revision.operation_ids == [state.record.operation_id]
    assert published.revision.graph_schema == "dm_union_graph_v3"
    assert published.revision.graph_payload_sha256 == PAYLOAD_SHA256
    assert graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]
    after_review = reviews.get(WORLD_ID, REVIEW_ID)
    assert after_review is not None
    assert after_review.model_dump(mode="json") == before_review.model_dump(mode="json")
    assert parent.revision.revision_id == PARENT_REVISION_ID


@pytest.mark.conformance
def test_public_seam_accepts_only_durable_review_identifiers() -> None:
    names = set(inspect.signature(publish_finalized_review).parameters)
    assert names == {
        "world_id",
        "review_id",
        "published_at",
        "review_repository",
        "world_graph_repository",
        "graph_reader",
    }
    assert not names & {
        "state",
        "contribution",
        "materialization",
        "graph_payload",
        "parent",
        "expected_parent_revision_id",
        "operation_ids",
        "command",
    }


@pytest.mark.conformance
def test_missing_durable_review_cannot_publish() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    # Deliberately use a separate empty review store with the same otherwise
    # valid identifiers.
    empty_reviews = InMemoryContributionReviewRepository(InMemoryContributionRepository())
    before = graph.get_head(WORLD_ID)

    with pytest.raises(ContributionReviewNotFoundError) as exc:
        _publish(empty_reviews, graph, reader)

    assert exc.value.details == {"world_id": WORLD_ID, "review_id": REVIEW_ID}
    assert graph.get_head(WORLD_ID) == before
    assert reviews.get(WORLD_ID, REVIEW_ID) is not None


@pytest.mark.conformance
def test_invalid_durable_review_is_a_sanitized_integrity_failure() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)

    with pytest.raises(PersistenceIntegrityError) as exc:
        _publish(_CorruptReviewRepository(), graph, reader)

    assert exc.value.details == {"reason": "finalized_review_reload_validation"}
    assert "synthetic" not in str(exc.value)
    assert graph.get_head(WORLD_ID).head_revision_id == PARENT_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_missing_head_fails_before_parent_load_or_publish() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _parent_inputs()
    reviews, _state_value = _seed_review()

    with pytest.raises(HeadNotFoundError):
        _publish(reviews, graph, reader)

    assert graph.get_head(WORLD_ID) is None


@pytest.mark.conformance
def test_missing_exact_parent_fails_without_publish() -> None:
    _parent, reader = _parent_inputs()
    reviews, _state_value = _seed_review()
    graph = _MissingParentWorldGraphRepository(PARENT_REVISION_ID)

    with pytest.raises(RevisionNotFoundError):
        _publish(reviews, graph, reader)

    assert graph.publish_calls == 0


@pytest.mark.conformance
def test_known_stale_parent_fails_before_materialization_or_publish() -> None:
    graph = InMemoryWorldGraphRepository()
    parent, _reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision.revision_id,
            expected_parent_revision_id=parent.revision.revision_id,
            operation_ids=["op:competing-writer"],
            graph_schema="dm_union_graph_v3",
            graph_payload=copy.deepcopy(parent.graph_payload),
            created_at=PUBLISHED_AT,
        )
    )
    spy = _SpyWorldGraphRepository(graph)

    with pytest.raises(StaleParentRevisionError):
        _publish(reviews, spy, _RejectingReader())

    assert spy.get_head_calls == 1
    assert spy.get_revision_calls == 0
    assert spy.publish_calls == 0


@pytest.mark.conformance
def test_materialization_failure_is_write_free() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, _reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    spy = _SpyWorldGraphRepository(graph)

    with pytest.raises(ContributionMaterializationError) as exc:
        _publish(reviews, spy, _RejectingReader())

    assert exc.value.details["reason"] == "parent_reload_validation"
    assert spy.get_head_calls == 1
    assert spy.get_revision_calls == 1
    assert spy.publish_calls == 0
    assert graph.get_head(WORLD_ID).head_revision_id == PARENT_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_cas_race_rejects_stale_materialization_without_a_child() -> None:
    graph = InMemoryWorldGraphRepository()
    parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()

    def competitor_wins() -> None:
        graph.publish_revision(
            PublishRevisionCommand(
                world_id=WORLD_ID,
                parent_revision_id=parent.revision.revision_id,
                expected_parent_revision_id=parent.revision.revision_id,
                operation_ids=["op:race-winner"],
                graph_schema="dm_union_graph_v3",
                graph_payload=copy.deepcopy(parent.graph_payload),
                created_at=PUBLISHED_AT,
            )
        )

    spy = _SpyWorldGraphRepository(graph, before_publish=competitor_wins)
    with pytest.raises(StaleParentRevisionError):
        _publish(reviews, spy, reader)

    assert spy.publish_calls == 1
    assert graph.get_head(WORLD_ID).head_revision_id != PARENT_REVISION_ID  # type: ignore[union-attr]
    assert graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None


@pytest.mark.conformance
def test_concurrent_same_review_calls_have_one_winner_and_one_stale_loser() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    repository = _HeadBarrierWorldGraphRepository(graph, threading.Barrier(2))
    outcomes: list[object] = []

    def call() -> None:
        try:
            outcomes.append(_publish(reviews, repository, reader))
        except BaseException as exc:
            outcomes.append(exc)

    first = threading.Thread(target=call)
    second = threading.Thread(target=call)
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive() and not second.is_alive()
    assert sum(isinstance(item, FinalizedReviewPublication) for item in outcomes) == 1
    assert sum(isinstance(item, StaleParentRevisionError) for item in outcomes) == 1
    assert graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_immediate_replay_after_success_is_stale_not_idempotent_success() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    before = graph.get_head(WORLD_ID)

    with pytest.raises(StaleParentRevisionError):
        _publish(reviews, graph, _RejectingReader())

    assert first.published_revision_id == PUBLISHED_REVISION_ID
    assert graph.get_head(WORLD_ID) == before


@pytest.mark.conformance
def test_explicit_rollback_allows_same_content_addressed_revision_replay() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    graph.rollback_head(WORLD_ID, PARENT_REVISION_ID, updated_at=PUBLISHED_AT)

    replay = _publish(reviews, graph, reader, published_at=PUBLISHED_AT)

    assert replay.published_revision_id == first.published_revision_id == PUBLISHED_REVISION_ID
    assert graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_success_path_has_no_post_commit_repository_read() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    spy = _SpyWorldGraphRepository(graph)

    result = _publish(reviews, spy, reader)

    assert result.published_revision_id == PUBLISHED_REVISION_ID
    assert spy.get_head_calls == 1
    assert spy.get_revision_calls == 1
    assert spy.publish_calls == 1


@pytest.mark.conformance
def test_mismatched_returned_envelope_fails_without_retry_or_post_commit_read() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()

    def alter(revision: WorldGraphRevision) -> WorldGraphRevision:
        return revision.model_copy(update={"operation_ids": ["reviewop:" + "2" * 32]})

    spy = _SpyWorldGraphRepository(graph, alter_return=alter)
    with pytest.raises(PersistenceIntegrityError) as exc:
        _publish(reviews, spy, reader)

    assert exc.value.details == {"reason": "published_revision_envelope_mismatch"}
    assert spy.get_head_calls == 1
    assert spy.get_revision_calls == 1
    assert spy.publish_calls == 1


@pytest.mark.conformance
def test_unknown_publish_outcome_is_propagated_without_retry_or_inference() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    spy = _SpyWorldGraphRepository(graph, raise_after_publish=True)

    with pytest.raises(RuntimeError, match="synthetic response loss"):
        _publish(reviews, spy, reader)

    assert spy.publish_calls == 1
    assert spy.get_head_calls == 1
    assert spy.get_revision_calls == 1
