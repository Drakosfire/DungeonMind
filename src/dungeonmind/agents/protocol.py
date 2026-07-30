"""Agent adapter protocol.

DungeonMind orchestrates agent turns through this port. An adapter receives
a sanitized, capability-bounded input — never the raw MindTurnRequest with
caller/tenant authentication metadata — and returns an answer plus claims.
It never receives durable write authority, never assembles graph queries
itself, and never sees unfiltered scope. Hermes will be the first adapter
(``agents/hermes/``, optional extra, successor slice); replacing Hermes must
mean writing a new adapter, not changing DungeonMind.

``CapabilityPolicy`` on ``AgentTurnContext`` is the sole authority for tools.
Adapters that need a serialized tool list must derive it via
``domain.capability.permitted_tool_names`` — never from caller-supplied names.

When a policy carries ``graph_scope``, it must agree with ``AgentTurnInput``
on world, campaign, focus, admissibility, and the resolved revision pin —
otherwise the turn is split-brain and rejected.
"""

from typing import Protocol, Self

from pydantic import model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.capability import CapabilityPolicy
from ..contracts.projection import Admissibility, FocusKind
from ..contracts.retrieval import Claim, DiagnosticEntry


class AdmittedSurfaceContext(DungeonMindModel):
    """Surface context admitted for agent use — no auth/tenancy metadata."""

    surface_id: str
    mode: str | None = None
    selected_object_ids: list[str] = []


class AgentTurnInput(DungeonMindModel):
    """Sanitized agent input. Auth/tenancy stay in the orchestration layer."""

    message: str
    world_id: str
    campaign_id: str | None = None
    focus_kind: FocusKind = FocusKind.NONE
    focus_session_id: str | None = None
    admissibility: Admissibility
    surface: AdmittedSurfaceContext
    assembled_context: str
    revision_id: str


class AgentTurnContext(DungeonMindModel):
    """Everything an adapter may see for one turn — assembled, bounded, explicit.

    ``capability_policy.graph_scope``, when present, must match ``input`` on
    world/campaign/focus/admissibility and must pin ``revision_pin`` to the
    same resolved ``input.revision_id`` (never an unresolved ``None`` pin).
    """

    input: AgentTurnInput
    # Sole tool authority. Derive permitted names from this policy.
    capability_policy: CapabilityPolicy

    @model_validator(mode="after")
    def _graph_scope_agrees_with_input(self) -> Self:
        scope = self.capability_policy.graph_scope
        if scope is None:
            return self
        if scope.revision_pin is None:
            raise ValueError(
                "AgentTurnContext requires capability_policy.graph_scope.revision_pin "
                "bound to the resolved input.revision_id"
            )
        inp = self.input
        mismatches: list[str] = []
        if inp.world_id != scope.world_id:
            mismatches.append("world_id")
        if inp.campaign_id != scope.campaign_id:
            mismatches.append("campaign_id")
        if inp.admissibility != scope.admissibility:
            mismatches.append("admissibility")
        if inp.focus_kind != scope.focus.kind:
            mismatches.append("focus.kind")
        if inp.focus_session_id != scope.focus.session_id:
            mismatches.append("focus.session_id")
        if inp.revision_id != scope.revision_pin:
            mismatches.append("revision_id/revision_pin")
        if mismatches:
            raise ValueError(
                "AgentTurnInput and CapabilityPolicy.graph_scope disagree on: "
                + ", ".join(mismatches)
            )
        return self


class AgentTurnResult(DungeonMindModel):
    answer: str
    claims: list[Claim] = []
    diagnostics: list[DiagnosticEntry] = []


class AgentAdapter(Protocol):
    """One agent provider behind the port. Adapters hold no graph authority."""

    @property
    def adapter_id(self) -> str: ...

    def execute_turn(self, context: AgentTurnContext) -> AgentTurnResult:
        """Produce an answer for the turn. Must honor ``capability_policy``
        fail-closed; must not persist anything."""
        ...


def sanitize_agent_input(
    *,
    message: str,
    world_id: str,
    campaign_id: str | None,
    focus_kind: FocusKind,
    focus_session_id: str | None,
    admissibility: Admissibility,
    surface_id: str,
    surface_mode: str | None,
    selected_object_ids: list[str],
    assembled_context: str,
    revision_id: str,
) -> AgentTurnInput:
    """Build agent input from orchestration state without auth/tenancy fields.

    Does not accept a permitted-tool list — tools are derived from
    ``CapabilityPolicy`` on ``AgentTurnContext``.
    """
    return AgentTurnInput(
        message=message,
        world_id=world_id,
        campaign_id=campaign_id,
        focus_kind=focus_kind,
        focus_session_id=focus_session_id,
        admissibility=admissibility,
        surface=AdmittedSurfaceContext(
            surface_id=surface_id,
            mode=surface_mode,
            selected_object_ids=list(selected_object_ids),
        ),
        assembled_context=assembled_context,
        revision_id=revision_id,
    )
