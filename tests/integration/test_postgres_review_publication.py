"""PostgreSQL owning-boundary proofs for finalized-review publication."""

from __future__ import annotations

import copy
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.application.review_publication import (
    FinalizedReviewPublication,
    publish_finalized_review,
)
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
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationCommand
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    FinalizedReviewPublicationOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

if TYPE_CHECKING:
    from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle

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


class _RejectingReader:
    def parse(self, *, graph_schema: str, graph_payload: dict) -> None:
        del graph_schema, graph_payload
        raise AssertionError("replay unexpectedly rematerialized the graph")


class _ResponseLossPublicationRepository:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.publish_calls = 0

    def get_for_review(self, world_id: str, review_id: str):
        return self.inner.get_for_review(world_id, review_id)

    def get(self, world_id: str, operation_id: str):
        return self.inner.get(world_id, operation_id)

    def publish(self, command):
        self.publish_calls += 1
        self.inner.publish(command)
        raise RuntimeError("synthetic committed response loss")


def _head_event_count(pg) -> int:
    with pg.database.connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.world_graph_head_events
            WHERE world_id = %s
            """,
            (WORLD_ID,),
        ).fetchone()
    return int(row["count"])


def _publication_count(pg) -> int:
    with pg.database.connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.finalized_review_publications
            WHERE world_id = %s
            """,
            (WORLD_ID,),
        ).fetchone()
    return int(row["count"])


def _publish_exact_predecessor(pg) -> StoredGraphRevision:
    parent, _reader_value = _parent_inputs()
    payload = json.loads(MATERIALIZED_FIXTURE.read_text(encoding="utf-8"))
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=PARENT_REVISION_ID,
            expected_parent_revision_id=PARENT_REVISION_ID,
            operation_ids=[_state().record.operation_id],
            graph_schema="dm_union_graph_v3",
            graph_payload=copy.deepcopy(payload),
            created_at=PUBLISHED_AT,
        )
    )
    stored = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert stored is not None
    assert stored.revision.parent_revision_id == parent.revision.revision_id
    return stored


def _publish_descendant(pg, parent_revision_id: str) -> StoredGraphRevision:
    parent = pg.world_graph.get_revision(WORLD_ID, parent_revision_id)
    assert parent is not None
    operation_id = "reviewop:descendant0000000000000000000000"
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent_revision_id,
            expected_parent_revision_id=parent_revision_id,
            operation_ids=[operation_id],
            graph_schema=parent.revision.graph_schema,
            graph_payload=copy.deepcopy(parent.graph_payload),
            created_at=datetime(2026, 8, 4, tzinfo=UTC),
        )
    )
    descendant_id = compute_revision_id(
        world_id=WORLD_ID,
        parent_revision_id=parent_revision_id,
        operation_ids=[operation_id],
        graph_schema=parent.revision.graph_schema,
        graph_payload_sha256=parent.revision.graph_payload_sha256,
    )
    descendant = pg.world_graph.get_revision(WORLD_ID, descendant_id)
    assert descendant is not None
    return descendant


def _publish(
    bundle: PostgresRepositoryBundle,
    reader: Any,
    *,
    review_id: str = REVIEW_ID,
    published_at: datetime = PUBLISHED_AT,
    publication_repository=None,
) -> FinalizedReviewPublication:
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=published_at,
        review_repository=bundle.contribution_reviews,
        world_graph_repository=bundle.world_graph,
        publication_repository=(
            bundle.finalized_review_publications
            if publication_repository is None
            else publication_repository
        ),
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
def test_postgres_immediate_replay_returns_original_publication(pg) -> None:
    _seed_tripod(pg)
    first = _publish(pg, _reader())
    events_before = _head_event_count(pg)
    publications_before = _publication_count(pg)

    replay = publish_finalized_review(
        WORLD_ID,
        REVIEW_ID,
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=pg.finalized_review_publications,
        graph_reader=_reader(),
    )

    assert replay == first
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]
    assert _head_event_count(pg) == events_before
    assert _publication_count(pg) == publications_before


@pytest.mark.integration
def test_postgres_same_review_two_connections_return_one_durable_record(
    migrated_database: str,
    pg,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    _seed_tripod(pg)
    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    successes: list[FinalizedReviewPublication] = []
    errors: list[BaseException] = []

    def call(bundle: PostgresRepositoryBundle) -> None:
        try:
            barrier.wait(timeout=5)
            successes.append(_publish(bundle, _reader()))
        except BaseException as exc:
            errors.append(exc)

    first_thread = threading.Thread(target=call, args=(bundle_a,))
    second_thread = threading.Thread(target=call, args=(bundle_b,))
    first_thread.start()
    second_thread.start()
    first_thread.join(timeout=15)
    second_thread.join(timeout=15)

    assert not first_thread.is_alive() and not second_thread.is_alive()
    assert len(successes) == 2
    assert not errors
    assert successes[0] == successes[1]
    assert _publication_count(pg) == 1
    assert _head_event_count(pg) == 2


@pytest.mark.integration
@pytest.mark.parametrize("failure_at", [1, 2])
def test_postgres_atomic_publication_rolls_back_at_both_failure_points(
    migrated_database: str,
    pg,
    failure_at: int,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresFinalizedReviewPublicationRepository,
    )

    _seed_tripod(pg)
    calls = 0

    def fail_at_selected_point() -> None:
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise RuntimeError("synthetic atomic publication abort")

    publication = PostgresFinalizedReviewPublicationRepository(
        PostgresDatabase(migrated_database),
        failure_hook=fail_at_selected_point,
    )

    with pytest.raises(FinalizedReviewPublicationOutcomeUnknownError):
        _publish(pg, _reader(), publication_repository=publication)

    assert calls == failure_at
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PARENT_REVISION_ID  # type: ignore[union-attr]
    assert pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID) is None
    assert _publication_count(pg) == 0
    assert _head_event_count(pg) == 1


@pytest.mark.integration
def test_postgres_committed_response_loss_recovers_from_fresh_transaction(
    migrated_database: str,
    pg,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresFinalizedReviewPublicationRepository,
    )

    _seed_tripod(pg)
    inner = PostgresFinalizedReviewPublicationRepository(PostgresDatabase(migrated_database))
    response_loss = _ResponseLossPublicationRepository(inner)
    events_before = _head_event_count(pg)

    recovered = _publish(pg, _reader(), publication_repository=response_loss)

    assert response_loss.publish_calls == 1
    assert recovered.published_revision_id == PUBLISHED_REVISION_ID
    assert _publication_count(pg) == 1
    assert _head_event_count(pg) == events_before + 1


@pytest.mark.integration
@pytest.mark.parametrize("head_state", ["child", "descendant", "rollback"])
def test_postgres_exact_predecessor_adoption_preserves_head_and_events(
    pg,
    head_state: str,
) -> None:
    _seed_tripod(pg)
    _publish_exact_predecessor(pg)
    if head_state == "descendant":
        descendant = _publish_descendant(pg, PUBLISHED_REVISION_ID)
        expected_head = descendant.revision.revision_id
    elif head_state == "rollback":
        pg.world_graph.rollback_head(
            WORLD_ID,
            PARENT_REVISION_ID,
            updated_at=datetime(2026, 8, 4, tzinfo=UTC),
        )
        expected_head = PARENT_REVISION_ID
    else:
        expected_head = PUBLISHED_REVISION_ID
    events_before = _head_event_count(pg)

    adopted = _publish(pg, _reader())

    assert adopted.published_revision_id == PUBLISHED_REVISION_ID
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == expected_head  # type: ignore[union-attr]
    assert _head_event_count(pg) == events_before
    assert _publication_count(pg) == 1


@pytest.mark.integration
@pytest.mark.parametrize("head_state", ["descendant", "rollback"])
def test_postgres_historical_replay_ignores_descendant_or_rollback(
    pg,
    head_state: str,
) -> None:
    _seed_tripod(pg)
    first = _publish(pg, _reader())
    if head_state == "descendant":
        descendant = _publish_descendant(pg, first.published_revision_id)
        expected_head = descendant.revision.revision_id
    else:
        pg.world_graph.rollback_head(
            WORLD_ID,
            PARENT_REVISION_ID,
            updated_at=datetime(2026, 8, 4, tzinfo=UTC),
        )
        expected_head = PARENT_REVISION_ID
    events_before = _head_event_count(pg)
    publications_before = _publication_count(pg)

    replay = _publish(
        pg,
        _RejectingReader(),
        published_at=datetime(2026, 8, 5, tzinfo=UTC),
    )

    assert replay == first
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == expected_head  # type: ignore[union-attr]
    assert _head_event_count(pg) == events_before
    assert _publication_count(pg) == publications_before


@pytest.mark.integration
@pytest.mark.parametrize(
    ("drift_column", "drift_value"),
    [
        ("record_fingerprint", "deadbeef" * 8),
        ("published_at", datetime(2026, 8, 4, tzinfo=UTC)),
    ],
)
def test_postgres_publication_record_drift_fails_closed(
    migrated_database: str,
    pg,
    drift_column: str,
    drift_value,
) -> None:
    _seed_tripod(pg)
    _publish(pg, _reader())
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    with PostgresDatabase(migrated_database).transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.finalized_review_publications "
            f"SET {drift_column} = %s WHERE world_id = %s AND review_id = %s",
            (drift_value, WORLD_ID, REVIEW_ID),
        )

    with pytest.raises(PersistenceIntegrityError):
        pg.finalized_review_publications.get_for_review(WORLD_ID, REVIEW_ID)


@pytest.mark.integration
def test_postgres_referenced_revision_payload_drift_fails_closed(
    migrated_database: str,
    pg,
) -> None:
    _seed_tripod(pg)
    _publish(pg, _reader())
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase, jsonb

    with PostgresDatabase(migrated_database).transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.graph_revisions SET graph_payload = %s "
            "WHERE world_id = %s AND revision_id = %s",
            (jsonb({"tampered": True}), WORLD_ID, PUBLISHED_REVISION_ID),
        )

    with pytest.raises(PersistenceIntegrityError):
        pg.finalized_review_publications.get_for_review(WORLD_ID, REVIEW_ID)


@pytest.mark.integration
def test_postgres_changed_content_for_same_operation_is_conflict(
    pg,
) -> None:
    _seed_tripod(pg)
    first = _publish(pg, _reader())
    payload = {"tampered": True}
    payload_sha256 = canonical_sha256(payload)
    command = FinalizedReviewPublicationCommand(
        world_id=first.world_id,
        review_id=first.review_id,
        reviewed_contribution_id=first.reviewed_contribution_id,
        reviewed_contribution_sha256=first.reviewed_contribution_sha256,
        review_intent_sha256=first.review_intent_sha256,
        confirmation_id=first.confirmation_id,
        operation_id=first.operation_id,
        expected_parent_revision_id=first.expected_parent_revision_id,
        parent_graph_payload_sha256=first.parent_graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=first.world_id,
            parent_revision_id=first.expected_parent_revision_id,
            operation_ids=[first.operation_id],
            graph_schema=first.graph_schema,
            graph_payload_sha256=payload_sha256,
        ),
        graph_schema=first.graph_schema,
        graph_payload=payload,
        graph_payload_sha256=payload_sha256,
        requested_published_at=datetime(2026, 8, 4, tzinfo=UTC),
    )

    with pytest.raises(IdempotencyConflictError):
        pg.finalized_review_publications.publish(command)

    assert _publication_count(pg) == 1
    assert _head_event_count(pg) == 2


@pytest.mark.integration
def test_postgres_two_finalized_reviews_pinned_to_one_parent_have_one_cas_winner(
    migrated_database: str,
    pg,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

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
    winner = successes[0]
    loser_review_id = (
        second.record.review_id if winner.review_id == REVIEW_ID else REVIEW_ID
    )
    assert pg.finalized_review_publications.get_for_review(WORLD_ID, loser_review_id) is None
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == winner.published_revision_id  # type: ignore[union-attr]
    assert pg.world_graph.get_revision(WORLD_ID, PARENT_REVISION_ID) is not None


def test_verified_ancestry_uses_one_connection_and_one_reconstruction_per_revision(pg, monkeypatch):
    from dungeonmind.infrastructure.postgres import review_publication as module

    _seed_tripod(pg)
    _publish(pg, _reader())
    expected = pg.finalized_review_publications.get_for_published_revision(
        WORLD_ID, PUBLISHED_REVISION_ID)
    original_connect = pg.database.connect
    original_reconstruct = module._reconstruct_stored_revision
    connections, revision_ids = [], []
    def connect():
        connections.append(True)
        return original_connect()
    def reconstruct(row):
        revision_ids.append(row['revision_id'])
        return original_reconstruct(row)
    monkeypatch.setattr(pg.database, 'connect', connect)
    monkeypatch.setattr(module, '_reconstruct_stored_revision', reconstruct)
    rows = pg.finalized_review_publications.read_verified_ancestry(WORLD_ID, PUBLISHED_REVISION_ID)
    assert len(connections) == 1
    assert revision_ids == [PUBLISHED_REVISION_ID, PARENT_REVISION_ID]
    assert [row.revision.revision_id for row in rows] == revision_ids
    assert rows[0].publication == expected
    assert rows[0].review == _state()
    original_revision = rows[0].revision.model_copy(deep=True)
    rows[0].revision.operation_ids.append('caller:only')
    rows[0].review.reviewed_contribution.assertions.clear()
    again = pg.finalized_review_publications.read_verified_ancestry(WORLD_ID, PUBLISHED_REVISION_ID)
    assert again[0].revision == original_revision
    assert again[0].review == _state()
    assert again[0].publication == expected


@pytest.mark.parametrize('damage', ['publication', 'parent', 'child', 'review', 'contribution'])
def test_verified_ancestry_rejects_corrupt_join(pg, damage):
    from psycopg import sql

    _seed_tripod(pg)
    _publish(pg, _reader())
    table, column, value = {
        'publication': ('finalized_review_publications', 'review_id', REVIEW_ID),
        'parent': ('graph_revisions', 'revision_id', PARENT_REVISION_ID),
        'child': ('graph_revisions', 'revision_id', PUBLISHED_REVISION_ID),
        'review': ('contribution_reviews', 'review_id', REVIEW_ID),
        'contribution': ('graph_contributions', 'contribution_id',
                         _state().record.reviewed_contribution_id),
    }[damage]
    with pg.database.transaction() as conn:
        conn.execute(sql.SQL('UPDATE dungeonmind.{} SET record_fingerprint = %s WHERE {} = %s')
                     .format(sql.Identifier(table), sql.Identifier(column)), ('bad', value))
    with pytest.raises(PersistenceIntegrityError):
        pg.finalized_review_publications.read_verified_ancestry(WORLD_ID, PUBLISHED_REVISION_ID)


def test_verified_ancestry_rejects_missing_or_foreign_start(pg):
    _seed_tripod(pg)
    for world, revision in [(WORLD_ID, 'missing'), ('other', PARENT_REVISION_ID)]:
        with pytest.raises(PersistenceIntegrityError):
            pg.finalized_review_publications.read_verified_ancestry(world, revision)


@pytest.fixture(params=["v1", "v2"])
def historical_publication_lane(pg, request):
    """Both immutable receipt families; no new schema or transport fixture."""
    from types import SimpleNamespace

    from dungeonmind.infrastructure.postgres import PostgresFinalizedReviewPublicationRepository
    from tests.integration.test_postgres_publication_admission import setup_pg
    from tests.unit.test_publication_admission import SyntheticValidator

    if request.param == "v2":
        original = setup_pg(pg, validator=SyntheticValidator())
        receipt = original.publications.publish(original.command)
        state = original.state
    else:
        state = _seed_tripod(pg)
        receipt = _publish(pg, _reader())
    # Recovery must not require the original validator registry/process.
    repo = PostgresFinalizedReviewPublicationRepository(pg.database)
    return SimpleNamespace(pg=pg, receipt=receipt, state=state, repo=repo)


def _historical_read(lane):
    from dungeonmind.application.compatibility import read_historical_finalized_publication

    return read_historical_finalized_publication(
        lane.receipt.world_id, lane.receipt.operation_id, reader=lane.repo
    )


def _historical_snapshot(pg):
    """Compare complete rows, not just counts, across the privileged read."""
    from psycopg import sql

    with pg.database.connect() as conn:
        return {
            table: sorted(
                json.dumps(row["row"], sort_keys=True)
                for row in conn.execute(
                    sql.SQL("SELECT to_jsonb(t) AS row FROM dungeonmind.{} t").format(
                        sql.Identifier(table)
                    )
                ).fetchall()
            )
            for table in (
                "finalized_review_publications",
                "graph_revisions",
                "world_graph_heads",
                "world_graph_head_events",
                "contribution_reviews",
                "graph_contributions",
                "source_artifacts",
                "source_revisions",
                "evidence_refs",
            )
        }


def test_historical_terminal_is_one_bounded_readonly_snapshot(
    historical_publication_lane, monkeypatch
):
    from collections import Counter
    from contextlib import contextmanager

    lane = historical_publication_lane
    before = _historical_snapshot(lane.pg)
    calls, statements, modes = Counter(), [], []
    database = lane.pg.database
    original_transaction = database.transaction
    original_review, original_revision = lane.repo._load_review, lane.repo._load_revision

    class ConnectionProbe:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, statement, params=None):
            text = statement if isinstance(statement, str) else statement.as_string(self.conn)
            statements.append(text)
            result = self.conn.execute(statement, params)
            if text.startswith("SET TRANSACTION"):
                modes.append(
                    (
                        self.conn.execute("SHOW transaction_isolation").fetchone()[
                            "transaction_isolation"
                        ],
                        self.conn.execute("SHOW transaction_read_only").fetchone()[
                            "transaction_read_only"
                        ],
                    )
                )
            return result

    @contextmanager
    def transaction():
        calls["transaction"] += 1
        with original_transaction() as conn:
            yield ConnectionProbe(conn)

    def review(conn, **kwargs):
        calls["review"] += 1
        return original_review(conn, **kwargs)

    def revision(conn, **kwargs):
        calls[kwargs["revision_id"]] += 1
        return original_revision(conn, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("historical query attempted current authority or publication")

    with monkeypatch.context() as patch:
        patch.setattr(database, "transaction", transaction)
        patch.setattr(lane.repo, "_load_review", review)
        patch.setattr(lane.repo, "_load_revision", revision)
        patch.setattr(lane.repo, "publish", forbidden)
        patch.setattr(lane.repo._graph, "get_head", forbidden)
        patch.setattr(lane.repo, "get_provenance_snapshot", forbidden)
        patch.setattr(lane.repo._admission_registry, "validate", forbidden)
        entry = _historical_read(lane)
    assert entry.publication == lane.receipt
    assert entry.review == lane.state
    assert entry.revision.revision_id == lane.receipt.published_revision_id
    assert calls == Counter(
        {
            "transaction": 1,
            "review": 1,
            lane.receipt.published_revision_id: 1,
            lane.receipt.expected_parent_revision_id: 1,
        }
    )
    assert modes == [("repeatable read", "on")]
    assert all(text.lstrip().startswith(("SELECT", "SET TRANSACTION")) for text in statements)
    assert not any("source_artifacts" in text or "world_graph_heads" in text for text in statements)
    assert _historical_snapshot(lane.pg) == before
    entry.revision.operation_ids.clear()
    entry.review.reviewed_contribution.assertions.clear()
    entry.publication.confirmation_id = "caller:only"
    again = _historical_read(lane)
    assert again.publication == lane.receipt
    assert again.review == lane.state
    assert again.revision.operation_ids == [lane.receipt.operation_id]


def test_historical_absence_never_finishes_a_finalized_review(
    historical_publication_lane, monkeypatch
):
    lane = historical_publication_lane
    with lane.pg.database.transaction() as conn:
        conn.execute(
            "DELETE FROM dungeonmind.finalized_review_publications "
            "WHERE world_id=%s AND operation_id=%s",
            (lane.receipt.world_id, lane.receipt.operation_id),
        )
    before = _historical_snapshot(lane.pg)

    def forbidden(*args, **kwargs):
        raise AssertionError("absence must not publish or finalize")

    monkeypatch.setattr(lane.repo, "publish", forbidden)
    monkeypatch.setattr(lane.pg.contribution_reviews, "finalize", forbidden)
    assert _historical_read(lane) is None
    assert (
        lane.pg.contribution_reviews.get(lane.receipt.world_id, lane.receipt.review_id)
        == lane.state
    )
    assert _historical_snapshot(lane.pg) == before


@pytest.mark.parametrize("movement", ["descendant", "rollback"])
def test_historical_original_survives_head_movement(
    historical_publication_lane, movement, monkeypatch
):
    from datetime import timedelta

    lane = historical_publication_lane
    receipt = lane.receipt
    if movement == "descendant":
        original = lane.pg.world_graph.get_revision(receipt.world_id, receipt.published_revision_id)
        lane.pg.world_graph.publish_revision(
            PublishRevisionCommand(
                world_id=receipt.world_id,
                parent_revision_id=receipt.published_revision_id,
                expected_parent_revision_id=receipt.published_revision_id,
                operation_ids=["historical:descendant"],
                graph_schema=receipt.graph_schema,
                graph_payload=original.graph_payload,
                created_at=receipt.published_at + timedelta(seconds=1),
            )
        )
    else:
        lane.pg.world_graph.rollback_head(
            receipt.world_id,
            receipt.expected_parent_revision_id,
            updated_at=receipt.published_at + timedelta(seconds=1),
        )
    before = _historical_snapshot(lane.pg)
    monkeypatch.setattr(
        lane.repo._graph, "get_head", lambda *args: pytest.fail("current head read")
    )
    assert _historical_read(lane).publication == receipt
    assert _historical_snapshot(lane.pg) == before


@pytest.mark.parametrize("selector", ["world", "operation"])
def test_historical_valid_receipt_substitution_is_integrity(
    historical_publication_lane, monkeypatch, selector
):
    from dungeonmind.infrastructure.postgres import review_publication as module

    lane = historical_publication_lane
    with lane.pg.database.transaction() as conn:
        row = module._publication_row(
            conn, world_id=lane.receipt.world_id, operation_id=lane.receipt.operation_id
        )
    before = _historical_snapshot(lane.pg)
    monkeypatch.setattr(module, "_publication_row", lambda *args, **kwargs: row)
    world = "world:foreign" if selector == "world" else lane.receipt.world_id
    operation = "operation:foreign" if selector == "operation" else lane.receipt.operation_id
    with pytest.raises(PersistenceIntegrityError):
        lane.repo.read_verified_publication(world, operation)
    assert _historical_snapshot(lane.pg) == before


@pytest.mark.parametrize(
    "damage", ["publication", "review", "candidate", "contribution", "parent", "child"]
)
def test_historical_corrupt_companion_is_integrity(historical_publication_lane, damage):
    from psycopg import sql

    lane = historical_publication_lane
    receipt = lane.receipt
    table, column, value = {
        "publication": ("finalized_review_publications", "operation_id", receipt.operation_id),
        "review": ("contribution_reviews", "review_id", receipt.review_id),
        "candidate": (
            "graph_contributions",
            "contribution_id",
            lane.state.record.stored_candidate_contribution_id,
        ),
        "contribution": (
            "graph_contributions",
            "contribution_id",
            receipt.reviewed_contribution_id,
        ),
        "parent": ("graph_revisions", "revision_id", receipt.expected_parent_revision_id),
        "child": ("graph_revisions", "revision_id", receipt.published_revision_id),
    }[damage]
    with lane.pg.database.transaction() as conn:
        conn.execute(
            sql.SQL("UPDATE dungeonmind.{} SET record_fingerprint='bad' WHERE {}=%s").format(
                sql.Identifier(table), sql.Identifier(column)
            ),
            (value,),
        )
    before = _historical_snapshot(lane.pg)
    with pytest.raises(PersistenceIntegrityError):
        _historical_read(lane)
    assert _historical_snapshot(lane.pg) == before


@pytest.mark.parametrize("missing", ["review", "candidate", "contribution", "parent", "child"])
def test_historical_fk_protected_missing_row_read_fails_closed(
    historical_publication_lane, monkeypatch, missing
):
    """Inject absent read results without disabling database foreign keys."""
    from contextlib import contextmanager

    lane = historical_publication_lane
    key = {
        "review": ("review_id", lane.receipt.review_id),
        "candidate": ("contribution_id", lane.state.record.stored_candidate_contribution_id),
        "contribution": ("contribution_id", lane.receipt.reviewed_contribution_id),
        "parent": ("revision_id", lane.receipt.expected_parent_revision_id),
        "child": ("revision_id", lane.receipt.published_revision_id),
    }[missing]
    before = _historical_snapshot(lane.pg)
    original_transaction = lane.pg.database.transaction

    table = {
        "review": "contribution_reviews",
        "candidate": "graph_contributions",
        "contribution": "graph_contributions",
        "parent": "graph_revisions",
        "child": "graph_revisions",
    }[missing]

    class CursorFilter:
        def __init__(self, cursor, applies):
            self.cursor = cursor
            self.applies = applies

        def fetchone(self):
            row = self.cursor.fetchone()
            return (
                None
                if self.applies and row is not None and row.get(key[0]) == key[1]
                else row
            )

        def fetchall(self):
            return [
                row for row in self.cursor.fetchall()
                if not self.applies or row.get(key[0]) != key[1]
            ]

    class ConnectionFilter:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, statement, *args, **kwargs):
            text = statement if isinstance(statement, str) else statement.as_string(self.conn)
            return CursorFilter(
                self.conn.execute(statement, *args, **kwargs), f".{table}" in text
            )

    @contextmanager
    def filtered_transaction():
        with original_transaction() as conn:
            yield ConnectionFilter(conn)

    with monkeypatch.context() as patch:
        patch.setattr(lane.pg.database, "transaction", filtered_transaction)
        with pytest.raises(PersistenceIntegrityError):
            _historical_read(lane)
    assert _historical_snapshot(lane.pg) == before


def test_historical_v2_withdrawal_preserves_immutable_proof_and_ceiling(pg, monkeypatch):
    from dungeonmind.application.compatibility import read_historical_finalized_publication
    from dungeonmind.domain.errors import CapabilityDeniedError
    from dungeonmind.infrastructure.postgres import PostgresFinalizedReviewPublicationRepository
    from tests.integration.test_postgres_publication_admission import retract_source, setup_pg
    from tests.unit.test_publication_admission import SyntheticValidator

    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    artifact_id = receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id
    retract_source(pg, artifact_id)
    before = _historical_snapshot(pg)
    repo = PostgresFinalizedReviewPublicationRepository(pg.database)
    monkeypatch.setattr(
        repo._admission_registry, "validate", lambda *args: pytest.fail("validator rerun")
    )
    entry = read_historical_finalized_publication(
        receipt.world_id, receipt.operation_id, reader=repo
    )
    assert entry.publication == receipt
    assert entry.publication.admission_context.source_snapshot.artifacts[0].status == "active"
    with pytest.raises(CapabilityDeniedError):
        read_historical_finalized_publication(
            receipt.world_id,
            receipt.operation_id,
            reader=repo,
            allowed_receipt_schemas=frozenset({"dm_finalized_review_publication_v1"}),
        )
    assert _historical_snapshot(pg) == before
    revision_id = receipt.admission_context.source_snapshot.revisions[0].source_revision_id
    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.source_revisions SET content_sha256=%s WHERE source_revision_id=%s",
            ("0" * 64, revision_id),
        )
    with pytest.raises(PersistenceIntegrityError):
        read_historical_finalized_publication(receipt.world_id, receipt.operation_id, reader=repo)


def test_historical_read_keeps_verified_snapshot_under_concurrent_drift(
    historical_publication_lane, monkeypatch
):
    lane = historical_publication_lane
    original = lane.repo._load_review

    def review_then_drift(conn, **kwargs):
        state = original(conn, **kwargs)
        # A distinct committed writer changes the still-unread child. The
        # readonly repeatable snapshot must return the original verified view.
        with lane.pg.database.transaction() as writer:
            writer.execute(
                "UPDATE dungeonmind.graph_revisions SET graph_payload='{}'::jsonb "
                "WHERE world_id=%s AND revision_id=%s",
                (lane.receipt.world_id, lane.receipt.published_revision_id),
            )
        return state

    monkeypatch.setattr(lane.repo, "_load_review", review_then_drift)
    entry = _historical_read(lane)
    assert entry.publication == lane.receipt
    assert entry.review == lane.state
    monkeypatch.setattr(lane.repo, "_load_review", original)
    with pytest.raises(PersistenceIntegrityError):
        _historical_read(lane)


def test_historical_unknown_receipt_family_is_integrity(historical_publication_lane):
    lane = historical_publication_lane
    with lane.pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.finalized_review_publications SET schema_version='unknown' "
            "WHERE world_id=%s AND operation_id=%s",
            (lane.receipt.world_id, lane.receipt.operation_id),
        )
    before = _historical_snapshot(lane.pg)
    with pytest.raises(PersistenceIntegrityError):
        _historical_read(lane)
    assert _historical_snapshot(lane.pg) == before


def test_historical_unavailability_is_not_absence(historical_publication_lane, monkeypatch):
    from contextlib import contextmanager

    from dungeonmind.domain.errors import PersistenceUnavailableError

    lane = historical_publication_lane
    before = _historical_snapshot(lane.pg)

    @contextmanager
    def unavailable():
        raise PersistenceUnavailableError("synthetic unavailable transaction")
        yield  # pragma: no cover

    with monkeypatch.context() as patch:
        patch.setattr(lane.pg.database, "transaction", unavailable)
        with pytest.raises(PersistenceUnavailableError):
            _historical_read(lane)
    assert _historical_snapshot(lane.pg) == before
