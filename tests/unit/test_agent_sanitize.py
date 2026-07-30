"""Agent adapters receive sanitized input; CapabilityPolicy is sole tool authority."""

import pytest
from pydantic import ValidationError

from dungeonmind.agents import AgentTurnContext, AgentTurnInput, sanitize_agent_input
from dungeonmind.agents.protocol import AdmittedSurfaceContext
from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    FocusKind,
    GraphScope,
    ProjectionFocus,
    ToolCapabilityRule,
)
from dungeonmind.domain import permitted_tool_names

REVISION = "rev:" + "ab" * 16


def _player_policy(**scope_overrides: object) -> CapabilityPolicy:
    scope_kwargs: dict[str, object] = {
        "world_id": "world:demo",
        "campaign_id": "camp:1",
        "focus": ProjectionFocus(),
        "admissibility": Admissibility.PLAYER,
        "revision_pin": REVISION,
    }
    scope_kwargs.update(scope_overrides)
    return CapabilityPolicy(
        policy_id="pol:1",
        graph_scope=GraphScope(**scope_kwargs),  # type: ignore[arg-type]
        enabled_tools=["graph.search"],
        tool_rules=[
            ToolCapabilityRule(
                tool_name="graph.search",
                category=CapabilityCategory.READ_ONLY,
                allowed_effects=[CapabilityEffect.READ],
            )
        ],
    )


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
        revision_id=REVISION,
    )
    dumped = agent_input.model_dump()
    assert "caller_id" not in dumped
    assert "tenant_id" not in dumped
    assert "roles" not in dumped
    assert "selected_document_ref" not in dumped
    assert "active_artifact_refs" not in dumped
    assert "permitted_tool_names" not in dumped
    assert "focus_kind" not in dumped
    assert "focus_session_id" not in dumped
    assert agent_input.message.startswith("Where")
    assert agent_input.admissibility is Admissibility.PLAYER
    assert agent_input.focus.kind is FocusKind.NONE
    assert agent_input.surface.selected_object_ids == ["obj:1"]


def test_caller_cannot_inject_tools_through_sanitization() -> None:
    agent_input = sanitize_agent_input(
        message="hi",
        world_id="world:demo",
        campaign_id="camp:1",
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.PLAYER,
        surface_id="surface:plan",
        surface_mode=None,
        selected_object_ids=[],
        assembled_context="",
        revision_id=REVISION,
    )
    policy = _player_policy()
    context = AgentTurnContext(input=agent_input, capability_policy=policy)
    assert permitted_tool_names(context.capability_policy) == ["graph.search"]
    assert "permitted_tool_names" not in type(context.input).model_fields
    assert context.capability_policy.graph_scope is not None
    assert context.capability_policy.graph_scope.admissibility is Admissibility.PLAYER
    assert context.capability_policy.graph_scope.revision_pin == REVISION


def test_agent_turn_context_rejects_admissibility_mismatch() -> None:
    agent_input = sanitize_agent_input(
        message="hi",
        world_id="world:demo",
        campaign_id="camp:1",
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.GM,
        surface_id="surface:plan",
        surface_mode=None,
        selected_object_ids=[],
        assembled_context="",
        revision_id=REVISION,
    )
    with pytest.raises(ValidationError, match="admissibility"):
        AgentTurnContext(input=agent_input, capability_policy=_player_policy())


def test_agent_turn_context_rejects_unresolved_revision_pin() -> None:
    agent_input = sanitize_agent_input(
        message="hi",
        world_id="world:demo",
        campaign_id="camp:1",
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.PLAYER,
        surface_id="surface:plan",
        surface_mode=None,
        selected_object_ids=[],
        assembled_context="",
        revision_id=REVISION,
    )
    with pytest.raises(ValidationError, match="revision_pin"):
        AgentTurnContext(
            input=agent_input,
            capability_policy=_player_policy(revision_pin=None),
        )


def test_agent_turn_context_rejects_world_and_revision_mismatch() -> None:
    agent_input = sanitize_agent_input(
        message="hi",
        world_id="world:demo",
        campaign_id="camp:1",
        focus_kind=FocusKind.NONE,
        focus_session_id=None,
        admissibility=Admissibility.PLAYER,
        surface_id="surface:plan",
        surface_mode=None,
        selected_object_ids=[],
        assembled_context="",
        revision_id=REVISION,
    )
    with pytest.raises(ValidationError, match="world_id"):
        AgentTurnContext(
            input=agent_input,
            capability_policy=_player_policy(world_id="world:other"),
        )
    with pytest.raises(ValidationError, match="revision_id/revision_pin"):
        AgentTurnContext(
            input=agent_input,
            capability_policy=_player_policy(revision_pin="rev:" + "cd" * 16),
        )


def test_agent_turn_input_rejects_invalid_focus_combinations() -> None:
    surface = AdmittedSurfaceContext(surface_id="surface:plan")
    with pytest.raises(ValidationError):
        AgentTurnInput(
            message="hi",
            world_id="world:demo",
            campaign_id="camp:1",
            focus=ProjectionFocus(kind=FocusKind.NONE, session_id="ses:1"),
            admissibility=Admissibility.PLAYER,
            surface=surface,
            assembled_context="",
            revision_id=REVISION,
        )
    with pytest.raises(ValidationError):
        AgentTurnInput(
            message="hi",
            world_id="world:demo",
            campaign_id=None,
            focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="ses:1"),
            admissibility=Admissibility.PLAYER,
            surface=surface,
            assembled_context="",
            revision_id=REVISION,
        )
