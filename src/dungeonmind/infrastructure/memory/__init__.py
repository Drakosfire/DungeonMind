"""In-memory adapters for unit tests and local development.

Semantics match the port contracts (including CAS/stale-parent behavior) so
that unit tests pin the same invariants the PostgreSQL adapters must honor.
"""

from .repositories import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryEmbeddingRunRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryMindThreadRepository,
    InMemoryRetrievalSessionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

__all__ = [
    "InMemoryContributionRepository",
    "InMemoryContributionReviewRepository",
    "InMemoryEmbeddingRunRepository",
    "InMemoryExistingWorldAdoptionRepository",
    "InMemoryFinalizedReviewPublicationRepository",
    "InMemoryIdentityDecisionRepository",
    "InMemoryMindThreadRepository",
    "InMemoryRetrievalSessionRepository",
    "InMemoryReviewedWorldInitializationRepository",
    "InMemorySemanticDocumentRepository",
    "InMemorySemanticSearch",
    "InMemorySourceRepository",
    "InMemoryWorldGraphRepository",
]
