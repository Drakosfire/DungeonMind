"""Application layer: repository protocols (ports) and orchestration seams.

Adapters live in ``dungeonmind.infrastructure.*``; this package never imports
them. All ports are synchronous (blocking) by design — transport layers
offload (e.g. ``asyncio.to_thread``) rather than forcing async into adapters,
following the statblocks_v1 discipline in DungeonMindServer.
"""

from .repositories import (
    ContributionRepository,
    EmbeddingRunRepository,
    IdentityDecisionRepository,
    MindThreadRepository,
    RetrievalSessionRepository,
    SemanticDocumentRepository,
    SemanticSearchPort,
    SourceRepository,
    WorldGraphRepository,
)

__all__ = [
    "ContributionRepository",
    "EmbeddingRunRepository",
    "IdentityDecisionRepository",
    "MindThreadRepository",
    "RetrievalSessionRepository",
    "SemanticDocumentRepository",
    "SemanticSearchPort",
    "SourceRepository",
    "WorldGraphRepository",
]
