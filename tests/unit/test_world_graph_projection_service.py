from datetime import UTC, datetime, timedelta

import pytest

from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from dungeonmind.contracts.projection import (
    Admissibility,
    FocusKind,
    ProjectionFocus,
    ScopeMode,
    WorldGraphProjectionRequest,
)
from dungeonmind.domain.errors import (
    HeadNotFoundError,
    RevisionNotFoundError,
    ScopeResolutionError,
)
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

WORLD_ID = "world:test"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class _FixedClock:
    def now(self):
        return NOW


def _empty_graph(world_id: str = WORLD_ID) -> dict:
    return {
        "world_id": world_id,
        "nodes": [],
        "relationships": [],
        "evidence_refs": [],
    }


def _publish(
    world_graph: InMemoryWorldGraphRepository,
    *,
    parent_revision_id: str | None = None,
    operation_id: str = "op:first",
    graph_world_id: str = WORLD_ID,
    created_at: datetime = NOW,
) -> WorldGraphRevision:
    return world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent_revision_id,
            expected_parent_revision_id=parent_revision_id,
            operation_ids=[operation_id],
            graph_schema="dm_union_graph_v1",
            graph_payload=_empty_graph(graph_world_id),
            created_at=created_at,
        )
    )


def _service(world_graph) -> WorldGraphProjectionService:
    return WorldGraphProjectionService(
        world_graph=world_graph,
        sources=InMemorySourceRepository(),
        graph_reader=UnionGraphV1SnapshotReader(),
        clock=_FixedClock(),
    )


def _world_request(*, revision_pin: str | None = None) -> WorldGraphProjectionRequest:
    return WorldGraphProjectionRequest(
        world_id=WORLD_ID,
        admissibility=Admissibility.GM,
        revision_pin=revision_pin,
        scope_mode=ScopeMode.WORLD,
    )


def test_unpinned_projection_resolves_and_reports_current_head():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)

    result = _service(world_graph).project(_world_request())

    assert result.snapshot.revision_id == published.revision_id
    assert result.snapshot.head_revision_id == published.revision_id
    assert result.snapshot.is_head is True
    assert result.snapshot.projected_at == NOW
    assert result.graph.world_id == WORLD_ID
    assert result.graph.objects == {}
    assert result.graph.relationships == {}


def test_exact_historical_pin_is_repinable_while_current_head_is_reported():
    world_graph = InMemoryWorldGraphRepository()
    first = _publish(world_graph)
    second = _publish(
        world_graph,
        parent_revision_id=first.revision_id,
        operation_id="op:second",
        created_at=NOW + timedelta(seconds=1),
    )

    result = _service(world_graph).project(
        _world_request(revision_pin=first.revision_id)
    )

    assert result.snapshot.revision_id == first.revision_id
    assert result.snapshot.head_revision_id == second.revision_id
    assert result.snapshot.is_head is False


def test_projection_preserves_authorized_campaign_focus_and_admissibility_identity():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    request = WorldGraphProjectionRequest(
        world_id=WORLD_ID,
        campaign_id="campaign:test",
        focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="session:test"),
        admissibility=Admissibility.PLAYER,
        revision_pin=published.revision_id,
        query_text="context carried for successor retrieval",
        scope_mode=ScopeMode.CAMPAIGN,
    )

    result = _service(world_graph).project(request)

    assert result.snapshot.campaign_id == request.campaign_id
    assert result.snapshot.focus == request.focus
    assert result.snapshot.admissibility is Admissibility.PLAYER
    assert result.snapshot.scope_mode is ScopeMode.CAMPAIGN


def test_missing_world_head_fails_closed():
    with pytest.raises(HeadNotFoundError):
        _service(InMemoryWorldGraphRepository()).project(_world_request())


def test_missing_revision_pin_fails_closed():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)

    with pytest.raises(RevisionNotFoundError):
        _service(world_graph).project(_world_request(revision_pin="rev:not-present"))


def test_payload_world_mismatch_fails_closed():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, graph_world_id="world:other")

    with pytest.raises(ScopeResolutionError) as excinfo:
        _service(world_graph).project(_world_request())

    assert excinfo.value.details["reason"] == "payload_world_mismatch"


class _RevisionWorldMismatchRepository:
    def get_head(self, world_id: str) -> WorldGraphHead:
        return WorldGraphHead(
            world_id=world_id,
            head_revision_id="rev:foreign",
            updated_at=NOW,
        )

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision:
        return StoredGraphRevision(
            revision=WorldGraphRevision(
                world_id="world:other",
                revision_id=revision_id,
                parent_revision_id=None,
                created_at=NOW,
                operation_ids=["op:foreign"],
                graph_schema="dm_union_graph_v1",
                graph_payload_sha256="sha256:foreign",
            ),
            graph_payload=_empty_graph("world:other"),
        )


def test_repository_revision_world_mismatch_fails_before_graph_parse():
    with pytest.raises(ScopeResolutionError) as excinfo:
        _service(_RevisionWorldMismatchRepository()).project(_world_request())

    assert excinfo.value.details["reason"] == "revision_world_mismatch"
