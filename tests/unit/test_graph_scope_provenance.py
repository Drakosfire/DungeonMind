"""Adversarial provenance tests for scoped graph projection."""

from __future__ import annotations

from datetime import UTC, datetime

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.application.context_assembly import assemble_agent_context
from dungeonmind.application.graph_scope import project_scoped_snapshot
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.retrieval import Coverage
from dungeonmind.contracts.vocabulary import Visibility
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
READER = UnionGraphV1SnapshotReader()


def _base_payload() -> dict:
    return {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": ["Sun Ledger"],
                "evidence_ref_ids": ["ev:ledger"],
                "summary": "a brass-bound account of every dawn debt owed in Vael",
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "locator": "fixture://atlas-notes#sun-ledger",
            }
        ],
    }


def _sources_with_atlas(
    *,
    revision_artifact_id: str = "src:atlas-notes",
) -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:atlas-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:other-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:atlas-notes-v1",
            source_artifact_id=revision_artifact_id,
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://atlas-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def test_missing_source_revision_hides_object_and_summary() -> None:
    payload = _base_payload()
    payload["evidence_refs"][0]["source_revision_id"] = "srcrev:missing"
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)
    sources = _sources_with_atlas()
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
    )
    assert scoped.objects == {}


def test_revision_belonging_to_other_artifact_hides_object() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_base_payload())
    sources = _sources_with_atlas(revision_artifact_id="src:other-notes")
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
    )
    assert "obj:item-sun-ledger" not in scoped.objects


def test_source_domain_mismatch_hides_object() -> None:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:atlas-notes",
            source_domain=SourceDomain.PREP,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:atlas-notes-v1",
            source_artifact_id="src:atlas-notes",
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://atlas-notes",
            created_at=FIXED_NOW,
        )
    )
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_base_payload())
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
    )
    assert scoped.objects == {}


def test_mixed_player_and_gm_evidence_keeps_only_player_ids() -> None:
    payload = {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:city-vael",
                "kind": "location",
                "label": "Vael",
                "aliases": ["Vael City", "GM Secret Alias"],
                "evidence_ref_ids": ["ev:player", "ev:gm"],
                "summary": "harbor city with a GM-only footnote",
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:player",
                "source_artifact_id": "src:player-notes",
                "source_revision_id": "srcrev:player-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:gm",
                "source_artifact_id": "src:gm-notes",
                "source_revision_id": "srcrev:gm-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
        ],
    }
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:player-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:gm-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:player-v1",
            source_artifact_id="src:player-notes",
            content_sha256="bb" * 32,
            body_storage="external",
            locator="fixture://player",
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:gm-v1",
            source_artifact_id="src:gm-notes",
            content_sha256="cc" * 32,
            body_storage="external",
            locator="fixture://gm",
            created_at=FIXED_NOW,
        )
    )
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.PLAYER,
    )
    obj = scoped.objects["obj:city-vael"]
    assert obj.evidence_ref_ids == ["ev:player"]
    assert "ev:gm" not in scoped.evidence
    context = assemble_agent_context(
        revision_id="rev:test",
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.PLAYER,
        focus=ProjectionFocus(),
        objects=[obj],
        relationships=[],
        evidence=[],
        source_anchors=[],
        coverage=Coverage(),
    )
    assert "ev:gm" not in context
    assert "ev:player" in context


def test_one_valid_and_one_invalid_evidence_keeps_only_valid() -> None:
    payload = {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": [],
                "evidence_ref_ids": ["ev:ledger", "ev:broken"],
                "summary": "a brass-bound account of every dawn debt owed in Vael",
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:broken",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:missing",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
        ],
    }
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)
    sources = _sources_with_atlas()
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
    )
    obj = scoped.objects["obj:item-sun-ledger"]
    assert obj.evidence_ref_ids == ["ev:ledger"]
    assert "ev:broken" not in scoped.evidence


def test_broken_revision_ownership_does_not_reach_agent_as_inference() -> None:
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    # Corrupt revision ownership after seed (bypasses put() idempotency).
    existing = sources._revisions["srcrev:atlas-notes-v1"]
    sources._revisions["srcrev:atlas-notes-v1"] = existing.model_copy(
        update={"source_artifact_id": "src:other-notes"}
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:other-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=fixture.world_id,
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    # All curated evidence shares srcrev:atlas-notes-v1, so the graph drops.
    service = MindTurnService(
        world_graph=world_graph,
        retrieval_sessions=retrieval_sessions,
        threads=threads,
        semantic_documents=semantic_documents,
        semantic_search=InMemorySemanticSearch(semantic_documents, embedding_runs),
        sources=sources,
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(FIXED_NOW),
    )
    binding = fixture.authorized_demo_binding
    response = service.execute(
        MindTurnRequest(
            request_id="req:broken-revision",
            thread_id=str(binding["thread_id"]),
            caller_scope=CallerScope(
                caller_id=str(binding["caller_id"]),
                tenant_id=binding.get("tenant_id"),
                roles=list(binding["roles"]),
            ),
            world_id=str(binding["world_id"]),
            campaign_id=binding.get("campaign_id"),
            admissibility=Admissibility.GM,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id=str(binding["surface_id"])),
            message="What is the Sun Ledger?",
        )
    )
    assert "brass-bound" not in response.answer.casefold()
    assert response.claims == []
    assert "obj:item-sun-ledger" not in {
        proj.payload.get("object_id")
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    }
