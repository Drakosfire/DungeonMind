"""Lazy PostgreSQL adapter exports.

Individual adapters require their own optional dependencies only when requested.
The explicitly requested legacy bundle may load the full adapter family.
"""

from importlib import import_module as _import_module
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from ...application.publication_admission import (
        PublicationAdmissionRegistry as PublicationAdmissionRegistry,
    )
    from .database import PostgresDatabase
    from .existing_world_adoption import PostgresExistingWorldAdoptionRepository
    from .graph import PostgresWorldGraphRepository
    from .publication_admission import PostgresPublicationAdmissionRepository
    from .records import (
        PostgresContributionRepository,
        PostgresContributionReviewRepository,
        PostgresIdentityDecisionRepository,
        PostgresRetrievalSessionRepository,
        PostgresSourceRepository,
    )
    from .review_publication import PostgresFinalizedReviewPublicationRepository
    from .reviewed_world_initialization import PostgresReviewedWorldInitializationRepository
    from .semantic import (
        PostgresEmbeddingRunRepository,
        PostgresSemanticDocumentRepository,
        PostgresSemanticSearch,
    )
    from .threads import PostgresMindThreadRepository
    from .vnext_sources import PostgresNativeSourceEvidenceRepository
    from .world_identity_reconciliation import PostgresWorldIdentityReconciliationRepository


_EXPORTS: dict[str, tuple[str, str]] = {
    "PublicationAdmissionRegistry": (
        "...application.publication_admission",
        "PublicationAdmissionRegistry",
    ),
    "PostgresDatabase": (".database", "PostgresDatabase"),
    "PostgresExistingWorldAdoptionRepository": (
        ".existing_world_adoption",
        "PostgresExistingWorldAdoptionRepository",
    ),
    "PostgresWorldGraphRepository": (".graph", "PostgresWorldGraphRepository"),
    "PostgresPublicationAdmissionRepository": (
        ".publication_admission",
        "PostgresPublicationAdmissionRepository",
    ),
    "PostgresContributionRepository": (".records", "PostgresContributionRepository"),
    "PostgresContributionReviewRepository": (".records", "PostgresContributionReviewRepository"),
    "PostgresIdentityDecisionRepository": (".records", "PostgresIdentityDecisionRepository"),
    "PostgresRetrievalSessionRepository": (".records", "PostgresRetrievalSessionRepository"),
    "PostgresSourceRepository": (".records", "PostgresSourceRepository"),
    "PostgresFinalizedReviewPublicationRepository": (
        ".review_publication",
        "PostgresFinalizedReviewPublicationRepository",
    ),
    "PostgresReviewedWorldInitializationRepository": (
        ".reviewed_world_initialization",
        "PostgresReviewedWorldInitializationRepository",
    ),
    "PostgresEmbeddingRunRepository": (".semantic", "PostgresEmbeddingRunRepository"),
    "PostgresSemanticDocumentRepository": (".semantic", "PostgresSemanticDocumentRepository"),
    "PostgresSemanticSearch": (".semantic", "PostgresSemanticSearch"),
    "PostgresMindThreadRepository": (".threads", "PostgresMindThreadRepository"),
    "PostgresNativeSourceEvidenceRepository": (
        ".vnext_sources",
        "PostgresNativeSourceEvidenceRepository",
    ),
    "PostgresWorldIdentityReconciliationRepository": (
        ".world_identity_reconciliation",
        "PostgresWorldIdentityReconciliationRepository",
    ),
}

__all__ = [
    "PostgresContributionRepository",
    "PostgresContributionReviewRepository",
    "PostgresDatabase",
    "PostgresEmbeddingRunRepository",
    "PostgresExistingWorldAdoptionRepository",
    "PostgresFinalizedReviewPublicationRepository",
    "PostgresIdentityDecisionRepository",
    "PostgresMindThreadRepository",
    "PostgresNativeSourceEvidenceRepository",
    "PostgresPublicationAdmissionRepository",
    "PostgresRetrievalSessionRepository",
    "PostgresReviewedWorldInitializationRepository",
    "PostgresSemanticDocumentRepository",
    "PostgresSemanticSearch",
    "PostgresSourceRepository",
    "PostgresWorldGraphRepository",
    "PostgresWorldIdentityReconciliationRepository",
]


class PostgresRepositoryBundle:
    """Optional convenience wiring; individual repositories stay explicit."""

    if _TYPE_CHECKING:
        database: PostgresDatabase
        publication_admission: PostgresPublicationAdmissionRepository
        world_graph: PostgresWorldGraphRepository
        contributions: PostgresContributionRepository
        contribution_reviews: PostgresContributionReviewRepository
        finalized_review_publications: PostgresFinalizedReviewPublicationRepository
        existing_world_adoptions: PostgresExistingWorldAdoptionRepository
        reviewed_world_initializations: PostgresReviewedWorldInitializationRepository
        identity_decisions: PostgresIdentityDecisionRepository
        identity_reconciliation: PostgresWorldIdentityReconciliationRepository
        sources: PostgresSourceRepository
        retrieval_sessions: PostgresRetrievalSessionRepository
        threads: PostgresMindThreadRepository
        embedding_runs: PostgresEmbeddingRunRepository
        semantic_documents: PostgresSemanticDocumentRepository
        semantic_search: PostgresSemanticSearch

    def __init__(
        self,
        database: "PostgresDatabase",
        *,
        admission_registry: "PublicationAdmissionRegistry | None" = None,
    ) -> None:
        from ._bundle import initialize_bundle

        initialize_bundle(self, database, admission_registry=admission_registry)


# Retain the real public source location while delaying annotation dependencies
# until the aggregate is explicitly requested.
_PostgresRepositoryBundle = PostgresRepositoryBundle
globals().pop("PostgresRepositoryBundle")


def __getattr__(name: str) -> object:
    if name == "PostgresRepositoryBundle":
        database_type = _import_module(".database", __name__).PostgresDatabase
        registry_type = _import_module(
            "...application.publication_admission", __name__
        ).PublicationAdmissionRegistry
        _PostgresRepositoryBundle.__init__.__annotations__.update(
            database=database_type, admission_registry=registry_type | None
        )
        globals()[name] = _PostgresRepositoryBundle
        return _PostgresRepositoryBundle
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(_import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _EXPORTS.keys() | {"PostgresRepositoryBundle"})
