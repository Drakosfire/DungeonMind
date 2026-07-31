"""Agent integration seam. Hermes is the first adapter, never a core dependency."""

from .fixture import FIXTURE_AGENT_ADAPTER_ID, FixtureGroundedAgentAdapter
from .protocol import (
    AdmittedSurfaceContext,
    AgentAdapter,
    AgentTurnContext,
    AgentTurnInput,
    AgentTurnResult,
    sanitize_agent_input,
)

__all__ = [
    "FIXTURE_AGENT_ADAPTER_ID",
    "AdmittedSurfaceContext",
    "AgentAdapter",
    "AgentTurnContext",
    "AgentTurnInput",
    "AgentTurnResult",
    "FixtureGroundedAgentAdapter",
    "sanitize_agent_input",
]
