"""Agent adapter protocol.

DungeonMind orchestrates agent turns through this port. An adapter receives
an assembled, capability-bounded context and returns an answer plus claims;
it never receives durable write authority, never assembles graph queries
itself, and never sees unfiltered scope. Hermes will be the first adapter
(``agents/hermes/``, optional extra, successor slice); replacing Hermes must
mean writing a new adapter, not changing DungeonMind.
"""

from typing import Protocol

from ..contracts.base import DungeonMindModel
from ..contracts.capability import CapabilityPolicy
from ..contracts.mind_turn import MindTurnRequest
from ..contracts.retrieval import Claim, DiagnosticEntry


class AgentTurnContext(DungeonMindModel):
    """Everything an adapter may see for one turn — assembled, bounded, explicit."""

    request: MindTurnRequest
    # Context assembled by DungeonMind (graph results, admitted evidence, budget).
    assembled_context: str
    capability_policy: CapabilityPolicy
    # The exact graph revision this turn is pinned to.
    revision_id: str


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
