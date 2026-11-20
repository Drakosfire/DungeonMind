"""Explicitly requested legacy PostgreSQL aggregate wiring."""

from ...application.publication_admission import PublicationAdmissionRegistry
from .database import PostgresDatabase


class PostgresRepositoryBundle:
    """Optional convenience wiring; individual repositories stay explicit."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        admission_registry: PublicationAdmissionRegistry | None = None,
    ) -> None:
        from . import (
            PostgresContributionRepository,
            PostgresContributionReviewRepository,
            PostgresEmbeddingRunRepository,
            PostgresExistingWorldAdoptionRepository,
            PostgresFinalizedReviewPublicationRepository,
            PostgresIdentityDecisionRepository,
            PostgresMindThreadRepository,
            PostgresPublicationAdmissionRepository,
            PostgresRetrievalSessionRepository,
            PostgresReviewedWorldInitializationRepository,
            PostgresSemanticDocumentRepository,
            PostgresSemanticSearch,
            PostgresSourceRepository,
            PostgresWorldGraphRepository,
            PostgresWorldIdentityReconciliationRepository,
        )

        self.database = database
        self.publication_admission = PostgresPublicationAdmissionRepository(database)
        self.world_graph = PostgresWorldGraphRepository(database)
        self.contributions = PostgresContributionRepository(database)
        self.contribution_reviews = PostgresContributionReviewRepository(database)
        self.finalized_review_publications = PostgresFinalizedReviewPublicationRepository(
            database, admission_registry=admission_registry
        )
        self.existing_world_adoptions = PostgresExistingWorldAdoptionRepository(database)
        self.reviewed_world_initializations = PostgresReviewedWorldInitializationRepository(
            database
        )
        self.identity_decisions = PostgresIdentityDecisionRepository(database)
        self.identity_reconciliation = PostgresWorldIdentityReconciliationRepository(database)
        self.sources = PostgresSourceRepository(database)
        self.retrieval_sessions = PostgresRetrievalSessionRepository(database)
        self.threads = PostgresMindThreadRepository(database)
        self.embedding_runs = PostgresEmbeddingRunRepository(database)
        self.semantic_documents = PostgresSemanticDocumentRepository(database)
        self.semantic_search = PostgresSemanticSearch(database)


# Keep the original public identity for reflection and pickle consumers.
PostgresRepositoryBundle.__module__ = "dungeonmind.infrastructure.postgres"
PostgresRepositoryBundle.__init__.__module__ = "dungeonmind.infrastructure.postgres"
