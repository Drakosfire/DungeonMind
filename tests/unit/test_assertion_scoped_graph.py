"""Parser, scoper, resolution, projection, and leak proof for dm_union_graph_v2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.application.graph_scope import project_scoped_snapshot
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    UnionGraphV1SnapshotReader,
    UnionGraphV2SnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import PersistenceIntegrityError
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
from dungeonmind.service.demo_access import DemoAccessBinding

FIXED_NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "curated_assertion_scope_v1.json"
)
V2 = UnionGraphV2SnapshotReader()
VERSIONED = VersionedUnionGraphSnapshotReader()

GM_ALIAS = "Debtbook of the First Light"
GM_SUMMARY = "a brass-bound account that records the names owed to the buried sun"
PLAYER_ALIAS = "Dawn Ledger"


def _v2_payload() -> dict:
    return {
        "world_id": "world:assertion-scope-demo",
        "nodes": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "evidence_ref_ids": ["ev:ledger-core-player"],
                "alias_assertions": [
                    {
                        "assertion_id": "asrt:ledger-alias-dawn",
                        "alias": PLAYER_ALIAS,
                        "evidence_ref_ids": ["ev:ledger-alias-player"],
                    },
                    {
                        "assertion_id": "asrt:ledger-alias-debtbook",
                        "alias": GM_ALIAS,
                        "evidence_ref_ids": ["ev:ledger-alias-gm"],
                    },
                ],
                "summary_assertion": {
                    "assertion_id": "asrt:ledger-summary-secret",
                    "summary": GM_SUMMARY,
                    "evidence_ref_ids": ["ev:ledger-summary-gm"],
                },
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:ledger-core-player",
                "source_artifact_id": "src:assertion-player-notes",
                "source_revision_id": "srcrev:assertion-player-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:ledger-alias-player",
                "source_artifact_id": "src:assertion-player-notes",
                "source_revision_id": "srcrev:assertion-player-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:ledger-alias-gm",
                "source_artifact_id": "src:assertion-gm-notes",
                "source_revision_id": "srcrev:assertion-gm-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:ledger-summary-gm",
                "source_artifact_id": "src:assertion-gm-notes",
                "source_revision_id": "srcrev:assertion-gm-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
        ],
    }


def _sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:assertion-player-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:assertion-scope-demo",
            campaign_id="camp:assertion-scope",
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:assertion-gm-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:assertion-scope-demo",
            campaign_id="camp:assertion-scope",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:assertion-player-notes-v1",
            source_artifact_id="src:assertion-player-notes",
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://assertion-scope/player-notes",
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:assertion-gm-notes-v1",
            source_artifact_id="src:assertion-gm-notes",
            content_sha256="bb" * 32,
            body_storage="external",
            locator="fixture://assertion-scope/gm-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def test_valid_v2_parsing() -> None:
    parsed = V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload())
    obj = parsed.objects["obj:item-sun-ledger"]
    assert obj.label == "The Sun Ledger"
    assert PLAYER_ALIAS in obj.aliases
    assert GM_ALIAS in obj.aliases
    assert obj.summary == GM_SUMMARY
    assert obj.object_field_schema == "v2"
    assert "ev:ledger-core-player" in obj.core_evidence_ref_ids


def test_versioned_reader_dispatches_and_rejects_unknown() -> None:
    parsed = VERSIONED.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload())
    assert parsed.graph_schema == GRAPH_SCHEMA_V2
    with pytest.raises(PersistenceIntegrityError):
        VERSIONED.parse(graph_schema="dm_union_graph_v9", graph_payload=_v2_payload())


def test_mixed_v1_v2_node_shape_rejected() -> None:
    payload = _v2_payload()
    payload["nodes"][0]["aliases"] = ["legacy"]
    with pytest.raises(PersistenceIntegrityError):
        V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)

    v1_mixed = {
        "world_id": "world:assertion-scope-demo",
        "nodes": [
            {
                "object_id": "obj:x",
                "kind": "artifact",
                "label": "X",
                "evidence_ref_ids": ["ev:x"],
                "alias_assertions": [],
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:x",
                "source_artifact_id": "src:assertion-player-notes",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            }
        ],
    }
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV1SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V1, graph_payload=v1_mixed
        )


def test_missing_core_evidence_rejected() -> None:
    payload = _v2_payload()
    payload["nodes"][0]["evidence_ref_ids"] = []
    with pytest.raises(PersistenceIntegrityError):
        V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)


def test_dangling_assertion_evidence_rejected() -> None:
    payload = _v2_payload()
    payload["nodes"][0]["alias_assertions"][0]["evidence_ref_ids"] = ["ev:missing"]
    with pytest.raises(PersistenceIntegrityError):
        V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)


def test_duplicate_assertion_id_rejected() -> None:
    payload = _v2_payload()
    payload["nodes"][0]["summary_assertion"]["assertion_id"] = "asrt:ledger-alias-dawn"
    with pytest.raises(PersistenceIntegrityError):
        V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)


def test_duplicate_normalized_alias_on_object_rejected() -> None:
    payload = _v2_payload()
    payload["nodes"][0]["alias_assertions"].append(
        {
            "assertion_id": "asrt:dup",
            "alias": "dawn ledger",
            "evidence_ref_ids": ["ev:ledger-alias-player"],
        }
    )
    with pytest.raises(PersistenceIntegrityError):
        V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)


def test_player_vs_gm_alias_and_summary_admission() -> None:
    parsed = V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload())
    sources = _sources()
    player = project_scoped_snapshot(
        parsed,
        sources=sources,
        world_id="world:assertion-scope-demo",
        campaign_id="camp:assertion-scope",
        admissibility=Admissibility.PLAYER,
    )
    gm = project_scoped_snapshot(
        parsed,
        sources=sources,
        world_id="world:assertion-scope-demo",
        campaign_id="camp:assertion-scope",
        admissibility=Admissibility.GM,
    )
    player_obj = player.snapshot.objects["obj:item-sun-ledger"]
    gm_obj = gm.snapshot.objects["obj:item-sun-ledger"]
    assert player_obj.aliases == [PLAYER_ALIAS]
    assert player_obj.summary is None
    assert GM_ALIAS not in player_obj.aliases
    assert gm_obj.aliases == [PLAYER_ALIAS, GM_ALIAS]
    assert gm_obj.summary == GM_SUMMARY
    assert "ev:ledger-alias-gm" not in player.snapshot.evidence
    assert "ev:ledger-summary-gm" not in player.snapshot.evidence
    assert "asrt:ledger-alias-debtbook" in player.assertion_exclusions
    assert "asrt:ledger-summary-secret" in player.assertion_exclusions


def test_hidden_alias_cannot_resolve() -> None:
    parsed = V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload())
    scoped = project_scoped_snapshot(
        parsed,
        sources=_sources(),
        world_id="world:assertion-scope-demo",
        campaign_id="camp:assertion-scope",
        admissibility=Admissibility.PLAYER,
    )
    referents = VERSIONED.resolve_mentions(
        scoped.snapshot,
        message=f"Tell me about the {GM_ALIAS}",
        selected_object_ids=[],
    )
    assert all(ref.object_id != "obj:item-sun-ledger" for ref in referents)
    dawn = VERSIONED.resolve_mentions(
        scoped.snapshot,
        message=f"Tell me about the {PLAYER_ALIAS}",
        selected_object_ids=[],
    )
    assert any(ref.object_id == "obj:item-sun-ledger" for ref in dawn)


def test_hidden_text_absent_from_scoped_snapshot_and_dumps() -> None:
    parsed = V2.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload())
    scoped = project_scoped_snapshot(
        parsed,
        sources=_sources(),
        world_id="world:assertion-scope-demo",
        campaign_id="camp:assertion-scope",
        admissibility=Admissibility.PLAYER,
    )
    rendered = str(scoped.snapshot)
    assert GM_ALIAS not in rendered
    assert GM_SUMMARY not in rendered
    obj = scoped.snapshot.objects["obj:item-sun-ledger"]
    dump = obj.model_dump(mode="json")
    assert "admitted_alias_assertions" not in dump
    assert "admitted_summary_assertion" not in dump
    assert "object_field_schema" not in dump
    assert dump["aliases"] == [PLAYER_ALIAS]
    assert "summary" not in dump or dump.get("summary") in (None, "")


def test_v1_coarse_behavior_remains_exact() -> None:
    payload = {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": ["Sun Ledger", GM_ALIAS],
                "evidence_ref_ids": ["ev:player", "ev:gm"],
                "summary": GM_SUMMARY,
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:player",
                "source_artifact_id": "src:assertion-player-notes",
                "source_revision_id": "srcrev:assertion-player-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
            {
                "evidence_ref_id": "ev:gm",
                "source_artifact_id": "src:assertion-gm-notes",
                "source_revision_id": "srcrev:assertion-gm-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            },
        ],
    }
    # Reuse assertion-scope sources but retarget world ids for this unit case.
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:assertion-player-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:assertion-gm-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:demo-atlas",
            visibility=Visibility.GM,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:assertion-player-notes-v1",
            source_artifact_id="src:assertion-player-notes",
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://assertion-scope/player-notes",
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:assertion-gm-notes-v1",
            source_artifact_id="src:assertion-gm-notes",
            content_sha256="bb" * 32,
            body_storage="external",
            locator="fixture://assertion-scope/gm-notes",
            created_at=FIXED_NOW,
        )
    )
    parsed = UnionGraphV1SnapshotReader().parse(
        graph_schema=GRAPH_SCHEMA_V1, graph_payload=payload
    )
    player = project_scoped_snapshot(
        parsed,
        sources=sources,
        world_id="world:demo-atlas",
        campaign_id=None,
        admissibility=Admissibility.PLAYER,
    )
    assert "obj:item-sun-ledger" not in player.snapshot.objects


def test_v1_model_dump_unchanged_shape() -> None:
    fixture = load_curated_mind_turn_fixture()
    parsed = VERSIONED.parse(
        graph_schema=fixture.graph_schema,
        graph_payload=fixture.graph_payload,
    )
    obj = parsed.objects["obj:item-sun-ledger"]
    dump = obj.model_dump(mode="json")
    assert set(dump.keys()) == {
        "object_id",
        "kind",
        "label",
        "aliases",
        "evidence_ref_ids",
        "summary",
    }


def test_fixture_loader_accepts_assertion_scope_version() -> None:
    fixture = load_curated_mind_turn_fixture(
        FIXTURE_PATH,
        expected_fixture_version="curated_assertion_scope_v1",
    )
    assert fixture.graph_schema == GRAPH_SCHEMA_V2
    assert fixture.world_id == "world:assertion-scope-demo"


def test_mind_turn_player_leak_audit_and_gm_fields() -> None:
    fixture = load_curated_mind_turn_fixture(
        FIXTURE_PATH,
        expected_fixture_version="curated_assertion_scope_v1",
    )
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()
    retrieval_sessions = InMemoryRetrievalSessionRepository()
    semantic_search = InMemorySemanticSearch(semantic_documents, embedding_runs)
    seed_curated_mind_turn(
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

    def _req(request_id: str, *, admissibility: Admissibility) -> MindTurnRequest:
        # Thread binding is world/campaign/caller/tenant only; admissibility may vary.
        return MindTurnRequest.for_authorized(
            request_id=request_id,
            thread_id=binding.thread_id,
            caller_scope=CallerScope(
                caller_id=binding.caller_id,
                tenant_id=binding.tenant_id,
                roles=list(binding.roles),
            ),
            world_id=binding.world_id,
            campaign_id=binding.campaign_id,
            admissibility=admissibility,
            focus=ProjectionFocus(),
            surface_context=SurfaceContext(surface_id=binding.surface_id),
            message="What is the Sun Ledger?",
        )

    player = service.execute(_req("req:assert-player", admissibility=Admissibility.PLAYER))
    gm = service.execute(_req("req:assert-gm", admissibility=Admissibility.GM))
    assert player.revision_id == gm.revision_id
    assert player.revision_id.startswith("rev:")

    player_text = player.model_dump_json()
    sentinels = fixture.raw["leak_sentinels"]
    for value in [
        sentinels["gm_alias"],
        sentinels["gm_summary"],
        *sentinels["gm_assertion_ids"],
        *sentinels["gm_evidence_ids"],
        *sentinels["gm_source_artifact_ids"],
        *sentinels["gm_source_revision_ids"],
        *sentinels["gm_locators"],
    ]:
        assert value not in player_text

    player_briefs = [
        p for p in player.semantic_projections if p.kind == "entity_brief"
    ]
    assert player_briefs
    assert PLAYER_ALIAS in player_briefs[0].payload["aliases"]
    assert GM_ALIAS not in player_briefs[0].payload.get("aliases", [])
    assert "summary" not in player_briefs[0].payload

    player_prov = [
        p for p in player.semantic_projections if p.kind == "entity_field_provenance"
    ]
    assert len(player_prov) == 1
    assert player_prov[0].payload["alias_assertions"] == [
        {
            "assertion_id": "asrt:ledger-alias-dawn",
            "alias": PLAYER_ALIAS,
            "evidence_ref_ids": ["ev:ledger-alias-player"],
        }
    ]
    assert "summary_assertion" not in player_prov[0].payload

    gm_briefs = [p for p in gm.semantic_projections if p.kind == "entity_brief"]
    assert GM_ALIAS in gm_briefs[0].payload["aliases"]
    assert gm_briefs[0].payload["summary"] == GM_SUMMARY
    gm_prov = [
        p for p in gm.semantic_projections if p.kind == "entity_field_provenance"
    ]
    assert len(gm_prov) == 1
    assert "summary_assertion" in gm_prov[0].payload
    assert GM_SUMMARY in gm.answer

    obj = VERSIONED.parse(
        graph_schema=fixture.graph_schema,
        graph_payload=fixture.graph_payload,
    ).objects["obj:item-sun-ledger"]
    assert "admitted_alias_assertions" not in obj.model_dump(mode="json")
