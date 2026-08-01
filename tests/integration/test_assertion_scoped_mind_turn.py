"""PostgreSQL-backed player/GM assertion-scoped Mind Turn proof."""

from __future__ import annotations

from pathlib import Path

import pytest

from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.agents.protocol import AgentTurnContext, AgentTurnResult
from dungeonmind.application.mind_turn import FixedClock, MindTurnService
from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.domain.errors import IdempotencyConflictError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.service.demo_access import DemoAccessBinding

pytestmark = pytest.mark.integration

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "curated_assertion_scope_v1.json"
)
PLAYER_ALIAS = "Dawn Ledger"
GM_ALIAS = "Debtbook of the First Light"
GM_SUMMARY = "a brass-bound account that records the names owed to the buried sun"


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


@pytest.fixture
def assertion_service(pg):
    fixture = load_curated_mind_turn_fixture(
        FIXTURE_PATH,
        expected_fixture_version="curated_assertion_scope_v1",
    )
    seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    # Idempotent reseed must reuse the same head.
    again = seed_curated_mind_turn(
        world_graph=pg.world_graph,
        sources=pg.sources,
        embedding_runs=pg.embedding_runs,
        semantic_documents=pg.semantic_documents,
        threads=pg.threads,
        fixture=fixture,
    )
    assert again.status == "reused"
    capturing = CapturingFixtureAgentAdapter()
    service = MindTurnService(
        world_graph=pg.world_graph,
        retrieval_sessions=pg.retrieval_sessions,
        threads=pg.threads,
        semantic_documents=pg.semantic_documents,
        semantic_search=pg.semantic_search,
        sources=pg.sources,
        query_embedder=fixture.query_embedder,
        agent_adapter=capturing,
        clock=FixedClock(fixture.created_at()),
    )
    return service, fixture, capturing


def _authorized_request(
    fixture,
    *,
    request_id: str,
    admissibility: Admissibility,
    message: str = "What is the Sun Ledger?",
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
        admissibility=admissibility,
        focus=ProjectionFocus(),
        surface_context=SurfaceContext(surface_id=binding.surface_id),
        message=message,
    )


def _assert_no_gm_sentinels(serialized: str, fixture) -> None:
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
        assert value not in serialized


def test_player_and_gm_turns_same_revision(assertion_service) -> None:
    service, fixture, capturing = assertion_service
    player = service.execute(
        _authorized_request(
            fixture,
            request_id="req:assert-int-player",
            admissibility=Admissibility.PLAYER,
        )
    )
    gm = service.execute(
        _authorized_request(
            fixture,
            request_id="req:assert-int-gm",
            admissibility=Admissibility.GM,
        )
    )

    assert player.revision_id == gm.revision_id
    assert player.revision_id.startswith("rev:")
    assert fixture.graph_schema == "dm_union_graph_v2"

    player_json = player.model_dump_json()
    _assert_no_gm_sentinels(player_json, fixture)
    assert len(capturing.assembled_contexts) >= 2
    _assert_no_gm_sentinels(capturing.assembled_contexts[0], fixture)
    assert PLAYER_ALIAS in player_json
    assert GM_SUMMARY not in player.answer

    player_briefs = [p for p in player.semantic_projections if p.kind == "entity_brief"]
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
    player_evidence_ids = {e.evidence_ref_id for e in player.evidence}
    for assertion in player_prov[0].payload["alias_assertions"]:
        for evidence_ref_id in assertion["evidence_ref_ids"]:
            assert evidence_ref_id in player_evidence_ids

    gm_briefs = [p for p in gm.semantic_projections if p.kind == "entity_brief"]
    assert PLAYER_ALIAS in gm_briefs[0].payload["aliases"]
    assert GM_ALIAS in gm_briefs[0].payload["aliases"]
    assert gm_briefs[0].payload["summary"] == GM_SUMMARY
    gm_prov = [p for p in gm.semantic_projections if p.kind == "entity_field_provenance"]
    assert len(gm_prov) == 1
    assert "summary_assertion" in gm_prov[0].payload
    assert GM_SUMMARY in gm.answer
    gm_evidence_ids = {e.evidence_ref_id for e in gm.evidence}
    assert "ev:ledger-alias-gm" in gm_evidence_ids
    assert "ev:ledger-summary-gm" in gm_evidence_ids
    assert any(
        a.source_artifact_id == "src:assertion-gm-notes" for a in gm.source_anchors
    )
    for assertion in gm_prov[0].payload.get("alias_assertions", []):
        for evidence_ref_id in assertion["evidence_ref_ids"]:
            assert evidence_ref_id in gm_evidence_ids
    for evidence_ref_id in gm_prov[0].payload["summary_assertion"]["evidence_ref_ids"]:
        assert evidence_ref_id in gm_evidence_ids


def test_hidden_alias_semantic_path_does_not_recover_object(assertion_service) -> None:
    service, fixture, capturing = assertion_service
    player = service.execute(
        _authorized_request(
            fixture,
            request_id="req:assert-int-player-hidden-alias",
            admissibility=Admissibility.PLAYER,
            message=f"What is the {GM_ALIAS}?",
        )
    )

    assert all(ref.object_id != "obj:item-sun-ledger" for ref in player.resolved_referents)
    assert not any(
        p.payload.get("object_id") == "obj:item-sun-ledger"
        for p in player.semantic_projections
    )
    assert "obj:item-sun-ledger" not in player.model_dump_json()
    assert not any(e.evidence_ref_id.startswith("ev:ledger-") for e in player.evidence)
    assert all(
        "obj:item-sun-ledger" not in str(change.payload)
        and "Sun Ledger" not in str(change.payload)
        for change in player.context_changes
    )
    assert "Sun Ledger" not in player.answer
    assert "do not have grounded knowledge" in player.answer.casefold()

    assert capturing.assembled_contexts
    agent_context = capturing.assembled_contexts[-1]
    assert "obj:item-sun-ledger" not in agent_context
    assert "Sun Ledger" not in agent_context
    for value in [
        fixture.raw["leak_sentinels"]["gm_summary"],
        *fixture.raw["leak_sentinels"]["gm_assertion_ids"],
        *fixture.raw["leak_sentinels"]["gm_evidence_ids"],
        *fixture.raw["leak_sentinels"]["gm_source_artifact_ids"],
        *fixture.raw["leak_sentinels"]["gm_source_revision_ids"],
        *fixture.raw["leak_sentinels"]["gm_locators"],
    ]:
        assert value not in player.model_dump_json()
        assert value not in agent_context


def test_exact_replay_skips_agent_and_conflict_on_changed_admissibility(
    assertion_service,
) -> None:
    service, fixture, _capturing = assertion_service
    req = _authorized_request(
        fixture,
        request_id="req:assert-int-replay-player",
        admissibility=Admissibility.PLAYER,
    )
    first = service.execute(req)
    count_after_first = service.agent_invocation_count
    second = service.execute(req)
    assert second.model_dump() == first.model_dump()
    assert service.agent_invocation_count == count_after_first

    gm_req = _authorized_request(
        fixture,
        request_id="req:assert-int-replay-gm",
        admissibility=Admissibility.GM,
    )
    gm_first = service.execute(gm_req)
    count_after_gm = service.agent_invocation_count
    gm_second = service.execute(gm_req)
    assert gm_second.model_dump() == gm_first.model_dump()
    assert service.agent_invocation_count == count_after_gm

    conflict = _authorized_request(
        fixture,
        request_id="req:assert-int-replay-player",
        admissibility=Admissibility.GM,
    )
    with pytest.raises(IdempotencyConflictError):
        service.execute(conflict)
