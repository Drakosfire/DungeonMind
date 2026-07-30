"""Agent adapters receive sanitized input, not raw MindTurnRequest auth metadata."""

from dungeonmind.agents import sanitize_agent_input
from dungeonmind.contracts import Admissibility, FocusKind


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
        permitted_tool_names=["graph.search"],
        revision_id="rev:" + "ab" * 16,
    )
    dumped = agent_input.model_dump()
    assert "caller_id" not in dumped
    assert "tenant_id" not in dumped
    assert "roles" not in dumped
    assert "selected_document_ref" not in dumped
    assert "active_artifact_refs" not in dumped
    assert agent_input.message.startswith("Where")
    assert agent_input.admissibility is Admissibility.PLAYER
    assert agent_input.surface.selected_object_ids == ["obj:1"]
