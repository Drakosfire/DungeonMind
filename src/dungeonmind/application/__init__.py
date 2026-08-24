"""Application layer: repository protocols (ports) and orchestration seams.

Adapters live in ``dungeonmind.infrastructure.*``; this package never imports
them. All ports are synchronous (blocking) by design — transport layers
offload (e.g. ``asyncio.to_thread``) rather than forcing async into adapters,
following the statblocks_v1 discipline in DungeonMindServer.
"""

from .contribution_review import finalize_contribution_review, load_contribution_review
from .contribution_review_v2 import (
    finalize_contribution_review_v2,
    load_contribution_review_v2,
)
from .existing_world_adoption import adopt_existing_world
from .existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
)
from .existing_world_correspondence import ExistingWorldCorrespondenceService
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
from .parsed_revision_cache import ParsedImmutableRevisionCache
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
from .review_materialization_v6 import materialize_finalized_review_v6
from .review_publication import (
    FinalizedReviewPublication,
    publish_finalized_review,
)
from .source_provenance_snapshot import SourceProvenanceSnapshot
from .world_graph_observability import (
    NOOP_READ_OBSERVER,
    PhaseRecorder,
    SystemMonotonicReadClock,
    WorldGraphReadClock,
    WorldGraphReadObservation,
    WorldGraphReadObserver,
    WorldGraphReadPhaseDuration,
    classify_read_failure,
    emit_read_observation,
)
from .world_graph_projection import (
    ProjectionClock,
    WorldGraphProjectionResult,
    WorldGraphProjectionService,
)
from .world_graph_read_context import WorldGraphReadContext
from .world_graph_retrieval import (
    AdmittedAssertionValue,
    EvidenceRetrievalResult,
    EvidenceTarget,
    GraphSearchResult,
    NeighborhoodResult,
    ObjectLookupResult,
    RetrievalBounds,
    RetrievalCoverage,
    SourceAnchorMetadata,
    SourceAnchorResolution,
    WorldGraphRetrievalService,
    derive_source_anchor_id,
)

__all__ = [
    "NOOP_READ_OBSERVER",
    "AdmittedAssertionValue",
    "ContributionRepository",
    "ContributionReviewRepository",
    "EmbeddingRunRepository",
    "EvidenceRetrievalResult",
    "EvidenceTarget",
    "ExistingWorldAdoptionRepository",
    "ExistingWorldCorrespondenceService",
    "FinalizedReviewGraphMaterialization",
    "FinalizedReviewPublication",
    "FinalizedReviewPublicationRepository",
    "FixedClock",
    "GraphObjectView",
    "GraphRelationshipView",
    "GraphSearchResult",
    "GraphSnapshotReader",
    "IdentityDecisionRepository",
    "MindThreadRepository",
    "MindTurnService",
    "NeighborhoodResult",
    "ObjectLookupResult",
    "ParsedGraphSnapshot",
    "ParsedImmutableRevisionCache",
    "PhaseRecorder",
    "ProjectionClock",
    "QueryEmbeddingProvider",
    "RetrievalBounds",
    "RetrievalCoverage",
    "RetrievalSessionRepository",
    "SemanticDocumentRepository",
    "SemanticSearchPort",
    "SourceAnchorMetadata",
    "SourceAnchorResolution",
    "SourceProvenanceSnapshot",
    "SourceRepository",
    "SystemMonotonicReadClock",
    "UnionGraphV1SnapshotReader",
    "WorldGraphProjectionResult",
    "WorldGraphProjectionService",
    "WorldGraphReadClock",
    "WorldGraphReadContext",
    "WorldGraphReadObservation",
    "WorldGraphReadObserver",
    "WorldGraphReadPhaseDuration",
    "WorldGraphRepository",
    "WorldGraphRetrievalService",
    "adopt_existing_world",
    "classify_read_failure",
    "derive_source_anchor_id",
    "emit_read_observation",
    "evaluate_fictional_time_query",
    "finalize_contribution_review",
    "finalize_contribution_review_v2",
    "load_contribution_review",
    "load_contribution_review_v2",
    "materialize_finalized_review",
    "materialize_finalized_review_v6",
    "publish_finalized_review",
    "query_fictional_time_shadow_at_revision",
    "repair_existing_world_adoption_source_classification",
]
