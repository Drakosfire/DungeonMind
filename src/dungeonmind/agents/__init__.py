"""Agent integration seam. Hermes is the first adapter, never a core dependency."""

from .protocol import (
    AdmittedSurfaceContext,
    AgentAdapter,
    AgentTurnContext,
    AgentTurnInput,
    AgentTurnResult,
    sanitize_agent_input,
)

__all__ = [
    "AdmittedSurfaceContext",
    "AgentAdapter",
    "AgentTurnContext",
    "AgentTurnInput",
    "AgentTurnResult",
    "sanitize_agent_input",
]
