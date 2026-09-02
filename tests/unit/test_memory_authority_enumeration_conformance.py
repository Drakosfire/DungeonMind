"""In-memory proofs for read-only authority enumeration repository ports."""

import pytest

from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.conformance.authority_enumeration_contract_cases import (
    CASES,
    EnumerationBundle,
)


@pytest.mark.conformance
@pytest.mark.parametrize("case_name,case_fn", CASES, ids=[name for name, _ in CASES])
def test_memory_authority_enumeration_conformance(case_name: str, case_fn) -> None:
    del case_name
    graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    contributions = InMemoryContributionRepository()
    identity = InMemoryIdentityDecisionRepository()
    bundle = EnumerationBundle(
        world_graph=graph,
        existing_world_adoptions=InMemoryExistingWorldAdoptionRepository(
            graph, sources, contributions, identity
        ),
        reviewed_world_initializations=InMemoryReviewedWorldInitializationRepository(
            graph, sources, contributions, identity
        ),
    )
    case_fn(bundle)
