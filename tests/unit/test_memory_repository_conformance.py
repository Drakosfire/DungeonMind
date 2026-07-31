"""In-memory adapters must satisfy the shared repository contract cases."""

import pytest

from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryEmbeddingRunRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryMindThreadRepository,
    InMemoryRetrievalSessionRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.conformance.repository_contract_cases import CASES, RepositoryBundle


@pytest.mark.conformance
@pytest.mark.parametrize("case_name,case_fn", CASES, ids=[n for n, _ in CASES])
def test_memory_conformance(case_name: str, case_fn) -> None:
    del case_name  # used only in the parametrize id
    runs = InMemoryEmbeddingRunRepository()
    docs = InMemorySemanticDocumentRepository(runs)
    bundle = RepositoryBundle(
        world_graph=InMemoryWorldGraphRepository(),
        contributions=InMemoryContributionRepository(),
        identity=InMemoryIdentityDecisionRepository(),
        sources=InMemorySourceRepository(),
        sessions=InMemoryRetrievalSessionRepository(),
        threads=InMemoryMindThreadRepository(),
        runs=runs,
        documents=docs,
        search=InMemorySemanticSearch(docs, runs),
    )
    case_fn(bundle)
