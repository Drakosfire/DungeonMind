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
    assert scoped.snapshot.objects == {}
    assert any(
        r.gap_code == "evidence_source_revision_missing" for r in scoped.rejections
    )


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
    assert "obj:item-sun-ledger" not in scoped.snapshot.objects
    assert any(
        r.gap_code == "evidence_source_revision_artifact_mismatch"
        for r in scoped.rejections
    )


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
    assert scoped.snapshot.objects == {}
    assert any(
        r.gap_code == "evidence_source_domain_mismatch" for r in scoped.rejections
    )


def test_mixed_player_and_gm_evidence_hides_object_under_coarse_policy() -> None:
    """Coarse-object policy: any out-of-scope evidence hides the whole object."""
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
    assert "obj:city-vael" not in scoped.snapshot.objects
    assert "GM Secret Alias".casefold() not in scoped.snapshot.alias_index
    assert scoped.rejections == []  # out-of-scope GM evidence is silent

    # Mention resolution must not resolve the secret alias.
    referents = READER.resolve_mentions(
        scoped.snapshot,
        message="Tell me about GM Secret Alias",
        selected_object_ids=[],
    )
    assert all(r.object_id is None for r in referents)

    context = assemble_agent_context(
        revision_id="rev:test",
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.PLAYER,
        focus=ProjectionFocus(),
        objects=list(scoped.snapshot.objects.values()),
        relationships=[],
        evidence=[],
        source_anchors=[],
        coverage=Coverage(),
    )
    assert "GM Secret Alias" not in context
    assert "GM-only footnote" not in context
    assert "harbor city" not in context


def test_one_valid_and_one_invalid_evidence_hides_object_and_records_gap() -> None:
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
    assert "obj:item-sun-ledger" not in scoped.snapshot.objects
    assert any(
        r.gap_code == "evidence_source_revision_missing"
        and r.missing_id == "srcrev:missing"
        for r in scoped.rejections
    )


def test_player_retracted_gm_artifact_does_not_leak_source_identity() -> None:
    """PLAYER + GM-only retracted artifact: no IDs or lifecycle gaps in coverage."""
    payload = {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": ["Sun Ledger"],
                "evidence_ref_ids": ["ev:ledger"],
                "summary": "player-visible ledger",
            },
            {
                "object_id": "obj:siege-plan",
                "kind": "document",
                "label": "Siege Plan",
                "aliases": [],
                "evidence_ref_ids": ["ev:gm-siege"],
                "summary": "GM-only siege footnotes",
            },
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:player-notes",
                "source_revision_id": "srcrev:player-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:gm-siege",
                "source_artifact_id": "src:gm-secret-siege-plan",
                "source_revision_id": "srcrev:gm-siege-v1",
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
            source_artifact_id="src:gm-secret-siege-plan",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.RETRACTED,
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
            source_revision_id="srcrev:gm-siege-v1",
            source_artifact_id="src:gm-secret-siege-plan",
            content_sha256="cc" * 32,
            body_storage="external",
            locator="fixture://gm-siege",
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
    assert "obj:item-sun-ledger" in scoped.snapshot.objects
    assert "obj:siege-plan" not in scoped.snapshot.objects
    # Out-of-scope GM artifact: silent — no lifecycle rejection identity.
    assert scoped.rejections == []
    exclusion = scoped.object_exclusions["obj:siege-plan"]
    assert exclusion.out_of_scope is True
    assert exclusion.rejections == []
    assert exclusion.scope_unknown is False


def test_player_missing_gm_artifact_id_absent_from_projection_diagnostics() -> None:
    """Missing GM artifact must not emit its identifier as a provenance gap."""
    payload = _base_payload()
    payload["nodes"].append(
        {
            "object_id": "obj:siege-plan",
            "kind": "document",
            "label": "Siege Plan",
            "aliases": [],
            "evidence_ref_ids": ["ev:gm-siege"],
        }
    )
    payload["evidence_refs"].append(
        {
            "evidence_ref_id": "ev:gm-siege",
            "source_artifact_id": "src:gm-secret-siege-plan",
            "source_revision_id": "srcrev:missing",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
        }
    )
    # Player-visible ledger source only — siege artifact intentionally absent.
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:atlas-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.PLAYER,
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
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.PLAYER,
    )
    assert "obj:siege-plan" not in scoped.snapshot.objects
    assert scoped.rejections == []
    assert scoped.object_exclusions["obj:siege-plan"].scope_unknown is True
    rendered = str(
        {
            "rejections": [
                (r.gap_code, r.missing_id) for r in scoped.rejections
            ],
            "exclusions": {
                oid: {
                    "out_of_scope": ex.out_of_scope,
                    "scope_unknown": ex.scope_unknown,
                    "rejections": [(r.gap_code, r.missing_id) for r in ex.rejections],
                }
                for oid, ex in scoped.object_exclusions.items()
            },
        }
    )
    # Flat public-facing rejection list must not name the missing artifact.
    assert "src:gm-secret-siege-plan" not in rendered
    assert "ev:gm-siege" not in str([(r.gap_code, r.missing_id) for r in scoped.rejections])


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
    assert "evidence_source_revision_artifact_mismatch" in response.coverage.gap_codes
    # Untargeted graph corruption elsewhere must not be required for this proof;
    # the ledger is request-targeted via semantic candidates.


def test_player_unrelated_question_hides_retracted_gm_source_identity() -> None:
    """End-to-end: PLAYER ask unrelated; retracted GM source IDs stay out of response."""
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    stored = world_graph.get_revision(fixture.world_id, seed.revision_id)
    assert stored is not None
    payload = dict(stored.graph_payload)
    payload["nodes"] = [
        *list(payload["nodes"]),
        {
            "object_id": "obj:siege-plan",
            "kind": "document",
            "label": "Siege Plan",
            "aliases": [],
            "evidence_ref_ids": ["ev:gm-siege"],
            "summary": "hidden siege prose",
        },
    ]
    payload["evidence_refs"] = [
        *list(payload["evidence_refs"]),
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": "ev:gm-siege",
            "source_artifact_id": "src:gm-secret-siege-plan",
            "source_revision_id": "srcrev:gm-siege-v1",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
            "can_open_source": True,
            "locator": "fixture://gm-siege",
        },
    ]
    from dungeonmind.contracts.graph import PublishRevisionCommand

    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=seed.revision_id,
            expected_parent_revision_id=seed.revision_id,
            operation_ids=["op:inject-gm-siege"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:gm-secret-siege-plan",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=fixture.world_id,
            visibility=Visibility.GM,
            status=SourceStatus.RETRACTED,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:gm-siege-v1",
            source_artifact_id="src:gm-secret-siege-plan",
            content_sha256="dd" * 32,
            body_storage="external",
            locator="fixture://gm-siege",
            created_at=FIXED_NOW,
        )
    )
    binding = fixture.authorized_demo_binding
    threads.create_thread(
        "thr:player-siege",
        world_id=fixture.world_id,
        campaign_id=binding.get("campaign_id"),
        caller_id="caller:player",
        tenant_id=None,
        created_at=FIXED_NOW,
    )
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
    response = service.execute(
        MindTurnRequest(
            request_id="req:player-unrelated-siege",
            thread_id="thr:player-siege",
            caller_scope=CallerScope(caller_id="caller:player", roles=["player"]),
            world_id=fixture.world_id,
            campaign_id=binding.get("campaign_id"),
            requested_revision_id=published.revision_id,
            admissibility=Admissibility.PLAYER,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id="landingpage:player"),
            message="What is the Sun Ledger?",
        )
    )
    rendered = str(response.model_dump(mode="json"))
    assert "src:gm-secret-siege-plan" not in rendered
    assert "ev:gm-siege" not in rendered
    assert "evidence_source_inactive" not in response.coverage.gap_codes
    assert "retracted" not in rendered.casefold()


def test_player_missing_secret_artifact_absent_everywhere_in_response() -> None:
    """End-to-end: missing src:gm-secret-siege-plan must not appear in the response."""
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    stored = world_graph.get_revision(fixture.world_id, seed.revision_id)
    assert stored is not None
    payload = dict(stored.graph_payload)
    payload["nodes"] = [
        *list(payload["nodes"]),
        {
            "object_id": "obj:siege-plan",
            "kind": "document",
            "label": "Siege Plan",
            "aliases": [],
            "evidence_ref_ids": ["ev:gm-siege"],
        },
    ]
    payload["evidence_refs"] = [
        *list(payload["evidence_refs"]),
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": "ev:gm-siege",
            "source_artifact_id": "src:gm-secret-siege-plan",
            "source_revision_id": "srcrev:gm-siege-v1",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
            "can_open_source": True,
            "locator": "fixture://gm-siege",
        },
    ]
    from dungeonmind.contracts.graph import PublishRevisionCommand

    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=seed.revision_id,
            expected_parent_revision_id=seed.revision_id,
            operation_ids=["op:inject-missing-gm-siege"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
    # Deliberately do not insert src:gm-secret-siege-plan.
    binding = fixture.authorized_demo_binding
    threads.create_thread(
        "thr:player-missing-siege",
        world_id=fixture.world_id,
        campaign_id=binding.get("campaign_id"),
        caller_id="caller:player",
        tenant_id=None,
        created_at=FIXED_NOW,
    )
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
    response = service.execute(
        MindTurnRequest(
            request_id="req:player-missing-siege",
            thread_id="thr:player-missing-siege",
            caller_scope=CallerScope(caller_id="caller:player", roles=["player"]),
            world_id=fixture.world_id,
            campaign_id=binding.get("campaign_id"),
            requested_revision_id=published.revision_id,
            admissibility=Admissibility.PLAYER,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id="landingpage:player"),
            message="What is the Sun Ledger?",
        )
    )
    rendered = str(response.model_dump(mode="json"))
    assert "src:gm-secret-siege-plan" not in rendered
    assert "ev:gm-siege" not in rendered
    assert "evidence_source_artifact_missing" not in response.coverage.gap_codes
    assert "stored_provenance_invalid" not in response.coverage.gap_codes


def test_gm_targeted_broken_provenance_surfaces_selected_gap() -> None:
    """GM targeting an object with broken in-scope provenance gets a detailed gap."""
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    # Corrupt revision ownership after seed.
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
            request_id="req:gm-targeted-broken",
            thread_id=str(binding["thread_id"]),
            caller_scope=CallerScope(
                caller_id=str(binding["caller_id"]),
                tenant_id=binding.get("tenant_id"),
                roles=list(binding["roles"]),
            ),
            world_id=str(binding["world_id"]),
            campaign_id=binding.get("campaign_id"),
            requested_revision_id=seed.revision_id,
            admissibility=Admissibility.GM,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(
                surface_id=str(binding["surface_id"]),
                selected_object_ids=["obj:item-sun-ledger"],
            ),
            message="Inspect the selected object.",
        )
    )
    assert "evidence_source_revision_artifact_mismatch" in response.coverage.gap_codes
    assert "obj:item-sun-ledger" not in {
        proj.payload.get("object_id")
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    }


def test_graph_global_broken_provenance_not_copied_into_unrelated_response() -> None:
    """In-scope broken provenance on an untargeted object must not enter coverage."""
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    stored = world_graph.get_revision(fixture.world_id, seed.revision_id)
    assert stored is not None
    payload = dict(stored.graph_payload)
    # Add a separate GM object with broken revision pointer; leave Sun Ledger intact.
    payload["nodes"] = [
        *list(payload["nodes"]),
        {
            "object_id": "obj:broken-side",
            "kind": "document",
            "label": "Broken Side Note",
            "aliases": [],
            "evidence_ref_ids": ["ev:broken-side"],
        },
    ]
    payload["evidence_refs"] = [
        *list(payload["evidence_refs"]),
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": "ev:broken-side",
            "source_artifact_id": "src:atlas-notes",
            "source_revision_id": "srcrev:missing-side",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
            "can_open_source": True,
            "locator": "fixture://broken-side",
        },
    ]
    from dungeonmind.contracts.graph import PublishRevisionCommand

    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=seed.revision_id,
            expected_parent_revision_id=seed.revision_id,
            operation_ids=["op:inject-broken-side"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
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
            request_id="req:gm-unrelated-global",
            thread_id=str(binding["thread_id"]),
            caller_scope=CallerScope(
                caller_id=str(binding["caller_id"]),
                tenant_id=binding.get("tenant_id"),
                roles=list(binding["roles"]),
            ),
            world_id=str(binding["world_id"]),
            campaign_id=binding.get("campaign_id"),
            requested_revision_id=published.revision_id,
            admissibility=Admissibility.GM,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id=str(binding["surface_id"])),
            message="What is the Sun Ledger?",
        )
    )
    assert "evidence_source_revision_missing" not in response.coverage.gap_codes
    assert "srcrev:missing-side" not in response.coverage.missing
    assert "brass-bound" in response.answer.casefold()


def test_player_cannot_resolve_or_inspect_mixed_provenance_gm_fields() -> None:
    """End-to-end: mixed GM/player evidence never leaks secret alias or summary."""
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    seed = seed_curated_mind_turn(
        world_graph=world_graph,
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        threads=threads,
        fixture=fixture,
    )
    stored = world_graph.get_revision(fixture.world_id, seed.revision_id)
    assert stored is not None
    payload = dict(stored.graph_payload)
    # Retarget Vael to mixed player+GM evidence with a secret alias/summary.
    nodes = []
    for node in payload["nodes"]:
        if node["object_id"] == "obj:city-vael":
            nodes.append(
                {
                    **node,
                    "aliases": ["Vael City", "GM Secret Alias"],
                    "summary": "harbor city with a GM-only footnote",
                    "evidence_ref_ids": ["ev:player-vael", "ev:gm-vael"],
                }
            )
        else:
            nodes.append(node)
    payload["nodes"] = nodes
    evidence_refs = [
        row
        for row in payload["evidence_refs"]
        if row["evidence_ref_id"] != "ev:vael"
    ]
    evidence_refs.extend(
        [
            {
                "schema_version": "dm_evidence_ref_v1",
                "evidence_ref_id": "ev:player-vael",
                "source_artifact_id": "src:player-notes",
                "source_revision_id": "srcrev:player-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://player#vael",
            },
            {
                "schema_version": "dm_evidence_ref_v1",
                "evidence_ref_id": "ev:gm-vael",
                "source_artifact_id": "src:gm-notes",
                "source_revision_id": "srcrev:gm-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://gm#vael",
            },
        ]
    )
    payload["evidence_refs"] = evidence_refs
    from dungeonmind.contracts.graph import PublishRevisionCommand

    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=seed.revision_id,
            expected_parent_revision_id=seed.revision_id,
            operation_ids=["op:mixed-vael-evidence"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:player-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=fixture.world_id,
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:gm-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=fixture.world_id,
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
    # Player-visible thread/request against the mixed-provenance revision.
    binding = fixture.authorized_demo_binding
    # Use a dedicated player thread to avoid GM demo binding constraints in service.
    threads.create_thread(
        "thr:player-mixed",
        world_id=fixture.world_id,
        campaign_id=binding.get("campaign_id"),
        caller_id="caller:player",
        tenant_id=None,
        created_at=FIXED_NOW,
    )
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
    response = service.execute(
        MindTurnRequest(
            request_id="req:mixed-secret-alias",
            thread_id="thr:player-mixed",
            caller_scope=CallerScope(caller_id="caller:player", roles=["player"]),
            world_id=fixture.world_id,
            campaign_id=binding.get("campaign_id"),
            requested_revision_id=published.revision_id,
            admissibility=Admissibility.PLAYER,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id="landingpage:player"),
            message="Tell me about GM Secret Alias",
        )
    )
    assert not any(r.object_id == "obj:city-vael" for r in response.resolved_referents)
    briefs = [
        proj.payload
        for proj in response.semantic_projections
        if proj.kind == "entity_brief"
    ]
    assert all(p.get("object_id") != "obj:city-vael" for p in briefs)
    for brief in briefs:
        aliases = brief.get("aliases") or []
        assert "GM Secret Alias" not in aliases
        assert "GM-only footnote" not in str(brief.get("summary") or "")
    # User message may mention the secret phrase; admitted ledgers must not echo it.
    admitted = {
        "answer": response.answer,
        "claims": [c.model_dump(mode="json") for c in response.claims],
        "evidence": [e.model_dump(mode="json") for e in response.evidence],
        "projections": [p.model_dump(mode="json") for p in response.semantic_projections],
        "anchors": [a.model_dump(mode="json") for a in response.source_anchors],
    }
    admitted_text = str(admitted)
    assert "GM Secret Alias" not in admitted_text
    assert "GM-only footnote" not in admitted_text
    assert "do not have grounded knowledge" in response.answer.casefold()
