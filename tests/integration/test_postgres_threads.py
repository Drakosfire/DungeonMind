"""PostgreSQL mind-thread binding, correlation, retry, and ordinal order."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CallerScope,
    MindTurnRequest,
    MindTurnResponse,
    SurfaceContext,
)
from dungeonmind.domain.errors import IdempotencyConflictError, ThreadContextMismatchError

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
REV = "rev:" + "ab" * 16


def _create(threads, *, thread_id: str = "thr:pg") -> None:
    threads.create_thread(
        thread_id,
        world_id="world:demo",
        campaign_id="camp:1",
        caller_id="user:1",
        tenant_id="tenant:a",
        created_at=NOW,
    )


def _request(
    *,
    thread_id: str = "thr:pg",
    request_id: str = "req:1",
    world_id: str = "world:demo",
    campaign_id: str | None = "camp:1",
    caller_id: str = "user:1",
    tenant_id: str | None = "tenant:a",
    surface_id: str = "surface:plan",
) -> MindTurnRequest:
    return MindTurnRequest(
        request_id=request_id,
        thread_id=thread_id,
        caller_scope=CallerScope(caller_id=caller_id, tenant_id=tenant_id),
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=Admissibility.GM,
        surface_context=SurfaceContext(surface_id=surface_id),
        message="hello",
    )


def _response(request: MindTurnRequest, *, turn_id: str = "turn:1") -> MindTurnResponse:
    return MindTurnResponse(
        request_id=request.request_id,
        turn_id=turn_id,
        thread_id=request.thread_id,
        world_id=request.world_id,
        campaign_id=request.campaign_id,
        revision_id=REV,
        answer="ok",
    )


@pytest.mark.integration
def test_binding_and_created_at(pg) -> None:
    threads = pg.threads
    _create(threads)
    _create(threads)
    with pytest.raises(IdempotencyConflictError):
        threads.create_thread(
            "thr:pg",
            world_id="world:demo",
            campaign_id="camp:1",
            caller_id="user:1",
            tenant_id="tenant:a",
            created_at=NOW + timedelta(seconds=1),
        )


@pytest.mark.integration
def test_correlation_rejects_mismatches(pg) -> None:
    threads = pg.threads
    _create(threads)
    wrong = _request(world_id="world:other")
    with pytest.raises(ThreadContextMismatchError):
        threads.append_turn(wrong, _response(wrong))

    req = _request(request_id="req:2")
    with pytest.raises(ThreadContextMismatchError):
        threads.append_turn(
            req, _response(req).model_copy(update={"request_id": "req:other"})
        )


@pytest.mark.integration
def test_retry_and_ordinal_order(pg) -> None:
    threads = pg.threads
    _create(threads, thread_id="thr:ord")
    req1 = _request(thread_id="thr:ord", request_id="req:1")
    resp1 = _response(req1, turn_id="turn:1")
    threads.append_turn(req1, resp1)
    threads.append_turn(req1, resp1)

    req2 = _request(
        thread_id="thr:ord",
        request_id="req:2",
        surface_id="surface:play",
    )
    resp2 = _response(req2, turn_id="turn:2")
    threads.append_turn(req2, resp2)

    turns = threads.list_turns("thr:ord")
    assert len(turns) == 2
    assert [resp.turn_id for _, resp in turns] == ["turn:1", "turn:2"]
    assert turns[0][0].surface_context.surface_id == "surface:plan"
    assert turns[1][0].surface_context.surface_id == "surface:play"
