"""Agent adapter protocol.

DungeonMind orchestrates agent turns through this port. An adapter receives
a sanitized, capability-bounded input — never the raw MindTurnRequest with
caller/tenant authentication metadata — and returns an answer plus claims.
It never receives durable write authority, never assembles graph queries
itself, and never sees unfiltered scope. Hermes will be the first adapter
(``agents/hermes/``, optional extra, successor slice); replacing Hermes must
mean writing a new adapter, not changing DungeonMind.
"""

from typing import Protocol

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
    permitted_tool_names: list[str] = []
    revision_id: str


class AgentTurnContext(DungeonMindModel):
    """Everything an adapter may see for one turn — assembled, bounded, explicit."""

    input: AgentTurnInput
    # Capability policy for fail-closed tool evaluation inside the adapter.
    # Does not include caller/tenant identity.
    capability_policy: CapabilityPolicy


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
    permitted_tool_names: list[str],
    revision_id: str,
) -> AgentTurnInput:
    """Build agent input from orchestration state without auth/tenancy fields."""
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
        permitted_tool_names=list(permitted_tool_names),
        revision_id=revision_id,
    )
