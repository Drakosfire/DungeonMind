"""PostgreSQL owning-boundary proofs for finalized-review publication."""

from __future__ import annotations

import copy
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application import FinalizedReviewPublication, publish_finalized_review
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
    WorldGraphRevision,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import StaleParentRevisionError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.postgres import (
    PostgresDatabase,
    PostgresRepositoryBundle,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

pytestmark = pytest.mark.integration

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


def _second_state() -> ContributionReviewState:
    """Create a second valid review pinned to the same parent and new operation."""
    payload = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    payload["record"]["operation_id"] = "reviewop:" + "2" * 32
    payload["record"]["plan_ref"]["source_plan_id"] = "plan:" + "2" * 32

    candidate = GraphContribution.model_validate(payload["candidate_contribution"])
    candidate_preview = candidate.model_copy(
        update={"status": ContributionStatus.ACTIVE}
    )
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
    reviewed_at = datetime.fromisoformat(
        payload["record"]["reviewed_at"].replace("Z", "+00:00")
    )
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
    payload["record"]["reviewed_contribution_sha256"] = contribution_payload_sha256(
        reviewed
    )
    payload["record"]["confirmation_id"] = derive_confirmation_id(
        operation_id=payload["record"]["operation_id"],
        review_intent_sha256=review_intent_sha256,
        actor=payload["record"]["reviewer_id"],
        confirmed_at=reviewed_at,
    )
    payload["reviewed_contribution"] = reviewed.model_dump(mode="json")
    return ContributionReviewState.model_validate(payload)


def _seed_parent(bundle: PostgresRepositoryBundle) -> StoredGraphRevision:
    parent, _reader = _parent_inputs()
    bundle.world_graph.publish_revision(
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
    return parent


def _reader() -> UnionGraphV3SnapshotReader:
    _parent, reader = _parent_inputs()
    return reader


def _publish(
    bundle: PostgresRepositoryBundle,
    reader: UnionGraphV3SnapshotReader,
    *,
    review_id: str = REVIEW_ID,
) -> FinalizedReviewPublication:
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=PUBLISHED_AT,
        review_repository=bundle.contribution_reviews,
        world_graph_repository=bundle.world_graph,
        graph_reader=reader,
    )


def _seed_tripod(bundle: PostgresRepositoryBundle) -> ContributionReviewState:
    _seed_parent(bundle)
    state = _state()
    bundle.contribution_reviews.finalize(state)
    return state


@pytest.mark.integration
def test_postgres_publishes_exact_tripod_review_and_preserves_review(
    pg,
) -> None:
    state = _seed_tripod(pg)
    before = pg.contribution_reviews.get(WORLD_ID, REVIEW_ID)
    assert before is not None

    result = _publish(pg, _reader())

    assert result.published_revision_id == PUBLISHED_REVISION_ID
    assert result.expected_parent_revision_id == PARENT_REVISION_ID
    assert result.operation_id == state.record.operation_id
    assert result.graph_schema == "dm_union_graph_v3"
    assert result.graph_payload_sha256 == PAYLOAD_SHA256
    assert result.published_at == PUBLISHED_AT
    stored = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert stored is not None
    assert stored.graph_payload == json.loads(
        MATERIALIZED_FIXTURE.read_text(encoding="utf-8")
    )
    assert stored.revision.operation_ids == [state.record.operation_id]
    assert stored.revision.parent_revision_id == PARENT_REVISION_ID
    assert stored.revision.created_at == PUBLISHED_AT
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]
    after = pg.contribution_reviews.get(WORLD_ID, REVIEW_ID)
    assert after is not None
    assert after.model_dump(mode="json") == before.model_dump(mode="json")


@pytest.mark.integration
def test_postgres_immediate_replay_is_stale_and_keeps_one_child(pg) -> None:
    _seed_tripod(pg)
    first = _publish(pg, _reader())

    with pytest.raises(StaleParentRevisionError):
        _publish(pg, _reader())

    assert first.published_revision_id == PUBLISHED_REVISION_ID
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.integration
def test_postgres_two_finalized_reviews_pinned_to_one_parent_have_one_cas_winner(
    migrated_database: str,
    pg,
) -> None:
    _seed_tripod(pg)
    second = _second_state()
    pg.contribution_reviews.finalize(second)

    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    successes: list[FinalizedReviewPublication] = []
    errors: list[BaseException] = []

    def call(bundle: PostgresRepositoryBundle, review_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            successes.append(_publish(bundle, _reader(), review_id=review_id))
        except BaseException as exc:
            errors.append(exc)

    first_thread = threading.Thread(target=call, args=(bundle_a, REVIEW_ID))
    second_thread = threading.Thread(
        target=call,
        args=(bundle_b, second.record.review_id),
    )
    first_thread.start()
    second_thread.start()
    first_thread.join(timeout=15)
    second_thread.join(timeout=15)

    assert not first_thread.is_alive() and not second_thread.is_alive()
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], StaleParentRevisionError)
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == successes[0].published_revision_id  # type: ignore[union-attr]
    assert pg.world_graph.get_revision(WORLD_ID, PARENT_REVISION_ID) is not None
