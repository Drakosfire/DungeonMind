"""Thread binding and turn-correlation enforcement (caller-private, cross-surface)."""

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


def _create(
    repo: InMemoryMindThreadRepository,
    *,
    thread_id: str = "thr:1",
    world_id: str = "world:demo",
    campaign_id: str | None = "camp:1",
    caller_id: str = "user:1",
    tenant_id: str | None = "tenant:a",
) -> None:
    repo.create_thread(
        thread_id,
        world_id=world_id,
        campaign_id=campaign_id,
        caller_id=caller_id,
        tenant_id=tenant_id,
        created_at=NOW,
    )


def _request(
    *,
    thread_id: str = "thr:1",
    world_id: str = "world:demo",
    campaign_id: str | None = "camp:1",
    tenant_id: str | None = "tenant:a",
    caller_id: str = "user:1",
    request_id: str = "req:1",
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
        revision_id="rev:" + "ab" * 16,
        answer="ok",
    )


def test_create_thread_idempotent_for_identical_binding() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    _create(repo)


def test_create_thread_rejects_world_rebinding() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    with pytest.raises(IdempotencyConflictError):
        _create(repo, world_id="world:other")


def test_create_thread_rejects_campaign_rebinding() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    with pytest.raises(IdempotencyConflictError):
        _create(repo, campaign_id="camp:other")


def test_create_thread_rejects_tenant_rebinding() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    with pytest.raises(IdempotencyConflictError):
        _create(repo, tenant_id="tenant:other")


def test_create_thread_rejects_caller_rebinding() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    with pytest.raises(IdempotencyConflictError):
        _create(repo, caller_id="user:other")


def test_surface_may_change_between_turns() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    req_a = _request(surface_id="surface:plan", request_id="req:1")
    repo.append_turn(req_a, _response(req_a, turn_id="turn:1"))
    req_b = _request(surface_id="surface:play", request_id="req:2")
    repo.append_turn(req_b, _response(req_b, turn_id="turn:2"))
    assert len(repo.list_turns("thr:1")) == 2


def test_append_rejects_correlation_mismatches() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)

    wrong_world = _request(world_id="world:other")
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(wrong_world, _response(wrong_world))

    req = _request(request_id="req:2")
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req, _response(req).model_copy(update={"request_id": "req:other"}))
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req, _response(req).model_copy(update={"thread_id": "thr:other"}))
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req, _response(req).model_copy(update={"world_id": "world:other"}))
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req, _response(req).model_copy(update={"campaign_id": "camp:other"}))


def test_cross_caller_append_rejected_same_tenant() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo, caller_id="user:1", tenant_id="tenant:a")
    req = _request(caller_id="user:2", tenant_id="tenant:a")
    with pytest.raises(ThreadContextMismatchError):
        repo.append_turn(req, _response(req))


def test_exact_append_retry_is_idempotent() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    req = _request()
    resp = _response(req)
    repo.append_turn(req, resp)
    repo.append_turn(req, resp)
    assert len(repo.list_turns("thr:1")) == 1


def test_same_turn_id_changed_payload_rejected() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    req = _request()
    resp = _response(req)
    repo.append_turn(req, resp)
    changed = resp.model_copy(update={"answer": "different"})
    with pytest.raises(IdempotencyConflictError):
        repo.append_turn(req, changed)


def test_same_request_id_different_turn_id_rejected() -> None:
    repo = InMemoryMindThreadRepository()
    _create(repo)
    req = _request(request_id="req:1")
    repo.append_turn(req, _response(req, turn_id="turn:1"))
    with pytest.raises(IdempotencyConflictError):
        repo.append_turn(req, _response(req, turn_id="turn:2"))
