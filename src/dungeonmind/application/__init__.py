"""Application layer: repository protocols (ports) and orchestration seams.

Adapters live in ``dungeonmind.infrastructure.*``; this package never imports
them. All ports are synchronous (blocking) by design — transport layers
offload (e.g. ``asyncio.to_thread``) rather than forcing async into adapters,
following the statblocks_v1 discipline in DungeonMindServer.
"""

from .contribution_review import finalize_contribution_review, load_contribution_review
from .graph_snapshot import (
    GraphObjectView,
    GraphRelationshipView,
    GraphSnapshotReader,
    ParsedGraphSnapshot,
    UnionGraphV1SnapshotReader,
)
from .mind_turn import FixedClock, MindTurnService
from .query_embedding import QueryEmbeddingProvider
from .repositories import (
    ContributionRepository,
    ContributionReviewRepository,
    EmbeddingRunRepository,
    IdentityDecisionRepository,
    MindThreadRepository,
    RetrievalSessionRepository,
    SemanticDocumentRepository,
    SemanticSearchPort,
    SourceRepository,
    WorldGraphRepository,
)
from .review_materialization import (
    FinalizedReviewGraphMaterialization,
    materialize_finalized_review,
)

__all__ = [
    "ContributionRepository",
    "ContributionReviewRepository",
    "EmbeddingRunRepository",
    "FinalizedReviewGraphMaterialization",
    "FixedClock",
    "GraphObjectView",
    "GraphRelationshipView",
    "GraphSnapshotReader",
    "IdentityDecisionRepository",
    "MindThreadRepository",
    "MindTurnService",
    "ParsedGraphSnapshot",
    "QueryEmbeddingProvider",
    "RetrievalSessionRepository",
    "SemanticDocumentRepository",
    "SemanticSearchPort",
    "SourceRepository",
    "UnionGraphV1SnapshotReader",
    "WorldGraphRepository",
    "finalize_contribution_review",
    "load_contribution_review",
    "materialize_finalized_review",
]
