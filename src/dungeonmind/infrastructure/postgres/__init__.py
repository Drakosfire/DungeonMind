"""PostgreSQL adapters for DungeonMind application ports.

Importing this package requires the ``postgres`` extra
(``uv sync --extra postgres``). Core ``dungeonmind`` imports never load this
package.
"""

from .database import PostgresDatabase
from .graph import PostgresWorldGraphRepository
from .records import (
    PostgresContributionRepository,
    PostgresIdentityDecisionRepository,
    PostgresRetrievalSessionRepository,
    PostgresSourceRepository,
)
from .semantic import (
    PostgresEmbeddingRunRepository,
    PostgresSemanticDocumentRepository,
    PostgresSemanticSearch,
)
from .threads import PostgresMindThreadRepository

__all__ = [
    "PostgresContributionRepository",
    "PostgresDatabase",
    "PostgresEmbeddingRunRepository",
    "PostgresIdentityDecisionRepository",
    "PostgresMindThreadRepository",
    "PostgresRetrievalSessionRepository",
    "PostgresSemanticDocumentRepository",
    "PostgresSemanticSearch",
    "PostgresSourceRepository",
    "PostgresWorldGraphRepository",
]


class PostgresRepositoryBundle:
    """Optional convenience wiring; individual repositories stay explicit."""

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database
        self.world_graph = PostgresWorldGraphRepository(database)
        self.contributions = PostgresContributionRepository(database)
        self.identity_decisions = PostgresIdentityDecisionRepository(database)
        self.sources = PostgresSourceRepository(database)
        self.retrieval_sessions = PostgresRetrievalSessionRepository(database)
        self.threads = PostgresMindThreadRepository(database)
        self.embedding_runs = PostgresEmbeddingRunRepository(database)
        self.semantic_documents = PostgresSemanticDocumentRepository(database)
        self.semantic_search = PostgresSemanticSearch(database)
