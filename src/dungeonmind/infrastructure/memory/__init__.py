"""In-memory adapters for unit tests and local development.

Semantics match the port contracts (including CAS/stale-parent behavior) so
that unit tests pin the same invariants the PostgreSQL adapters must honor.
"""

from .repositories import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryEmbeddingRunRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryMindThreadRepository,
    InMemoryRetrievalSessionRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

__all__ = [
    "InMemoryContributionRepository",
    "InMemoryContributionReviewRepository",
    "InMemoryEmbeddingRunRepository",
    "InMemoryIdentityDecisionRepository",
    "InMemoryMindThreadRepository",
    "InMemoryRetrievalSessionRepository",
    "InMemorySemanticDocumentRepository",
    "InMemorySemanticSearch",
    "InMemorySourceRepository",
    "InMemoryWorldGraphRepository",
]
