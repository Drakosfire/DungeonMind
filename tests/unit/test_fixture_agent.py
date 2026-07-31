"""Unit tests for the deterministic fixture-grounded agent adapter."""


from dungeonmind.agents.fixture import FixtureGroundedAgentAdapter
from dungeonmind.agents.protocol import AdmittedSurfaceContext, AgentTurnContext, AgentTurnInput
from dungeonmind.contracts.capability import CapabilityPolicy, GraphScope
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.retrieval import ClaimAuthority
from dungeonmind.domain.canonical import canonical_json

REVISION = "rev:" + "ab" * 16


def _context(
    assembled: str,
    *,
    message: str = "Who safeguards the Sun Ledger?",
) -> AgentTurnContext:
    agent_input = AgentTurnInput(
        message=message,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        focus=ProjectionFocus(),
        admissibility=Admissibility.GM,
        surface=AdmittedSurfaceContext(surface_id="landingpage:mind-turn-demo"),
        assembled_context=assembled,
        revision_id=REVISION,
    )
    policy = CapabilityPolicy(
        policy_id="pol:fixture-test",
        graph_scope=GraphScope(
            world_id="world:demo-atlas",
            campaign_id="camp:demo",
            focus=ProjectionFocus(),
            admissibility=Admissibility.GM,
            revision_pin=REVISION,
        ),
        enabled_tools=[],
        tool_rules=[],
    )
    return AgentTurnContext(input=agent_input, capability_policy=policy)


def _ledger_context(*, evidence_role: str = "support") -> str:
    document = {
        "revision_id": REVISION,
        "world_id": "world:demo-atlas",
        "campaign_id": "camp:demo",
        "admissibility": "gm",
        "focus": {"kind": "none", "session_id": None},
        "objects": [
            {
                "object_id": "obj:npc-mere-astor",
                "kind": "npc",
                "label": "Mere Astor",
                "aliases": ["Astor"],
                "evidence_ref_ids": ["ev:astor"],
            },
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": [],
                "evidence_ref_ids": ["ev:ledger"],
                "summary": "a brass-bound account of every dawn debt owed in Vael",
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel:astor-safeguards-ledger",
                "subject_object_id": "obj:npc-mere-astor",
                "predicate": "safeguards",
                "object_object_id": "obj:item-sun-ledger",
                "evidence_ref_ids": ["ev:astor-ledger"],
            }
        ],
        "evidence": [
            {
                "evidence_ref_id": "ev:astor-ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_domain": "worldbuilding",
                "evidence_role": evidence_role,
                "can_open_source": True,
            }
        ],
        "source_anchors": [],
        "coverage": {"known": [], "missing": [], "gap_codes": []},
    }
    return canonical_json(document)


def test_same_context_yields_identical_result() -> None:
    adapter = FixtureGroundedAgentAdapter()
    context = _context(_ledger_context())
    first = adapter.execute_turn(context)
    second = adapter.execute_turn(context)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert "Mere Astor" in first.answer
    assert "safeguards" in first.answer.casefold()


def test_unknown_or_empty_context_abstains() -> None:
    adapter = FixtureGroundedAgentAdapter()

    empty = _context(
        canonical_json(
            {
                "objects": [],
                "relationships": [],
                "evidence": [],
                "coverage": {"missing": ["Moon King"], "gap_codes": ["unresolved_referent"]},
            }
        ),
        message="Who is the Moon King?",
    )
    empty_result = adapter.execute_turn(empty)
    assert empty_result.claims == []
    assert "do not have grounded knowledge" in empty_result.answer.casefold()
    assert any(d.code == "fixture_agent_abstain" for d in empty_result.diagnostics)

    invalid = _context("not-json{", message="Who safeguards the Sun Ledger?")
    invalid_result = adapter.execute_turn(invalid)
    assert invalid_result.claims == []
    assert any(d.code == "fixture_agent_invalid_context" for d in invalid_result.diagnostics)


def test_accepted_graph_fact_only_with_support_evidence() -> None:
    adapter = FixtureGroundedAgentAdapter()

    with_support = adapter.execute_turn(_context(_ledger_context(evidence_role="support")))
    assert with_support.claims
    claim = with_support.claims[0]
    assert claim.authority is ClaimAuthority.GRAPH_FACT
    assert claim.evidence_ref_ids == ["ev:astor-ledger"]

    without_support = adapter.execute_turn(
        _context(_ledger_context(evidence_role="context"))
    )
    assert without_support.claims
    inference = without_support.claims[0]
    assert inference.authority is ClaimAuthority.INFERENCE
    assert inference.evidence_ref_ids == []


def test_adapter_executes_without_repository_args() -> None:
    # Smoke: constructor takes no repos; execute_turn needs only AgentTurnContext.
    adapter = FixtureGroundedAgentAdapter()
    result = adapter.execute_turn(_context(_ledger_context()))
    assert result.answer
    assert adapter.adapter_id == "fixture-grounded-agent-v1"


def test_ledger_answer_follows_context_summary_not_compiled_in_prose() -> None:
    adapter = FixtureGroundedAgentAdapter()
    altered = {
        "revision_id": REVISION,
        "objects": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": [],
                "evidence_ref_ids": ["ev:ledger"],
                "summary": "a silver daybook of harbor tithes",
            }
        ],
        "relationships": [],
        "evidence": [
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
            }
        ],
        "coverage": {"known": [], "missing": [], "gap_codes": []},
    }
    result = adapter.execute_turn(
        _context(canonical_json(altered), message="What is the Sun Ledger?")
    )
    assert "silver daybook" in result.answer
    assert "brass-bound" not in result.answer.casefold()
    assert result.claims[0].authority is ClaimAuthority.GRAPH_FACT

    no_summary = {
        "revision_id": REVISION,
        "objects": [
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": [],
                "evidence_ref_ids": ["ev:ledger"],
            }
        ],
        "relationships": [],
        "evidence": [
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            }
        ],
        "coverage": {"known": [], "missing": [], "gap_codes": []},
    }
    kind_only = adapter.execute_turn(
        _context(canonical_json(no_summary), message="What is the Sun Ledger?")
    )
    assert kind_only.answer == "The Sun Ledger is an artifact."
