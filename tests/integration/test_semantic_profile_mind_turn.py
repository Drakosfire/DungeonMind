"""PostgreSQL-backed narrative semantic-profile Mind Turn canary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.agents.protocol import AgentTurnContext, AgentTurnResult
from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.errors import (
    SemanticProfileIntegrityError,
    SemanticProfileNotFoundError,
)
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.infrastructure.semantic_profiles import (
    FilesystemSemanticProfileRegistry,
    StaticSemanticProfileRegistry,
)
from dungeonmind.service.demo_access import DemoAccessBinding

pytestmark = pytest.mark.integration

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "curated_semantic_profile_v1.json"
)
NARRATIVE_DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-narrative-v1.json"
)


class CapturingFixtureAgentAdapter:
    """Records assembled agent context while delegating to the fixture agent."""

    def __init__(self) -> None:
        self._inner = FixtureGroundedAgentAdapter()
        self.assembled_contexts: list[str] = []

    @property
    def adapter_id(self) -> str:
        return self._inner.adapter_id

    def execute_turn(self, context: AgentTurnContext) -> AgentTurnResult:
        self.assembled_contexts.append(context.input.assembled_context)
        return self._inner.execute_turn(context)


def _narrative_registry() -> StaticSemanticProfileRegistry:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(NARRATIVE_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    return StaticSemanticProfileRegistry([descriptor])


@pytest.fixture
def semantic_profile_service(pg):
    registry = _narrative_registry()
    graph_reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    fixture = load_curated_mind_turn_fixture(
        FIXTURE_PATH,
        expected_fixture_version="curated_semantic_profile_v1",
        graph_reader=graph_reader,
    )
    seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    capturing = CapturingFixtureAgentAdapter()
    service = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=graph_reader,
        query_embedder=fixture.query_embedder,
        agent_adapter=capturing,
        clock=FixedClock(fixture.created_at()),
    )
    return service, fixture, capturing, registry, graph_reader, pg


def _authorized_request(
    fixture,
    *,
    request_id: str,
    message: str = "What is the Buried Sun Clock?",
) -> MindTurnRequest:
    binding = DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)
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
        admissibility=Admissibility.PLAYER,
        focus=ProjectionFocus(),
        surface_context=SurfaceContext(surface_id=binding.surface_id),
        message=message,
    )


def _assert_no_path_leaks(serialized: str, fixture) -> None:
    for fragment in fixture.raw["leak_sentinels"]["path_fragments"]:
        assert fragment not in serialized
    for term in fixture.raw["leak_sentinels"]["forbidden_terms"]:
        assert term not in serialized.casefold()


def test_publish_mind_turn_replay_and_fresh_reconstruction(
    semantic_profile_service,
) -> None:
    service, fixture, capturing, _registry, graph_reader, pg = semantic_profile_service
    assert fixture.graph_schema == "dm_union_graph_v3"

    first = service.execute(
        _authorized_request(fixture, request_id="req:semantic-profile-1")
    )
    assert first.revision_id.startswith("rev:")
    assert "Buried Sun Clock" in first.answer or "Dawn Clock" in first.model_dump_json()
    _assert_no_path_leaks(first.model_dump_json(), fixture)
    assert capturing.assembled_contexts
    _assert_no_path_leaks(capturing.assembled_contexts[-1], fixture)

    count_after_first = service.agent_invocation_count
    replay = service.execute(
        _authorized_request(fixture, request_id="req:semantic-profile-1")
    )
    assert replay.model_dump() == first.model_dump()
    assert service.agent_invocation_count == count_after_first

    fresh_capturing = CapturingFixtureAgentAdapter()
    fresh = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=graph_reader,
        query_embedder=fixture.query_embedder,
        agent_adapter=fresh_capturing,
        clock=FixedClock(fixture.created_at()),
    )
    reconstructed = fresh.execute(
        _authorized_request(fixture, request_id="req:semantic-profile-fresh")
    )
    assert reconstructed.revision_id == first.revision_id
    assert "obj:clock-buried-sun" in reconstructed.model_dump_json()
    _assert_no_path_leaks(reconstructed.model_dump_json(), fixture)


def test_missing_profile_blocks_turn(semantic_profile_service) -> None:
    _service, fixture, _capturing, _registry, _reader, pg = semantic_profile_service
    empty_reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry()
    )
    blocked = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=empty_reader,
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(fixture.created_at()),
    )
    with pytest.raises(SemanticProfileNotFoundError) as exc_info:
        blocked.execute(
            _authorized_request(fixture, request_id="req:semantic-profile-missing")
        )
    assert str(NARRATIVE_DESCRIPTOR_PATH) not in str(exc_info.value)
    assert "semantic_profiles" not in str(exc_info.value)


def test_tampered_profile_blocks_without_path_leak(
    semantic_profile_service, tmp_path: Path
) -> None:
    _service, fixture, _capturing, _registry, _reader, pg = semantic_profile_service
    descriptor = json.loads(NARRATIVE_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    # Tamper bytes while keeping identity fields.
    descriptor["term_namespaces"] = ["narrative", "extra"]
    desc_path = tmp_path / "tampered.json"
    desc_path.write_text(json.dumps(descriptor), encoding="utf-8")
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "tampered.json",
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    tampered_registry = FilesystemSemanticProfileRegistry.from_config_path(config_path)
    # Digest of tampered descriptor differs from pinned ref.
    tampered = tampered_registry.get("test.narrative", "narrative-profile-v1")
    assert tampered is not None
    original = SemanticProfileDescriptor.model_validate(
        json.loads(NARRATIVE_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    assert descriptor_sha256(tampered) != descriptor_sha256(original)

    blocked_reader = VersionedUnionGraphSnapshotReader(
        profile_registry=tampered_registry
    )
    blocked = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=blocked_reader,
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(fixture.created_at()),
    )
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        blocked.execute(
            _authorized_request(fixture, request_id="req:semantic-profile-tamper")
        )
    blob = str(exc_info.value) + json.dumps(exc_info.value.details)
    assert str(tmp_path) not in blob
    assert "tampered.json" not in blob
    assert "semantic_profiles" not in blob
