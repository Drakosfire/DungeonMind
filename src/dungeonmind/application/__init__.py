"""Application layer: repository protocols (ports) and orchestration seams.

Adapters live in ``dungeonmind.infrastructure.*``; this package never imports
them. All ports are synchronous (blocking) by design — transport layers
offload (e.g. ``asyncio.to_thread``) rather than forcing async into adapters,
following the statblocks_v1 discipline in DungeonMindServer.
"""

from .contribution_review import finalize_contribution_review, load_contribution_review
from .existing_world_adoption import adopt_existing_world
from .fictional_time import evaluate_fictional_time_query
from .fictional_time_query_service import query_fictional_time_shadow_at_revision
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
    ExistingWorldAdoptionRepository,
    FinalizedReviewPublicationRepository,
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
from .review_publication import (
    FinalizedReviewPublication,
    publish_finalized_review,
)

__all__ = [
    "ContributionRepository",
    "ContributionReviewRepository",
    "EmbeddingRunRepository",
    "ExistingWorldAdoptionRepository",
    "FinalizedReviewGraphMaterialization",
    "FinalizedReviewPublication",
    "FinalizedReviewPublicationRepository",
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
    "adopt_existing_world",
    "evaluate_fictional_time_query",
    "finalize_contribution_review",
    "load_contribution_review",
    "materialize_finalized_review",
    "publish_finalized_review",
    "query_fictional_time_shadow_at_revision",
]
