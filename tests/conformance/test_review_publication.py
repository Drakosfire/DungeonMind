"""Owning-boundary proofs for finalized-review CAS publication."""

from __future__ import annotations

import copy
import inspect
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application import (
    FinalizedReviewPublication,
    publish_finalized_review,
)
from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.contribution import ContributionStatus, GraphContribution
from dungeonmind.contracts.contribution_review import (
    ContributionAssertionVerdict,
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionPlanRef,
    ContributionReviewState,
    contribution_payload_sha256,
    derive_confirmation_id,
    derive_review_id,
    derive_review_intent_sha256,
    derive_reviewed_contribution_id,
)
from dungeonmind.contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationCommand
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ContributionMaterializationError,
    ContributionReviewNotFoundError,
    FinalizedReviewPublicationOutcomeUnknownError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryFinalizedReviewPublicationRepository,
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


def _seed_review() -> tuple[InMemoryContributionReviewRepository, ContributionReviewState]:
    contributions = InMemoryContributionRepository()
    reviews = InMemoryContributionReviewRepository(contributions)
    state = _state()
    persisted = reviews.finalize(state)
    return reviews, persisted


def review_state_for_operation(operation_suffix: str) -> ContributionReviewState:
    """A second valid finalized review pinned to the same parent, new operation.

    Used by failure lanes that need a fresh durable publication boundary on a
    world whose head has already advanced past the fixture parent.
    """
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["record"]["operation_id"] = f"reviewop:{operation_suffix}"
    payload["record"]["plan_ref"]["source_plan_id"] = f"plan:{operation_suffix}"

    candidate = GraphContribution.model_validate(payload["candidate_contribution"])
    candidate_preview = candidate.model_copy(update={"status": ContributionStatus.ACTIVE})
    plan_ref = ContributionPlanRef.model_validate(payload["record"]["plan_ref"])
    identity_proposals = [
        ContributionIdentityProposal.model_validate(item)
        for item in payload["record"]["identity_proposals"]
    ]
    identity_verdicts = [
        ContributionIdentityVerdict.model_validate(item)
        for item in payload["record"]["identity_verdicts"]
    ]
    assertion_verdicts = [
        ContributionAssertionVerdict.model_validate(item)
        for item in payload["record"]["assertion_verdicts"]
    ]
    reviewed_at = datetime.fromisoformat(payload["record"]["reviewed_at"].replace("Z", "+00:00"))
    review_intent_sha256 = derive_review_intent_sha256(
        operation_id=payload["record"]["operation_id"],
        world_id=payload["record"]["world_id"],
        campaign_id=payload["record"]["campaign_id"],
        plan_ref=plan_ref,
        candidate_contribution=candidate_preview,
        identity_proposals=identity_proposals,
        identity_verdicts=identity_verdicts,
        assertion_verdicts=assertion_verdicts,
        reviewer_id=payload["record"]["reviewer_id"],
        reviewed_at=reviewed_at,
    )
    review_id = derive_review_id(
        operation_id=payload["record"]["operation_id"],
        review_intent_sha256=review_intent_sha256,
        world_id=payload["record"]["world_id"],
    )
    reviewed_payload = payload["reviewed_contribution"]
    reviewed_payload["contribution_id"] = derive_reviewed_contribution_id(
        review_id=review_id,
        candidate_contribution_id=candidate.contribution_id,
    )
    reviewed = GraphContribution.model_validate(reviewed_payload)

    payload["record"]["review_id"] = review_id
    payload["record"]["review_intent_sha256"] = review_intent_sha256
    payload["record"]["reviewed_contribution_id"] = reviewed.contribution_id
    payload["record"]["reviewed_contribution_sha256"] = contribution_payload_sha256(reviewed)
    payload["record"]["confirmation_id"] = derive_confirmation_id(
        operation_id=payload["record"]["operation_id"],
        review_intent_sha256=review_intent_sha256,
        actor=payload["record"]["reviewer_id"],
        confirmed_at=reviewed_at,
    )
    payload["reviewed_contribution"] = reviewed.model_dump(mode="json")
    return ContributionReviewState.model_validate(payload)


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


class _SpyPublicationRepository:
    def __init__(
        self,
        inner: InMemoryFinalizedReviewPublicationRepository,
        *,
        raise_after_publish: bool = False,
        alter_return: Callable[[FinalizedReviewPublication], FinalizedReviewPublication]
        | None = None,
        fail_recovery_probe: bool = False,
    ) -> None:
        self.inner = inner
        self.get_calls = 0
        self.publish_calls = 0
        self.raise_after_publish = raise_after_publish
        self.alter_return = alter_return
        self.fail_recovery_probe = fail_recovery_probe

    def get_for_review(self, world_id: str, review_id: str):
        self.get_calls += 1
        if self.fail_recovery_probe and self.publish_calls:
            raise RuntimeError("synthetic recovery outage")
        return self.inner.get_for_review(world_id, review_id)

    def get(self, world_id: str, operation_id: str):
        return self.inner.get(world_id, operation_id)

    def publish(self, command):
        self.publish_calls += 1
        publication = self.inner.publish(command)
        if self.raise_after_publish:
            raise RuntimeError("synthetic response loss")
        if self.alter_return is not None:
            return self.alter_return(publication)
        return publication


class _EmptyPublicationRepository:
    def get_for_review(self, world_id: str, review_id: str):
        del world_id, review_id
        return None

    def get(self, world_id: str, operation_id: str):
        del world_id, operation_id
        return None

    def publish(self, command):
        del command
        raise AssertionError("publication must not be reached")


class _RacePublicationRepository:
    def __init__(self, inner: InMemoryFinalizedReviewPublicationRepository, competitor):
        self.inner = inner
        self.competitor = competitor
        self.publish_calls = 0

    def get_for_review(self, world_id: str, review_id: str):
        return self.inner.get_for_review(world_id, review_id)

    def get(self, world_id: str, operation_id: str):
        return self.inner.get(world_id, operation_id)

    def publish(self, command):
        self.publish_calls += 1
        self.competitor()
        return self.inner.publish(command)


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
    publication_repository: Any | None = None,
) -> FinalizedReviewPublication:
    if publication_repository is None:
        owner = getattr(repository, "inner", repository)
        publication_repository = getattr(owner, "_publication_repository", None)
        if publication_repository is None:
            publication_repository = InMemoryFinalizedReviewPublicationRepository(
                reviews,
                owner,
            )
            owner._publication_repository = publication_repository
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=published_at,
        review_repository=reviews,
        world_graph_repository=repository,
        publication_repository=publication_repository,
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
        reviewed_contribution_sha256=state.record.reviewed_contribution_sha256,
        review_intent_sha256=state.record.review_intent_sha256,
        confirmation_id="confirm:fa0d200c9922caf3c7e925b320cf9dae",
        operation_id="reviewop:11111111111111111111111111111111",
        expected_parent_revision_id=PARENT_REVISION_ID,
        parent_graph_payload_sha256=state.record.plan_ref.base_graph_payload_sha256,
        published_revision_id=PUBLISHED_REVISION_ID,
        graph_schema="dm_union_graph_v3",
        graph_payload_sha256=PAYLOAD_SHA256,
        published_at=PUBLISHED_AT,
    )
    assert canonical_sha256(result.model_dump(mode="json")) == (
        "3e7a632142c41066d3866c8682290fdc8e57b8f08b3324689c2964f6b045958c"
    )
    published = graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert published is not None
    assert published.graph_payload == json.loads(MATERIALIZED_FIXTURE.read_text(encoding="utf-8"))
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
        "publication_repository",
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
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    graph._heads.pop(WORLD_ID)

    with pytest.raises(StaleParentRevisionError):
        _publish(reviews, graph, reader)

    assert graph.get_head(WORLD_ID) is None


@pytest.mark.conformance
def test_missing_exact_parent_fails_without_publish() -> None:
    _parent, reader = _parent_inputs()
    reviews, _state_value = _seed_review()
    graph = _MissingParentWorldGraphRepository(PARENT_REVISION_ID)

    with pytest.raises(RevisionNotFoundError):
        _publish(
            reviews,
            graph,
            reader,
            publication_repository=_EmptyPublicationRepository(),
        )

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
    publication = InMemoryFinalizedReviewPublicationRepository(reviews, graph)

    with pytest.raises(StaleParentRevisionError):
        _publish(
            reviews,
            spy,
            _parent_inputs()[1],
            publication_repository=publication,
        )

    assert spy.get_head_calls == 0
    assert spy.get_revision_calls == 1
    assert graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None


@pytest.mark.conformance
def test_materialization_failure_is_write_free() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, _reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    spy = _SpyWorldGraphRepository(graph)
    publication = _SpyPublicationRepository(
        InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    )

    with pytest.raises(ContributionMaterializationError) as exc:
        _publish(
            reviews,
            spy,
            _RejectingReader(),
            publication_repository=publication,
        )

    assert exc.value.details["reason"] == "parent_reload_validation"
    assert spy.get_head_calls == 0
    assert spy.get_revision_calls == 1
    assert publication.get_calls == 1
    assert publication.publish_calls == 0
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

    publication = _RacePublicationRepository(
        InMemoryFinalizedReviewPublicationRepository(reviews, graph),
        competitor_wins,
    )
    with pytest.raises(StaleParentRevisionError):
        _publish(reviews, graph, reader, publication_repository=publication)

    assert publication.publish_calls == 1
    assert graph.get_head(WORLD_ID).head_revision_id != PARENT_REVISION_ID  # type: ignore[union-attr]
    assert graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None


@pytest.mark.conformance
def test_concurrent_same_review_calls_have_one_winner_and_one_stale_loser() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    publication = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def call() -> None:
        try:
            barrier.wait(timeout=5)
            outcomes.append(
                _publish(
                    reviews,
                    graph,
                    reader,
                    publication_repository=publication,
                )
            )
        except BaseException as exc:
            outcomes.append(exc)

    first = threading.Thread(target=call)
    second = threading.Thread(target=call)
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive() and not second.is_alive()
    assert len(outcomes) == 2
    assert all(isinstance(item, FinalizedReviewPublication) for item in outcomes)
    assert outcomes[0] == outcomes[1]
    assert graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_immediate_replay_returns_original_record_without_rematerialization() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    before = graph.get_head(WORLD_ID)

    replay = _publish(
        reviews,
        graph,
        _RejectingReader(),
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert replay == first
    assert graph.get_head(WORLD_ID) == before


@pytest.mark.conformance
def test_explicit_rollback_allows_same_content_addressed_revision_replay() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    graph.rollback_head(WORLD_ID, PARENT_REVISION_ID, updated_at=PUBLISHED_AT)

    replay = _publish(
        reviews,
        graph,
        _RejectingReader(),
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert replay == first
    assert graph.get_head(WORLD_ID).head_revision_id == PARENT_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_success_path_has_no_post_commit_repository_read() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    spy = _SpyWorldGraphRepository(graph)
    publication = _SpyPublicationRepository(
        InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    )

    result = _publish(
        reviews,
        spy,
        reader,
        publication_repository=publication,
    )

    assert result.published_revision_id == PUBLISHED_REVISION_ID
    assert spy.get_head_calls == 0
    assert spy.get_revision_calls == 1
    assert publication.get_calls == 1
    assert publication.publish_calls == 1


@pytest.mark.conformance
def test_mismatched_returned_envelope_recovers_durable_record_without_republish() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()

    def alter(publication: FinalizedReviewPublication) -> FinalizedReviewPublication:
        return publication.model_copy(update={"operation_id": "reviewop:" + "2" * 32})

    publication = _SpyPublicationRepository(
        InMemoryFinalizedReviewPublicationRepository(reviews, graph),
        alter_return=alter,
    )
    result = _publish(
        reviews,
        graph,
        reader,
        publication_repository=publication,
    )

    assert result.published_revision_id == PUBLISHED_REVISION_ID
    assert publication.get_calls == 2
    assert publication.publish_calls == 1


@pytest.mark.conformance
def test_response_loss_recovers_or_returns_sanitized_unknown_outcome() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    inner = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    spy = _SpyPublicationRepository(
        inner,
        raise_after_publish=True,
        fail_recovery_probe=True,
    )

    with pytest.raises(FinalizedReviewPublicationOutcomeUnknownError) as exc:
        _publish(
            reviews,
            graph,
            reader,
            publication_repository=spy,
        )

    assert exc.value.details == {
        "world_id": WORLD_ID,
        "review_id": REVIEW_ID,
        "operation_id": "reviewop:11111111111111111111111111111111",
        "expected_published_revision_id": PUBLISHED_REVISION_ID,
        "reason": "publication_attempt_or_recovery_probe_failed",
        "retry_safe": True,
    }
    assert spy.publish_calls == 1
    assert spy.get_calls == 2

    recovered = _publish(
        reviews,
        graph,
        _RejectingReader(),
        publication_repository=_SpyPublicationRepository(inner),
    )
    assert recovered.published_revision_id == PUBLISHED_REVISION_ID


@pytest.mark.conformance
def test_failed_atomic_publication_rolls_back_graph_and_record() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    publication = InMemoryFinalizedReviewPublicationRepository(
        reviews,
        graph,
        failure_hook=lambda: (_ for _ in ()).throw(RuntimeError("synthetic abort")),
    )

    with pytest.raises(FinalizedReviewPublicationOutcomeUnknownError):
        _publish(
            reviews,
            graph,
            reader,
            publication_repository=publication,
        )

    assert graph.get_head(WORLD_ID).head_revision_id == PARENT_REVISION_ID  # type: ignore[union-attr]
    assert graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None
    assert publication.get_for_review(WORLD_ID, REVIEW_ID) is None

    retry = _publish(
        reviews,
        graph,
        reader,
        publication_repository=InMemoryFinalizedReviewPublicationRepository(
            reviews,
            graph,
        ),
    )
    assert retry.published_revision_id == PUBLISHED_REVISION_ID


@pytest.mark.conformance
def test_exact_predecessor_revision_is_adopted_without_head_mutation() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    child = graph.get_revision(WORLD_ID, first.published_revision_id)
    assert child is not None

    publication = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    adopted = _publish(
        reviews,
        graph,
        reader,
        publication_repository=publication,
    )

    assert adopted == first
    assert graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.conformance
def test_historical_replay_ignores_descendant_head() -> None:
    graph = InMemoryWorldGraphRepository()
    _parent, reader = _seed_graph(graph)
    reviews, _state_value = _seed_review()
    first = _publish(reviews, graph, reader)
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=first.published_revision_id,
            expected_parent_revision_id=first.published_revision_id,
            operation_ids=["op:descendant"],
            graph_schema="dm_union_graph_v3",
            graph_payload=copy.deepcopy(
                graph.get_revision(WORLD_ID, first.published_revision_id).graph_payload  # type: ignore[union-attr]
            ),
            created_at=datetime(2026, 8, 4, tzinfo=UTC),
        )
    )

    replay = _publish(
        reviews,
        graph,
        _RejectingReader(),
        published_at=datetime(2026, 8, 5, tzinfo=UTC),
    )

    assert replay == first
    assert graph.get_head(WORLD_ID).head_revision_id != first.published_revision_id  # type: ignore[union-attr]


@pytest.mark.conformance
def test_publication_command_is_payload_and_revision_bound() -> None:
    with pytest.raises(ValidationError):
        FinalizedReviewPublicationCommand.model_validate(
            {
                "world_id": WORLD_ID,
                "review_id": REVIEW_ID,
                "reviewed_contribution_id": "contrib:" + "1" * 32,
                "reviewed_contribution_sha256": "0" * 64,
                "review_intent_sha256": "1" * 64,
                "confirmation_id": "confirm:" + "2" * 32,
                "operation_id": "reviewop:" + "3" * 32,
                "expected_parent_revision_id": PARENT_REVISION_ID,
                "parent_graph_payload_sha256": "4" * 64,
                "expected_published_revision_id": "rev:" + "5" * 32,
                "graph_schema": "dm_union_graph_v3",
                "graph_payload": {"tampered": True},
                "graph_payload_sha256": "6" * 64,
                "requested_published_at": "2026-08-03T23:00:00Z",
                "unexpected": "rejected",
            }
        )


@pytest.mark.conformance
def test_failed_world_rollback_preserves_concurrent_other_world_commit() -> None:
    world_a = WORLD_ID
    world_b = "world:synthetic-second"
    parent, _reader = _parent_inputs()
    graph = InMemoryWorldGraphRepository()
    parent_ids: dict[str, str] = {}
    for world_id in (world_a, world_b):
        graph.publish_revision(
            PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=list(parent.revision.operation_ids),
                graph_schema=parent.revision.graph_schema,
                graph_payload=copy.deepcopy(parent.graph_payload),
                created_at=parent.revision.created_at,
            )
        )
        head = graph.get_head(world_id)
        assert head is not None
        parent_ids[world_id] = head.head_revision_id

    base_record = _state().record

    def command_for(world_id: str, review_id: str) -> FinalizedReviewPublicationCommand:
        parent_id = parent_ids[world_id]
        payload = copy.deepcopy(parent.graph_payload)
        payload_sha256 = canonical_sha256(payload)
        operation_id = base_record.operation_id
        return FinalizedReviewPublicationCommand(
            world_id=world_id,
            review_id=review_id,
            reviewed_contribution_id=base_record.reviewed_contribution_id,
            reviewed_contribution_sha256=base_record.reviewed_contribution_sha256,
            review_intent_sha256=base_record.review_intent_sha256,
            confirmation_id=base_record.confirmation_id,
            operation_id=operation_id,
            expected_parent_revision_id=parent_id,
            parent_graph_payload_sha256=base_record.plan_ref.base_graph_payload_sha256,
            expected_published_revision_id=compute_revision_id(
                world_id=world_id,
                parent_revision_id=parent_id,
                operation_ids=[operation_id],
                graph_schema=base_record.plan_ref.base_graph_schema,
                graph_payload_sha256=payload_sha256,
            ),
            graph_schema=base_record.plan_ref.base_graph_schema,
            graph_payload=payload,
            graph_payload_sha256=payload_sha256,
            requested_published_at=PUBLISHED_AT,
        )

    def state_for(world_id: str, review_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            record=SimpleNamespace(
                world_id=world_id,
                review_id=review_id,
                reviewed_contribution_id=base_record.reviewed_contribution_id,
                reviewed_contribution_sha256=base_record.reviewed_contribution_sha256,
                review_intent_sha256=base_record.review_intent_sha256,
                confirmation_id=base_record.confirmation_id,
                operation_id=base_record.operation_id,
                plan_ref=SimpleNamespace(
                    expected_parent_revision_id=parent_ids[world_id],
                    base_graph_payload_sha256=base_record.plan_ref.base_graph_payload_sha256,
                    base_graph_schema=base_record.plan_ref.base_graph_schema,
                ),
            )
        )

    review_repository = SimpleNamespace(
        get=lambda world_id, review_id: {
            (world_a, "review:a"): state_for(world_a, "review:a"),
            (world_b, "review:b"): state_for(world_b, "review:b"),
        }.get((world_id, review_id))
    )
    a_ready = threading.Event()
    b_committed = threading.Event()
    current_world = threading.local()

    def fail_world_a_after_graph_commit() -> None:
        if getattr(current_world, "value", None) == world_a:
            a_ready.set()
            assert b_committed.wait(timeout=5)
            raise RuntimeError("synthetic world-A failure")

    publication = InMemoryFinalizedReviewPublicationRepository(
        review_repository,  # type: ignore[arg-type]
        graph,
        failure_hook=fail_world_a_after_graph_commit,
    )
    commands = {
        world_a: command_for(world_a, "review:a"),
        world_b: command_for(world_b, "review:b"),
    }
    outcomes: dict[str, object] = {}

    def publish_world(world_id: str) -> None:
        current_world.value = world_id
        try:
            outcomes[world_id] = publication.publish(commands[world_id])
        except BaseException as exc:
            outcomes[world_id] = exc

    def publish_world_b() -> None:
        assert a_ready.wait(timeout=5)
        publish_world(world_b)
        b_committed.set()

    thread_a = threading.Thread(target=publish_world, args=(world_a,))
    thread_b = threading.Thread(target=publish_world_b)
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=5)
    thread_b.join(timeout=5)

    assert not thread_a.is_alive() and not thread_b.is_alive()
    assert isinstance(outcomes[world_a], RuntimeError)
    winning = outcomes[world_b]
    assert isinstance(winning, FinalizedReviewPublication)
    assert graph.get_head(world_a).head_revision_id == parent_ids[world_a]  # type: ignore[union-attr]
    assert graph.get_head(world_b).head_revision_id == winning.published_revision_id  # type: ignore[union-attr]
    assert graph.get_revision(world_a, commands[world_a].expected_published_revision_id) is None
    assert publication.get_for_review(world_a, "review:a") is None
    assert publication.get_for_review(world_b, "review:b") == winning
