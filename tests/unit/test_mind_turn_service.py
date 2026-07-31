"""Unit tests for MindTurnService against in-memory repos + curated fixture."""

from __future__ import annotations

import json
from typing import Any

import pytest

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.agents.protocol import AgentTurnContext
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import ProjectionFocus
from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import IdempotencyConflictError, RevisionNotFoundError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.infrastructure.memory import (
    InMemoryEmbeddingRunRepository,
    InMemoryMindThreadRepository,
    InMemoryRetrievalSessionRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.service.demo_access import DemoAccessBinding, authorize_demo_request

from ..conftest import FIXED_NOW


def _build_service() -> tuple[MindTurnService, Any, DemoAccessBinding, str]:
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    semantic_search = InMemorySemanticSearch(semantic_documents, embedding_runs)

    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    binding = DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)
    service = MindTurnService(
        world_graph=world_graph,
        retrieval_sessions=retrieval_sessions,
        threads=threads,
        semantic_documents=semantic_documents,
        semantic_search=semantic_search,
        sources=sources,
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(FIXED_NOW),
    )
    return service, threads, binding, seed.revision_id


def _authorized_request(
    binding: DemoAccessBinding,
    *,
    request_id: str,
    message: str,
    requested_revision_id: str | None = None,
) -> MindTurnRequest:
    raw = MindTurnRequest(
        request_id=request_id,
        thread_id=binding.thread_id,
        caller_scope=CallerScope(
            caller_id=binding.caller_id,
            tenant_id=binding.tenant_id,
            roles=list(binding.roles),
        ),
        world_id=binding.world_id,
        campaign_id=binding.campaign_id,
        requested_revision_id=requested_revision_id,
        admissibility=binding.admissibility,
        focus=ProjectionFocus(),
        surface_context=SurfaceContext(surface_id=binding.surface_id, mode="ask"),
        message=message,
    )
    return authorize_demo_request(raw, binding=binding)


def _dump_tree(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump_tree(item) for item in value]
    if isinstance(value, dict):
        return {k: _dump_tree(v) for k, v in value.items()}
    return value


def _assert_no_similarity_scores(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key not in {"score", "similarity", "similarity_score"}
            _assert_no_similarity_scores(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_similarity_scores(item)


def test_omitted_revision_resolves_head() -> None:
    service, _threads, binding, revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:head-resolve",
            message="Who safeguards the Sun Ledger?",
            requested_revision_id=None,
        )
    )
    assert response.revision_id == revision_id


def test_explicit_valid_revision_reported() -> None:
    service, _threads, binding, revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:explicit-rev",
            message="Who safeguards the Sun Ledger?",
            requested_revision_id=revision_id,
        )
    )
    assert response.revision_id == revision_id


def test_unknown_revision_raises() -> None:
    service, _threads, binding, _revision_id = _build_service()
    with pytest.raises(RevisionNotFoundError):
        service.execute(
            _authorized_request(
                binding,
                request_id="req:missing-rev",
                message="Who safeguards the Sun Ledger?",
                requested_revision_id="rev:" + "ff" * 16,
            )
        )


def test_curated_who_safeguards_sun_ledger() -> None:
    service, _threads, binding, _revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:safeguards",
            message="Who safeguards the Sun Ledger?",
        )
    )
    assert "Mere Astor" in response.answer
    assert "safeguard" in response.answer.casefold()


def test_curated_where_mere_astor_lives() -> None:
    service, _threads, binding, _revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:resides",
            message="Where does Mere Astor live?",
        )
    )
    assert "Vael" in response.answer


def test_curated_what_is_sun_ledger() -> None:
    service, _threads, binding, _revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:ledger",
            message="What is the Sun Ledger?",
        )
    )
    assert "Sun Ledger" in response.answer


def test_curated_moon_king_abstains() -> None:
    service, _threads, binding, _revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:moon-king",
            message="Who is the Moon King?",
        )
    )
    assert "Moon King" not in response.answer
    assert response.claims == []
    assert "do not have grounded knowledge" in response.answer.casefold()
    invented = {"moon king", "obj:moon", "obj:moon-king"}
    known = {item.casefold() for item in response.coverage.known}
    assert not (invented & known)


def test_agent_context_has_no_auth_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _threads, binding, _revision_id = _build_service()
    captured: list[AgentTurnContext] = []
    original = service._agent_adapter.execute_turn

    def _capture(context: AgentTurnContext) -> Any:
        captured.append(context)
        return original(context)

    monkeypatch.setattr(service._agent_adapter, "execute_turn", _capture)
    service.execute(
        _authorized_request(
            binding,
            request_id="req:auth-sanitize",
            message="Who safeguards the Sun Ledger?",
        )
    )
    assert len(captured) == 1
    agent_input = captured[0].input
    dumped = agent_input.model_dump()
    assert "caller_id" not in dumped
    assert "tenant_id" not in dumped
    assert "roles" not in dumped
    assembled = json.loads(agent_input.assembled_context)
    assert "caller_id" not in assembled
    assert "tenant_id" not in assembled
    assert "roles" not in assembled


def test_policy_enabled_tools_empty_and_revision_pin_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _threads, binding, revision_id = _build_service()
    captured: list[AgentTurnContext] = []
    original = service._agent_adapter.execute_turn

    def _capture(context: AgentTurnContext) -> Any:
        captured.append(context)
        return original(context)

    monkeypatch.setattr(service._agent_adapter, "execute_turn", _capture)
    service.execute(
        _authorized_request(
            binding,
            request_id="req:policy",
            message="Who safeguards the Sun Ledger?",
        )
    )
    policy = captured[0].capability_policy
    assert policy.enabled_tools == []
    assert policy.tool_rules == []
    assert policy.graph_scope is not None
    assert policy.graph_scope.revision_pin == revision_id
    assert policy.graph_scope.revision_pin == captured[0].input.revision_id


def test_replay_same_request_id_and_payload() -> None:
    service, threads, binding, _revision_id = _build_service()
    request = _authorized_request(
        binding,
        request_id="req:replay",
        message="Who safeguards the Sun Ledger?",
    )
    first = service.execute(request)
    assert service.agent_invocation_count == 1
    second = service.execute(request)
    assert service.agent_invocation_count == 1
    assert canonical_json(first.model_dump(mode="json")) == canonical_json(
        second.model_dump(mode="json")
    )
    turns = threads.list_turns(binding.thread_id)
    assert len(turns) == 1


def test_same_request_id_changed_message_conflicts() -> None:
    service, _threads, binding, _revision_id = _build_service()
    first = _authorized_request(
        binding,
        request_id="req:conflict",
        message="Who safeguards the Sun Ledger?",
    )
    service.execute(first)
    changed = _authorized_request(
        binding,
        request_id="req:conflict",
        message="Where does Mere Astor live?",
    )
    with pytest.raises(IdempotencyConflictError):
        service.execute(changed)


def test_append_failure_recovery_reuses_session_without_reinvoking_agent() -> None:
    service, threads, binding, _revision_id = _build_service()
    request = _authorized_request(
        binding,
        request_id="req:recovery",
        message="Who safeguards the Sun Ledger?",
    )
    first = service.execute(request)
    assert service.agent_invocation_count == 1
    assert len(threads.list_turns(binding.thread_id)) == 1

    # Simulate append failure after session create: session remains, turn gone.
    threads._turns[binding.thread_id] = []
    assert threads.list_turns(binding.thread_id) == []

    recovered = service.execute(request)
    assert service.agent_invocation_count == 1
    assert recovered.request_id == first.request_id
    assert canonical_json(recovered.model_dump(mode="json")) == canonical_json(
        first.model_dump(mode="json")
    )
    assert len(threads.list_turns(binding.thread_id)) == 1


def test_projections_actions_source_reads_and_no_similarity() -> None:
    service, _threads, binding, _revision_id = _build_service()
    response = service.execute(
        _authorized_request(
            binding,
            request_id="req:projections",
            message="Who safeguards the Sun Ledger?",
        )
    )
    kinds = {proj.kind for proj in response.semantic_projections}
    assert "entity_brief" in kinds
    assert "relationship_list" in kinds
    assert "evidence_summary" in kinds

    assert response.source_reads == []

    admitted_anchor_ids = {anchor.anchor_id for anchor in response.source_anchors}
    for action in response.suggested_actions:
        if action.kind == "open_source":
            anchor_id = action.arguments.get("source_anchor_id")
            assert anchor_id in admitted_anchor_ids

    _assert_no_similarity_scores(_dump_tree(response.evidence))
    _assert_no_similarity_scores(_dump_tree(response.claims))
