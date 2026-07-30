"""Thread binding and turn-correlation enforcement."""

from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CallerScope,
    MindTurnRequest,
    MindTurnResponse,
    SurfaceContext,
)
from dungeonmind.domain.errors import IdempotencyConflictError, ThreadContextMismatchError
from dungeonmind.infrastructure.memory import InMemoryMindThreadRepository

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def _request(
    *,
    thread_id: str = "thr:1",
    world_id: str = "world:demo",
    campaign_id: str | None = "camp:1",
    tenant_id: str | None = "tenant:a",
    request_id: str = "req:1",
) -> MindTurnRequest:
    return MindTurnRequest(
        request_id=request_id,
        thread_id=thread_id,
        caller_scope=CallerScope(caller_id="user:1", tenant_id=tenant_id),
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=Admissibility.GM,
        surface_context=SurfaceContext(surface_id="surface:test"),
        message="hello",
    )


def _response(request: MindTurnRequest, *, turn_id: str = "turn:1") -> MindTurnResponse:
    return MindTurnResponse(
        request_id=request.request_id,
        turn_id=turn_id,
        thread_id=request.thread_id,
        world_id=request.world_id,
        campaign_id=request.campaign_id,
        revision_id="rev:" + "ab" * 16,
        answer="ok",
    )


def test_create_thread_idempotent_for_identical_binding() -> None:
    repo = InMemoryMindThreadRepository()
    assert (
        repo.create_thread(
            "thr:1",
            world_id="world:demo",
            campaign_id="camp:1",
            surface_id="surface:test",
            tenant_id="tenant:a",
            created_at=NOW,
        )
        == "thr:1"
    )
    assert (
        repo.create_thread(
            "thr:1",
            world_id="world:demo",
            campaign_id="camp:1",
            surface_id="surface:test",
            tenant_id="tenant:a",
            created_at=NOW,
        )
        == "thr:1"
    )


def test_create_thread_rejects_rebinding() -> None:
    repo = InMemoryMindThreadRepository()
    repo.create_thread(
        "thr:1",
        world_id="world:demo",
        campaign_id="camp:1",
        surface_id="surface:test",
        tenant_id="tenant:a",
        created_at=NOW,
    )
    with pytest.raises(IdempotencyConflictError):
        repo.create_thread(
            "thr:1",
            world_id="world:other",
            campaign_id="camp:1",
            surface_id="surface:test",
            tenant_id="tenant:a",
            created_at=NOW,
        )


def test_append_turn_enforces_binding_and_correlation() -> None:
    repo = InMemoryMindThreadRepository()
    repo.create_thread(
        "thr:1",
        world_id="world:demo",
        campaign_id="camp:1",
        surface_id="surface:test",
        tenant_id="tenant:a",
        created_at=NOW,
    )
    req = _request()
    repo.append_turn(req, _response(req))
    assert len(repo.list_turns("thr:1")) == 1

    wrong_world = _request(world_id="world:other")
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(wrong_world, _response(wrong_world))

    req2 = _request(request_id="req:2")
    mismatched = _response(req2).model_copy(update={"request_id": "req:other"})
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req2, mismatched)
