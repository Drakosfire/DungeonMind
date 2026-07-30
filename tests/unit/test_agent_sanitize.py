"""Agent adapters receive sanitized input; CapabilityPolicy is sole tool authority."""

from dungeonmind.agents import AgentTurnContext, sanitize_agent_input
from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    FocusKind,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.domain import permitted_tool_names


def test_sanitize_agent_input_omits_auth_fields() -> None:
    agent_input = sanitize_agent_input(
        message="Where does Mere Astor live?",
        world_id="world:demo",
        campaign_id="camp:1",
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.PLAYER,
        surface_id="surface:plan",
        surface_mode="ask",
        selected_object_ids=["obj:1"],
        assembled_context="Mere Astor resides in Vael.",
        revision_id="rev:" + "ab" * 16,
    )
    dumped = agent_input.model_dump()
    assert "caller_id" not in dumped
    assert "tenant_id" not in dumped
    assert "roles" not in dumped
    assert "selected_document_ref" not in dumped
    assert "active_artifact_refs" not in dumped
    assert "permitted_tool_names" not in dumped
    assert agent_input.message.startswith("Where")
    assert agent_input.admissibility is Admissibility.PLAYER
    assert agent_input.surface.selected_object_ids == ["obj:1"]


def test_caller_cannot_inject_tools_through_sanitization() -> None:
    agent_input = sanitize_agent_input(
        message="hi",
        world_id="world:demo",
        campaign_id=None,
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.GM,
        surface_id="surface:plan",
        surface_mode=None,
        selected_object_ids=[],
        assembled_context="",
        revision_id="rev:" + "ab" * 16,
    )
    policy = CapabilityPolicy(
        policy_id="pol:1",
        graph_scope=GraphScope(world_id="world:demo", admissibility=Admissibility.PLAYER),
        enabled_tools=["graph.search"],
        tool_rules=[
            ToolCapabilityRule(
                tool_name="graph.search",
                category=CapabilityCategory.READ_ONLY,
                allowed_effects=[CapabilityEffect.READ],
            )
        ],
    )
    context = AgentTurnContext(input=agent_input, capability_policy=policy)
    assert permitted_tool_names(context.capability_policy) == ["graph.search"]
    assert "permitted_tool_names" not in type(context.input).model_fields
    assert context.capability_policy.graph_scope is not None
    assert context.capability_policy.graph_scope.admissibility is Admissibility.PLAYER
