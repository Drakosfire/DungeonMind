"""Application and in-memory proofs for reviewed first-world initialization."""

from __future__ import annotations

import pytest

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.reviewed_world_initialization import (
    initialize_reviewed_world,
    reviewed_world_initialization_command_sha256,
)
from dungeonmind.contracts.existing_world_adoption import (
    existing_world_adoption_bundle_canonical_bytes,
)
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    ReviewedWorldInitializationOutcomeUnknownError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_existing_world_adoption import (
    graph_reader as adoption_graph_reader,
)
from tests.unit.test_existing_world_adoption import (
    make_isolated_bundle,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    INIT_ID,
    NOW,
    REV,
    WORLD_ID,
    graph_reader,
    make_accepted_edge_identity_command,
    make_accepted_node_non_create_new_command,
    make_artifact_only_command,
    make_command,
    make_created_new_edge_command,
    make_revision_only_assertion_command,
    make_unreferenced_extra_artifact_command,
    make_unreferenced_extra_revision_command,
)

OTHER_WORLD = "world:reviewed-init-other"


def make_stores(*, failure_hook=None, wire_reciprocal: bool = False):
    graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    contributions = InMemoryContributionRepository()
    identity = InMemoryIdentityDecisionRepository()
    inits = InMemoryReviewedWorldInitializationRepository(
        graph,
        sources,
        contributions,
        identity,
        failure_hook=failure_hook,
    )
    adoptions = InMemoryExistingWorldAdoptionRepository(
        graph,
        sources,
        contributions,
        identity,
    )
    if wire_reciprocal:
        inits._adoption_lookup = lambda world_id: world_id in adoptions._receipts_by_world
        adoptions._reviewed_initialization_lookup = (
            lambda world_id: world_id in inits._receipts_by_world
        )
    return graph, sources, contributions, identity, inits, adoptions


def _initialize(inits, command=None, *, initialized_at=NOW):
    resolved = command or make_command()
    if initialized_at != NOW:
        resolved = resolved.model_copy(update={"requested_initialized_at": initialized_at})
    return initialize_reviewed_world(
        resolved,
        initialization_repository=inits,
        graph_reader=graph_reader(),
    )


def _assert_zero_mutation(
    graph, sources, contributions, inits, *, world_id: str = WORLD_ID
) -> None:
    assert graph.get_head(world_id) is None
    assert graph._revisions == {}
    assert sources._artifacts == {}
    assert sources._revisions == {}
    assert contributions._items == {}
    assert inits._receipts_by_world == {}
    assert inits._receipts_by_initialization == {}


def _assert_initialized_edge(graph, receipt) -> None:
    assert "asrt:leads" in receipt.accepted_assertion_ids
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    assert stored.revision.parent_revision_id is None
    rels = stored.graph_payload["relationships"]
    assert {item["relationship_id"] for item in rels} == {"rel:leads"}
    for record in stored.graph_payload["evidence_refs"]:
        assert record["source_revision_id"] == REV


def test_command_digest_is_deterministic() -> None:
    first = reviewed_world_initialization_command_sha256(make_command())
    second = reviewed_world_initialization_command_sha256(make_command())
    assert first == second
    changed = reviewed_world_initialization_command_sha256(
        make_command(initialization_id="init:other")
    )
    assert changed != first


def test_in_memory_exact_retry_returns_same_receipt_and_revision() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    first = _initialize(inits)
    before_artifacts = len(sources._artifacts)
    before_revisions = len(graph._revisions)
    before_contributions = len(contributions._items)
    replayed = _initialize(inits)
    assert replayed == first
    assert replayed.initialization_id == INIT_ID
    assert replayed.published_graph_schema == "dm_union_graph_v6"
    head = graph.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == first.published_revision_id
    stored = graph.get_revision(WORLD_ID, first.published_revision_id)
    assert stored is not None
    assert stored.revision.parent_revision_id is None
    assert len(sources._artifacts) == before_artifacts
    assert len(graph._revisions) == before_revisions
    assert len(contributions._items) == before_contributions
    assert len(inits._receipts_by_world) == 1


def test_same_id_different_command_sha256_conflicts_and_does_not_return_receipt() -> None:
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    stored = _initialize(inits)
    conflicting = make_command(actor="gm:other-reviewer")
    with pytest.raises(IdempotencyConflictError) as exc:
        result = _initialize(inits, conflicting)
        raise AssertionError(f"returned stored receipt as success: {result}")
    assert stored.initialization_id == INIT_ID
    assert "command_sha256" in exc.value.details
    assert inits.get_for_world(WORLD_ID) == stored


def test_different_initialization_id_conflicts_with_zero_mutation() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    stored = _initialize(inits)
    artifact_count = len(sources._artifacts)
    revision_count = len(graph._revisions)
    contribution_count = len(contributions._items)
    with pytest.raises(IdempotencyConflictError):
        _initialize(inits, make_command(initialization_id="init:second"))
    assert inits.get_for_world(WORLD_ID) == stored
    assert len(sources._artifacts) == artifact_count
    assert len(graph._revisions) == revision_count
    assert len(contributions._items) == contribution_count


def test_initialization_id_reused_across_worlds_conflicts() -> None:
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    first = _initialize(inits)
    other = make_command(world_id=OTHER_WORLD)
    # Same initialization_id, different world.
    other = other.model_copy(update={"initialization_id": INIT_ID})
    other = other.model_copy(
        update={
            "reviewed_contribution": other.reviewed_contribution.model_copy(
                update={"world_id": OTHER_WORLD}
            )
        }
    )
    with pytest.raises(IdempotencyConflictError) as exc:
        _initialize(inits, other)
    assert INIT_ID in str(exc.value)
    assert inits.get_for_world(WORLD_ID) == first
    assert inits.get_for_world(OTHER_WORLD) is None


def _adoption_bytes():
    return existing_world_adoption_bundle_canonical_bytes(
        make_isolated_bundle(
            world_id=WORLD_ID,
            adoption_id="adopt:reviewed-init-reciprocal",
            token="init-reciprocal",
        )
    )


def test_adoption_rejects_world_with_init_receipt() -> None:
    _graph, _sources, _contributions, _identity, inits, adoptions = make_stores(
        wire_reciprocal=True
    )
    _initialize(inits)
    with pytest.raises(PersistenceIntegrityError) as exc:
        adopt_existing_world(
            _adoption_bytes(),
            adopted_at=NOW,
            adoption_repository=adoptions,
            graph_reader=adoption_graph_reader(),
        )
    assert exc.value.details["reason"] == "non_pristine_target"
    assert exc.value.details["family"] == "reviewed_world_initialization"


def test_init_rejects_world_with_adoption_receipt() -> None:
    _graph, _sources, _contributions, _identity, inits, adoptions = make_stores(
        wire_reciprocal=True
    )
    adopt_existing_world(
        _adoption_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=adoption_graph_reader(),
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(inits)
    assert exc.value.details["reason"] == "non_pristine_target"
    assert exc.value.details["family"] == "existing_world_adoption"


def test_lost_response_retry_returns_same_receipt() -> None:
    _graph, _sources, _contributions, _identity, inner, _adoptions = make_stores()

    class _CommitThenUnavailable:
        def __init__(self) -> None:
            self.initialize_calls = 0
            self.recovery_probes = 0

        def initialize(self, command, **kwargs):
            self.initialize_calls += 1
            inner.initialize(command, **kwargs)
            raise PersistenceUnavailableError("response lost")

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            receipt = inner.get_for_world(world_id)
            if self.initialize_calls:
                self.recovery_probes += 1
            return receipt

    wrapper = _CommitThenUnavailable()
    receipt = initialize_reviewed_world(
        make_command(),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert wrapper.initialize_calls == 1
    assert wrapper.recovery_probes == 1
    assert receipt.world_id == WORLD_ID
    replayed = initialize_reviewed_world(
        make_command(),
        initialization_repository=inner,
        graph_reader=graph_reader(),
    )
    assert replayed == receipt


def test_unknown_outcome_when_recovery_unavailable() -> None:
    class _Unavailable:
        def __init__(self) -> None:
            self.gets = 0

        def get_for_world(self, world_id: str):
            self.gets += 1
            if self.gets == 1:
                return None
            raise PersistenceUnavailableError("probe failed")

        def initialize(self, command, **kwargs):
            raise PersistenceUnavailableError("mutate failed")

        def get(self, world_id: str, initialization_id: str):
            return None

    with pytest.raises(ReviewedWorldInitializationOutcomeUnknownError) as exc:
        initialize_reviewed_world(
            make_command(),
            initialization_repository=_Unavailable(),  # type: ignore[arg-type]
            graph_reader=graph_reader(),
        )
    assert exc.value.details["retry_safe"] is True
    assert exc.value.details["world_id"] == WORLD_ID
    assert exc.value.details["initialization_id"] == INIT_ID


def test_failure_hook_before_commit_leaves_zero_partial_state() -> None:
    def hook(stage: str) -> None:
        if stage == "graph":
            raise RuntimeError("injected graph abort")

    graph, sources, contributions, _identity, inits, _adoptions = make_stores(
        failure_hook=hook
    )
    with pytest.raises(ReviewedWorldInitializationOutcomeUnknownError):
        _initialize(inits)
    assert graph.get_head(WORLD_ID) is None
    assert graph._revisions == {}
    assert sources._artifacts == {}
    assert contributions._items == {}
    assert inits._receipts_by_world == {}


def test_initialize_accepts_neutral_edge_identity_and_persists_relationship() -> None:
    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(inits)
    _assert_initialized_edge(graph, receipt)


def test_initialize_accepts_created_new_edge_identity() -> None:
    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(inits, make_created_new_edge_command())
    _assert_initialized_edge(graph, receipt)


def test_initialize_rejects_non_create_new_node_identity_with_zero_mutation() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(inits, make_accepted_node_non_create_new_command())
    assert exc.value.details["reason"] == "accepted_identity_not_create_new"
    _assert_zero_mutation(graph, sources, contributions, inits)


def test_initialize_rejects_unsupported_edge_identity_with_zero_mutation() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(
            inits, make_accepted_edge_identity_command(IdentityOutcome.AMBIGUOUS)
        )
    assert exc.value.details["reason"] == "accepted_edge_identity_unsupported"
    _assert_zero_mutation(graph, sources, contributions, inits)


def test_initialize_artifact_only_provenance_persists_current_revision_evidence() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(inits, make_artifact_only_command())
    _assert_initialized_edge(graph, receipt)
    assert len(sources._artifacts) == 1
    assert len(sources._revisions) == 1
    assert len(contributions._items) == 1
    assert len(inits._receipts_by_world) == 1


def test_initialize_revision_only_assertion_persists() -> None:
    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(inits, make_revision_only_assertion_command())
    _assert_initialized_edge(graph, receipt)


def test_initialize_unreferenced_extra_artifact_zero_mutation() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(inits, make_unreferenced_extra_artifact_command())
    assert exc.value.details["reason"] == "unreferenced_source_artifact"
    _assert_zero_mutation(graph, sources, contributions, inits)


def test_initialize_unreferenced_extra_revision_zero_mutation() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(inits, make_unreferenced_extra_revision_command())
    assert exc.value.details["reason"] == "unreferenced_source_revision"
    _assert_zero_mutation(graph, sources, contributions, inits)
