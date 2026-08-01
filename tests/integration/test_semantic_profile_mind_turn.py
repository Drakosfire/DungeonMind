"""PostgreSQL-backed narrative semantic-profile Mind Turn canary."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import pytest

# Core CI installs neither the ``api`` nor ``postgres`` extras. Skip collection
# when FastAPI is absent so ``pytest -m "not integration"`` stays clean.
pytest.importorskip("fastapi")

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
    ENV_SEMANTIC_PROFILE_REGISTRY_PATH,
    FilesystemSemanticProfileRegistry,
    StaticSemanticProfileRegistry,
)
from dungeonmind.service.bootstrap import load_configured_profile_registry
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


class _SuppressFirstAppendThreadRepository:
    """Thread-repo wrapper that drops the first ``append_turn`` call.

    The PostgreSQL retrieval session still persists, but no thread replay
    short-circuits ``_find_replay`` — so a fresh service must recover through
    the persisted-session reconstruction path.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self.suppressed_appends = 0

    def create_thread(self, thread_id, **kwargs):
        return self._inner.create_thread(thread_id, **kwargs)

    def append_turn(self, request, response) -> None:
        if self.suppressed_appends == 0:
            self.suppressed_appends += 1
            return
        self._inner.append_turn(request, response)

    def list_turns(self, thread_id):
        return self._inner.list_turns(thread_id)


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


def test_publish_mind_turn_and_thread_replay(semantic_profile_service) -> None:
    service, fixture, capturing, _registry, _graph_reader, _pg = semantic_profile_service
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


def test_fresh_service_reconstructs_persisted_retrieval_session(
    semantic_profile_service,
) -> None:
    _service, fixture, capturing, _registry, graph_reader, pg = semantic_profile_service
    request = _authorized_request(
        fixture, request_id="req:semantic-profile-reconstruct"
    )

    # Publish: the retrieval session persists, but the thread append is
    # suppressed so no thread replay can short-circuit recovery.
    first_service = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=_SuppressFirstAppendThreadRepository(pg.threads),
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        graph_reader=graph_reader,
        query_embedder=fixture.query_embedder,
        agent_adapter=capturing,
        clock=FixedClock(fixture.created_at()),
    )
    first = first_service.execute(request)
    assert first_service.agent_invocation_count == 1
    assert pg.threads.list_turns(request.thread_id) == []

    def _fresh_service(reader, adapter) -> MindTurnService:
        return MindTurnService(
            world_graph=pg.world_graph,
            retrieval_sessions=pg.retrieval_sessions,
            threads=_SuppressFirstAppendThreadRepository(pg.threads),
            semantic_documents=pg.semantic_documents,
            semantic_search=pg.semantic_search,
            sources=pg.sources,
            graph_reader=reader,
            query_embedder=fixture.query_embedder,
            agent_adapter=adapter,
            clock=FixedClock(fixture.created_at()),
        )

    # Fresh process equivalent: same request ID, profile-aware reader.
    fresh_capturing = CapturingFixtureAgentAdapter()
    fresh = _fresh_service(graph_reader, fresh_capturing)
    reconstructed = fresh.execute(request)
    assert reconstructed.model_dump() == first.model_dump()
    assert "obj:clock-buried-sun" in reconstructed.model_dump_json()
    _assert_no_path_leaks(reconstructed.model_dump_json(), fixture)
    assert fresh.agent_invocation_count == 0
    assert fresh_capturing.assembled_contexts == []
    # The successful recovery append is suppressed too, so the failure-mode
    # recoveries below still exercise the persisted-session path.
    assert pg.threads.list_turns(request.thread_id) == []

    # Missing profile blocks reconstruction after persistence.
    missing = _fresh_service(
        VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry()
        ),
        CapturingFixtureAgentAdapter(),
    )
    with pytest.raises(SemanticProfileNotFoundError):
        missing.execute(request)

    # Tampered descriptor (digest drift) blocks reconstruction after persistence.
    tampered_descriptor = SemanticProfileDescriptor.model_validate(
        {
            "schema_version": "dm_semantic_profile_v1",
            "profile_id": "test.narrative",
            "profile_revision": "narrative-profile-v1",
            "term_namespaces": ["narrative", "extra"],
        }
    )
    tampered = _fresh_service(
        VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([tampered_descriptor])
        ),
        CapturingFixtureAgentAdapter(),
    )
    with pytest.raises(SemanticProfileIntegrityError):
        tampered.execute(request)


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


def _assert_startup_traceback_clean(exc: BaseException, *needles: str) -> None:
    """The full chained traceback a startup logger emits must hide local paths."""
    blob = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    for needle in needles:
        assert needle not in blob
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def test_bootstrap_missing_registry_config_suppresses_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        ENV_SEMANTIC_PROFILE_REGISTRY_PATH, str(tmp_path / "registry.json")
    )
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        load_configured_profile_registry()
    _assert_startup_traceback_clean(exc_info.value, str(tmp_path), "registry.json")


def test_bootstrap_raw_oserror_suppresses_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raising_from_config_path(_path):
        raise OSError(f"simulated failure reading {tmp_path}/registry.json")

    monkeypatch.setattr(
        FilesystemSemanticProfileRegistry,
        "from_config_path",
        _raising_from_config_path,
    )
    monkeypatch.setenv(
        ENV_SEMANTIC_PROFILE_REGISTRY_PATH, str(tmp_path / "registry.json")
    )
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        load_configured_profile_registry()
    _assert_startup_traceback_clean(exc_info.value, str(tmp_path), "registry.json")
