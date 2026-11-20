"""Application layer: repository protocols (ports) and orchestration seams.

Adapters live in ``dungeonmind.infrastructure.*``; this package never imports
them. All ports are synchronous (blocking) by design — transport layers
offload (e.g. ``asyncio.to_thread``) rather than forcing async into adapters,
following the statblocks_v1 discipline in DungeonMindServer.
"""

from importlib import import_module as _import_module
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from .contribution_review import finalize_contribution_review, load_contribution_review
    from .contribution_review_v2 import (
        finalize_contribution_review_v2,
        load_contribution_review_v2,
    )
    from .contribution_review_v3 import (
        finalize_contribution_review_v3,
        load_contribution_review_v3,
    )
    from .contribution_review_v4 import finalize_contribution_review_v4, load_contribution_review_v4
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
    from .publication_admission import (
        InMemoryPublicationAdmissionRepository,
        PublicationAdmissionRegistry,
        PublicationAdmissionValidator,
    )
    from .publication_history import (
        HistoricalReviewPublication,
        PublicationHistory,
        discover_review_publications,
    )
    from .query_embedding import QueryEmbeddingProvider
    from .repositories import (
        ContributionRepository,
        ContributionReviewRepository,
        EmbeddingRunRepository,
        ExistingWorldAdoptionRepository,
        FinalizedReviewPublicationRepository,
        IdentityDecisionRepository,
        MindThreadRepository,
        PublicationAdmissionPolicyRepository,
        RetrievalSessionRepository,
        ReviewedWorldInitializationRepository,
        SemanticDocumentRepository,
        SemanticSearchPort,
        SourceRepository,
        WorldGraphRepository,
        WorldIdentityReconciliationRepository,
    )
    from .review_materialization import (
        FinalizedReviewGraphMaterialization,
        materialize_finalized_review,
    )
    from .review_materialization_v4 import materialize_finalized_review_v4
    from .review_materialization_v6 import materialize_finalized_review_v6
    from .review_publication import FinalizedReviewPublication
    from .reviewed_world_initialization import (
        FirstWorldMaterialization,
        initialize_reviewed_world,
        materialize_reviewed_world_initialization_v6,
    )
    from .source_admission import admit_source_revision
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
    )
    from .world_graph_read_context import WorldGraphReadContext
    from .world_graph_retrieval import (
        CONTEXT_ANCHOR_ID_PREFIX,
        AdmittedAssertionValue,
        CompleteObjectLookupResult,
        EvidenceRetrievalResult,
        EvidenceTarget,
        GraphSearchResult,
        NeighborhoodResult,
        ObjectLookupResult,
        RecapContextSectionSelectorV1,
        RecapSourceContextV1,
        RetrievalBounds,
        RetrievalCoverage,
        ReviewedSourceSessionRequest,
        SelectedObjectCompleteness,
        SourceAnchorBatchRequest,
        SourceAnchorBatchResolution,
        SourceAnchorIndexEntry,
        SourceAnchorIndexRequest,
        SourceAnchorIndexResult,
        SourceAnchorMetadata,
        SourceAnchorResolution,
        SourceContextIndexRequest,
        SourceContextIndexResult,
        SourceContextResolution,
        derive_source_anchor_id,
    )
    from .world_identity_reconciliation import (
        CanonicalRebindRequest,
        IdentityReconciliationPublicationResult,
        materialize_identity_reconciliation,
    )


_EXPORTS: dict[str, tuple[str, str]] = {
    "finalize_contribution_review": (".contribution_review", "finalize_contribution_review"),
    "load_contribution_review": (".contribution_review", "load_contribution_review"),
    "finalize_contribution_review_v2": (
        ".contribution_review_v2",
        "finalize_contribution_review_v2",
    ),
    "load_contribution_review_v2": (".contribution_review_v2", "load_contribution_review_v2"),
    "finalize_contribution_review_v3": (
        ".contribution_review_v3",
        "finalize_contribution_review_v3",
    ),
    "load_contribution_review_v3": (".contribution_review_v3", "load_contribution_review_v3"),
    "finalize_contribution_review_v4": (
        ".contribution_review_v4",
        "finalize_contribution_review_v4",
    ),
    "load_contribution_review_v4": (".contribution_review_v4", "load_contribution_review_v4"),
    "adopt_existing_world": (".existing_world_adoption", "adopt_existing_world"),
    "repair_existing_world_adoption_source_classification": (
        ".existing_world_adoption_repair",
        "repair_existing_world_adoption_source_classification",
    ),
    "ExistingWorldCorrespondenceService": (
        ".existing_world_correspondence",
        "ExistingWorldCorrespondenceService",
    ),
    "evaluate_fictional_time_query": (".fictional_time", "evaluate_fictional_time_query"),
    "query_fictional_time_shadow_at_revision": (
        ".fictional_time_query_service",
        "query_fictional_time_shadow_at_revision",
    ),
    "GraphObjectView": (".graph_snapshot", "GraphObjectView"),
    "GraphRelationshipView": (".graph_snapshot", "GraphRelationshipView"),
    "GraphSnapshotReader": (".graph_snapshot", "GraphSnapshotReader"),
    "ParsedGraphSnapshot": (".graph_snapshot", "ParsedGraphSnapshot"),
    "UnionGraphV1SnapshotReader": (".graph_snapshot", "UnionGraphV1SnapshotReader"),
    "FixedClock": (".mind_turn", "FixedClock"),
    "MindTurnService": (".mind_turn", "MindTurnService"),
    "ParsedImmutableRevisionCache": (".parsed_revision_cache", "ParsedImmutableRevisionCache"),
    "InMemoryPublicationAdmissionRepository": (
        ".publication_admission",
        "InMemoryPublicationAdmissionRepository",
    ),
    "PublicationAdmissionRegistry": (".publication_admission", "PublicationAdmissionRegistry"),
    "PublicationAdmissionValidator": (".publication_admission", "PublicationAdmissionValidator"),
    "HistoricalReviewPublication": (".publication_history", "HistoricalReviewPublication"),
    "PublicationHistory": (".publication_history", "PublicationHistory"),
    "discover_review_publications": (".publication_history", "discover_review_publications"),
    "QueryEmbeddingProvider": (".query_embedding", "QueryEmbeddingProvider"),
    "ContributionRepository": (".repositories", "ContributionRepository"),
    "ContributionReviewRepository": (".repositories", "ContributionReviewRepository"),
    "EmbeddingRunRepository": (".repositories", "EmbeddingRunRepository"),
    "ExistingWorldAdoptionRepository": (".repositories", "ExistingWorldAdoptionRepository"),
    "FinalizedReviewPublicationRepository": (
        ".repositories",
        "FinalizedReviewPublicationRepository",
    ),
    "IdentityDecisionRepository": (".repositories", "IdentityDecisionRepository"),
    "MindThreadRepository": (".repositories", "MindThreadRepository"),
    "PublicationAdmissionPolicyRepository": (
        ".repositories",
        "PublicationAdmissionPolicyRepository",
    ),
    "RetrievalSessionRepository": (".repositories", "RetrievalSessionRepository"),
    "ReviewedWorldInitializationRepository": (
        ".repositories",
        "ReviewedWorldInitializationRepository",
    ),
    "SemanticDocumentRepository": (".repositories", "SemanticDocumentRepository"),
    "SemanticSearchPort": (".repositories", "SemanticSearchPort"),
    "SourceRepository": (".repositories", "SourceRepository"),
    "WorldGraphRepository": (".repositories", "WorldGraphRepository"),
    "WorldIdentityReconciliationRepository": (
        ".repositories",
        "WorldIdentityReconciliationRepository",
    ),
    "FinalizedReviewGraphMaterialization": (
        ".review_materialization",
        "FinalizedReviewGraphMaterialization",
    ),
    "materialize_finalized_review": (".review_materialization", "materialize_finalized_review"),
    "materialize_finalized_review_v4": (
        ".review_materialization_v4",
        "materialize_finalized_review_v4",
    ),
    "materialize_finalized_review_v6": (
        ".review_materialization_v6",
        "materialize_finalized_review_v6",
    ),
    "FinalizedReviewPublication": (".review_publication", "FinalizedReviewPublication"),
    "FirstWorldMaterialization": (".reviewed_world_initialization", "FirstWorldMaterialization"),
    "initialize_reviewed_world": (".reviewed_world_initialization", "initialize_reviewed_world"),
    "materialize_reviewed_world_initialization_v6": (
        ".reviewed_world_initialization",
        "materialize_reviewed_world_initialization_v6",
    ),
    "admit_source_revision": (".source_admission", "admit_source_revision"),
    "SourceProvenanceSnapshot": (".source_provenance_snapshot", "SourceProvenanceSnapshot"),
    "NOOP_READ_OBSERVER": (".world_graph_observability", "NOOP_READ_OBSERVER"),
    "PhaseRecorder": (".world_graph_observability", "PhaseRecorder"),
    "SystemMonotonicReadClock": (".world_graph_observability", "SystemMonotonicReadClock"),
    "WorldGraphReadClock": (".world_graph_observability", "WorldGraphReadClock"),
    "WorldGraphReadObservation": (".world_graph_observability", "WorldGraphReadObservation"),
    "WorldGraphReadObserver": (".world_graph_observability", "WorldGraphReadObserver"),
    "WorldGraphReadPhaseDuration": (".world_graph_observability", "WorldGraphReadPhaseDuration"),
    "classify_read_failure": (".world_graph_observability", "classify_read_failure"),
    "emit_read_observation": (".world_graph_observability", "emit_read_observation"),
    "ProjectionClock": (".world_graph_projection", "ProjectionClock"),
    "WorldGraphProjectionResult": (".world_graph_projection", "WorldGraphProjectionResult"),
    "WorldGraphReadContext": (".world_graph_read_context", "WorldGraphReadContext"),
    "CONTEXT_ANCHOR_ID_PREFIX": (".world_graph_retrieval", "CONTEXT_ANCHOR_ID_PREFIX"),
    "AdmittedAssertionValue": (".world_graph_retrieval", "AdmittedAssertionValue"),
    "CompleteObjectLookupResult": (".world_graph_retrieval", "CompleteObjectLookupResult"),
    "EvidenceRetrievalResult": (".world_graph_retrieval", "EvidenceRetrievalResult"),
    "EvidenceTarget": (".world_graph_retrieval", "EvidenceTarget"),
    "GraphSearchResult": (".world_graph_retrieval", "GraphSearchResult"),
    "NeighborhoodResult": (".world_graph_retrieval", "NeighborhoodResult"),
    "ObjectLookupResult": (".world_graph_retrieval", "ObjectLookupResult"),
    "RecapContextSectionSelectorV1": (".world_graph_retrieval", "RecapContextSectionSelectorV1"),
    "RecapSourceContextV1": (".world_graph_retrieval", "RecapSourceContextV1"),
    "RetrievalBounds": (".world_graph_retrieval", "RetrievalBounds"),
    "RetrievalCoverage": (".world_graph_retrieval", "RetrievalCoverage"),
    "ReviewedSourceSessionRequest": (".world_graph_retrieval", "ReviewedSourceSessionRequest"),
    "SelectedObjectCompleteness": (".world_graph_retrieval", "SelectedObjectCompleteness"),
    "SourceAnchorBatchRequest": (".world_graph_retrieval", "SourceAnchorBatchRequest"),
    "SourceAnchorBatchResolution": (".world_graph_retrieval", "SourceAnchorBatchResolution"),
    "SourceAnchorIndexEntry": (".world_graph_retrieval", "SourceAnchorIndexEntry"),
    "SourceAnchorIndexRequest": (".world_graph_retrieval", "SourceAnchorIndexRequest"),
    "SourceAnchorIndexResult": (".world_graph_retrieval", "SourceAnchorIndexResult"),
    "SourceAnchorMetadata": (".world_graph_retrieval", "SourceAnchorMetadata"),
    "SourceAnchorResolution": (".world_graph_retrieval", "SourceAnchorResolution"),
    "SourceContextIndexRequest": (".world_graph_retrieval", "SourceContextIndexRequest"),
    "SourceContextIndexResult": (".world_graph_retrieval", "SourceContextIndexResult"),
    "SourceContextResolution": (".world_graph_retrieval", "SourceContextResolution"),
    "derive_source_anchor_id": (".world_graph_retrieval", "derive_source_anchor_id"),
    "CanonicalRebindRequest": (".world_identity_reconciliation", "CanonicalRebindRequest"),
    "IdentityReconciliationPublicationResult": (
        ".world_identity_reconciliation",
        "IdentityReconciliationPublicationResult",
    ),
    "materialize_identity_reconciliation": (
        ".world_identity_reconciliation",
        "materialize_identity_reconciliation",
    ),
}

__all__ = [
    "CONTEXT_ANCHOR_ID_PREFIX",
    "NOOP_READ_OBSERVER",
    "AdmittedAssertionValue",
    "CanonicalRebindRequest",
    "CompleteObjectLookupResult",
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
    "FirstWorldMaterialization",
    "FixedClock",
    "GraphObjectView",
    "GraphRelationshipView",
    "GraphSearchResult",
    "GraphSnapshotReader",
    "HistoricalReviewPublication",
    "IdentityDecisionRepository",
    "IdentityReconciliationPublicationResult",
    "InMemoryPublicationAdmissionRepository",
    "MindThreadRepository",
    "MindTurnService",
    "NeighborhoodResult",
    "ObjectLookupResult",
    "ParsedGraphSnapshot",
    "ParsedImmutableRevisionCache",
    "PhaseRecorder",
    "ProjectionClock",
    "PublicationAdmissionPolicyRepository",
    "PublicationAdmissionRegistry",
    "PublicationAdmissionValidator",
    "PublicationHistory",
    "QueryEmbeddingProvider",
    "RecapContextSectionSelectorV1",
    "RecapSourceContextV1",
    "RetrievalBounds",
    "RetrievalCoverage",
    "RetrievalSessionRepository",
    "ReviewedSourceSessionRequest",
    "ReviewedWorldInitializationRepository",
    "SelectedObjectCompleteness",
    "SemanticDocumentRepository",
    "SemanticSearchPort",
    "SourceAnchorBatchRequest",
    "SourceAnchorBatchResolution",
    "SourceAnchorIndexEntry",
    "SourceAnchorIndexRequest",
    "SourceAnchorIndexResult",
    "SourceAnchorMetadata",
    "SourceAnchorResolution",
    "SourceContextIndexRequest",
    "SourceContextIndexResult",
    "SourceContextResolution",
    "SourceProvenanceSnapshot",
    "SourceRepository",
    "SystemMonotonicReadClock",
    "UnionGraphV1SnapshotReader",
    "WorldGraphProjectionResult",
    "WorldGraphReadClock",
    "WorldGraphReadContext",
    "WorldGraphReadObservation",
    "WorldGraphReadObserver",
    "WorldGraphReadPhaseDuration",
    "WorldGraphRepository",
    "WorldIdentityReconciliationRepository",
    "admit_source_revision",
    "adopt_existing_world",
    "classify_read_failure",
    "derive_source_anchor_id",
    "discover_review_publications",
    "emit_read_observation",
    "evaluate_fictional_time_query",
    "finalize_contribution_review",
    "finalize_contribution_review_v2",
    "finalize_contribution_review_v3",
    "initialize_reviewed_world",
    "load_contribution_review",
    "load_contribution_review_v2",
    "load_contribution_review_v3",
    "materialize_finalized_review",
    "materialize_finalized_review_v6",
    "materialize_identity_reconciliation",
    "materialize_reviewed_world_initialization_v6",
    "query_fictional_time_shadow_at_revision",
    "repair_existing_world_adoption_source_classification",
]

__all__ += [
    "finalize_contribution_review_v4",
    "load_contribution_review_v4",
    "materialize_finalized_review_v4",
]


def __getattr__(name: str) -> object:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(_import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _EXPORTS.keys())
