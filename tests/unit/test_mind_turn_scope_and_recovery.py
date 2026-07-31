"""Adversarial Mind Turn tests for scope filtering and recovery binding."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.application.mind_turn import FixedClock, MindTurnService, _session_id_for
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, FocusKind, ProjectionFocus
from dungeonmind.contracts.vocabulary import Visibility
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

FIXED_NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _repos():
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    semantic_search = InMemorySemanticSearch(semantic_documents, embedding_runs)
    return {
        "world_graph": world_graph,
        "sources": sources,
        "embedding_runs": embedding_runs,
        "semantic_documents": semantic_documents,
        "threads": threads,
        "retrieval_sessions": retrieval_sessions,
        "semantic_search": semantic_search,
    }


def _service(repos: dict[str, Any], fixture) -> MindTurnService:
    return MindTurnService(
        world_graph=repos["world_graph"],
        retrieval_sessions=repos["retrieval_sessions"],
        threads=repos["threads"],
        semantic_documents=repos["semantic_documents"],
        semantic_search=repos["semantic_search"],
        sources=repos["sources"],
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(FIXED_NOW),
    )


def _seeded():
    fixture = load_curated_mind_turn_fixture()
    repos = _repos()
    seed = seed_curated_mind_turn(
        world_graph=repos["world_graph"],
        sources=repos["sources"],
        embedding_runs=repos["embedding_runs"],
        semantic_documents=repos["semantic_documents"],
        threads=repos["threads"],
        fixture=fixture,
    )
    service = _service(repos, fixture)
    return fixture, repos, service, seed.revision_id


def _player_request(
    fixture,
    *,
    request_id: str,
    message: str,
    selected_object_ids: list[str] | None = None,
    campaign_id: str | None = "camp:demo",
) -> MindTurnRequest:
    binding = fixture.authorized_demo_binding
    return MindTurnRequest(
        request_id=request_id,
        thread_id=binding["thread_id"],
        caller_scope=CallerScope(
            caller_id=binding["caller_id"],
            tenant_id=binding["tenant_id"],
            roles=list(binding["roles"]),
        ),
        world_id=binding["world_id"],
        campaign_id=campaign_id,
        admissibility=Admissibility.PLAYER,
        focus=ProjectionFocus(),
        surface_context=SurfaceContext(
            surface_id=binding["surface_id"],
            mode="ask",
            selected_object_ids=selected_object_ids or [],
        ),
        message=message,
    )


def _gm_request(
    fixture,
    *,
    request_id: str,
    message: str,
    **overrides: Any,
) -> MindTurnRequest:
    binding = fixture.authorized_demo_binding
    body = {
        "request_id": request_id,
        "thread_id": binding["thread_id"],
        "caller_scope": CallerScope(
            caller_id=binding["caller_id"],
            tenant_id=binding["tenant_id"],
            roles=list(binding["roles"]),
        ),
        "world_id": binding["world_id"],
        "campaign_id": binding["campaign_id"],
        "admissibility": Admissibility.GM,
        "focus": ProjectionFocus(),
        "surface_context": SurfaceContext(surface_id=binding["surface_id"], mode="ask"),
        "message": message,
    }
    body.update(overrides)
    return MindTurnRequest(**body)


def test_player_exact_label_cannot_bypass_gm_graph_filter() -> None:
    fixture, _repos, service, _revision_id = _seeded()
    response = service.execute(
        _player_request(
            fixture,
            request_id="req:player-label",
            message="Who is Mere Astor?",
        )
    )
    object_ids = {
        proj.payload.get("object_id")
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    }
    assert "obj:npc-mere-astor" not in object_ids
    assert not any(r.object_id == "obj:npc-mere-astor" for r in response.resolved_referents)
    assert response.claims == []
    assert "do not have grounded knowledge" in response.answer.casefold()


def test_player_selected_id_and_alias_and_one_hop_cannot_bypass() -> None:
    fixture, _repos, service, _revision_id = _seeded()
    response = service.execute(
        _player_request(
            fixture,
            request_id="req:player-selected",
            message="Tell me about Astor",
            selected_object_ids=["obj:npc-mere-astor", "obj:item-sun-ledger"],
        )
    )
    object_ids = {
        proj.payload.get("object_id")
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    }
    assert object_ids == set()
    assert response.claims == []
    assert all(r.object_id is None for r in response.resolved_referents)


def test_cross_campaign_and_world_scope_exclude_foreign_sources() -> None:
    from dungeonmind.application.graph_scope import (
        project_scoped_snapshot,
        source_artifact_in_scope,
    )
    from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader

    fixture, repos, service, revision_id = _seeded()
    foreign = SourceArtifact(
        source_artifact_id="src:camp-only-notes",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=fixture.world_id,
        campaign_id="camp:other",
        visibility=Visibility.GM,
        status=SourceStatus.ACTIVE,
        created_at=FIXED_NOW,
    )
    repos["sources"].put_artifact(foreign)
    repos["sources"].put_revision(
        SourceRevision(
            source_revision_id="srcrev:camp-only-v1",
            source_artifact_id="src:camp-only-notes",
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://camp-only",
            created_at=FIXED_NOW,
        )
    )
    assert not source_artifact_in_scope(
        foreign,
        world_id=fixture.world_id,
        campaign_id=None,
        admissibility=Admissibility.GM,
    )
    assert not source_artifact_in_scope(
        foreign,
        world_id=fixture.world_id,
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
    )

    stored = repos["world_graph"].get_revision(fixture.world_id, revision_id)
    assert stored is not None
    payload = dict(stored.graph_payload)
    evidence_refs = []
    for row in payload["evidence_refs"]:
        if row["evidence_ref_id"] == "ev:ledger":
            evidence_refs.append(
                {
                    **row,
                    "source_artifact_id": "src:camp-only-notes",
                    "source_revision_id": "srcrev:camp-only-v1",
                }
            )
        else:
            evidence_refs.append(row)
    payload["evidence_refs"] = evidence_refs
    published = repos["world_graph"].publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=revision_id,
            expected_parent_revision_id=revision_id,
            operation_ids=["op:retarget-ledger-evidence"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
    parsed = UnionGraphV1SnapshotReader().parse(
        graph_schema=stored.revision.graph_schema,
        graph_payload=payload,
    )
    world_projected = project_scoped_snapshot(
        parsed,
        sources=repos["sources"],
        world_id=fixture.world_id,
        campaign_id=None,
        admissibility=Admissibility.GM,
    )
    assert "obj:item-sun-ledger" not in world_projected.snapshot.objects

    response = service.execute(
        _gm_request(
            fixture,
            request_id="req:cross-campaign",
            message="What is the Sun Ledger?",
            requested_revision_id=published.revision_id,
        )
    )
    object_ids = {
        proj.payload.get("object_id")
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    }
    # Ledger evidence belongs to camp:other; camp:demo must not surface it.
    assert "obj:item-sun-ledger" not in object_ids


def _simulate_session_without_turn(repos: dict[str, Any], thread_id: str) -> None:
    repos["threads"]._turns[thread_id] = []


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            lambda req: req.model_copy(update={"message": "Where does Mere Astor live?"}),
            id="message",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={"requested_revision_id": "rev:" + "ab" * 16}
            ),
            id="requested_revision",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={
                    "focus": ProjectionFocus(kind=FocusKind.SESSION, session_id="sess:1")
                }
            ),
            id="focus",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={
                    "surface_context": req.surface_context.model_copy(
                        update={"selected_object_ids": ["obj:npc-mere-astor"]}
                    )
                }
            ),
            id="selected_object_ids",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={
                    "surface_context": req.surface_context.model_copy(
                        update={"mode": "inspect"}
                    )
                }
            ),
            id="surface_mode",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={
                    "surface_context": req.surface_context.model_copy(
                        update={"selected_document_ref": "doc:demo"}
                    )
                }
            ),
            id="selected_document_ref",
        ),
        pytest.param(
            lambda req: req.model_copy(
                update={
                    "surface_context": req.surface_context.model_copy(
                        update={"active_artifact_refs": ["art:demo"]}
                    )
                }
            ),
            id="active_artifact_refs",
        ),
    ],
)
def test_recovery_rejects_changed_request_fields(mutator) -> None:
    fixture, repos, service, _revision_id = _seeded()
    original = _gm_request(
        fixture,
        request_id="req:recovery-conflict",
        message="Who safeguards the Sun Ledger?",
    )
    service.execute(original)
    _simulate_session_without_turn(repos, fixture.authorized_demo_binding["thread_id"])
    assert repos["retrieval_sessions"].get(_session_id_for(original.request_id)) is not None

    changed = mutator(original)
    with pytest.raises(IdempotencyConflictError):
        service.execute(changed)


def test_recovery_fails_closed_when_pinned_revision_unreadable() -> None:
    fixture, repos, service, revision_id = _seeded()
    request = _gm_request(
        fixture,
        request_id="req:recovery-missing-rev",
        message="Who safeguards the Sun Ledger?",
    )
    service.execute(request)
    _simulate_session_without_turn(repos, fixture.authorized_demo_binding["thread_id"])
    session = repos["retrieval_sessions"].get(_session_id_for(request.request_id))
    assert session is not None
    # Corrupt storage: drop the pinned revision while leaving the session.
    repos["world_graph"]._revisions.pop((fixture.world_id, revision_id), None)
    with pytest.raises(RevisionNotFoundError):
        service.execute(request)
