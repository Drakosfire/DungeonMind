from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import dungeonmind.infrastructure.memory.repositories as memory_repositories
from dungeonmind.application.adopted_assertion_withdrawal import (
    withdraw_adopted_assertion,
)
from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.contracts.adopted_assertion_withdrawal import (
    ADOPTED_ASSERTION_WITHDRAWAL_TOOL,
    AdoptedAssertionWithdrawalCommandV1,
)
from dungeonmind.contracts.capability import (
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from tests.unit.test_existing_world_adoption import (
    NOW,
    WORLD_ID,
    graph_reader,
    make_stores,
    v2_bundle_bytes,
)
from tests.unit.test_existing_world_adoption_repair import (
    _intent,
    _repair,
    _repairable_bundle,
)


def _authorized_policy(*, world_id: str, revision_id: str) -> CapabilityPolicy:
    return CapabilityPolicy(
        policy_id="policy:test-withdrawal",
        graph_scope=GraphScope(
            world_id=world_id,
            admissibility=Admissibility.GM,
            revision_pin=revision_id,
        ),
        enabled_tools=[ADOPTED_ASSERTION_WITHDRAWAL_TOOL],
        tool_rules=[
            ToolCapabilityRule(
                tool_name=ADOPTED_ASSERTION_WITHDRAWAL_TOOL,
                category=CapabilityCategory.CONFIRM_COMMIT,
                allowed_effects=[CapabilityEffect.COMMIT],
            )
        ],
    )


def _prepared(*, world_id: str = WORLD_ID, stores=None):
    bundle = _repairable_bundle()
    if world_id != bundle.world_id:
        adoption_id = f"{bundle.adoption_id}:{world_id}"
        id_map = {
            bundle.world_id: world_id,
            bundle.adoption_id: adoption_id,
        }
        for items, field in (
            (bundle.source_artifacts, "source_artifact_id"),
            (bundle.source_revisions, "source_revision_id"),
            (bundle.contributions, "contribution_id"),
            (bundle.identity_decisions, "decision_id"),
        ):
            for item in items:
                identifier = getattr(item, field)
                id_map[identifier] = f"{identifier}:{world_id}"

        def rewrite(value):
            if isinstance(value, dict):
                return {key: rewrite(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rewrite(item) for item in value]
            if isinstance(value, str):
                return id_map.get(value, value)
            return value

        def rewrite_model(model):
            return type(model).model_validate(rewrite(model.model_dump(mode="json")))

        bundle = bundle.model_copy(
            update={
                "world_id": world_id,
                "adoption_id": adoption_id,
                "graph_payload": rewrite(bundle.graph_payload),
                "source_artifacts": [rewrite_model(item) for item in bundle.source_artifacts],
                "source_revisions": [rewrite_model(item) for item in bundle.source_revisions],
                "contributions": [rewrite_model(item) for item in bundle.contributions],
                "identity_decisions": [rewrite_model(item) for item in bundle.identity_decisions],
            }
        )
    graph_payload = copy.deepcopy(bundle.graph_payload)
    for evidence in graph_payload["evidence_refs"]:
        if evidence["evidence_ref_id"] == "ev:a":
            evidence["source_span_ref_id"] = "span:adopted-a"
            evidence["source_locator"] = "fixture://notes-a#span-17"
            evidence["can_highlight_span"] = True
    bundle = bundle.model_copy(update={"graph_payload": graph_payload})
    raw = v2_bundle_bytes(bundle)
    if stores is None:
        stores = make_stores()
    graph, _sources, _contributions, _identity, adoptions = stores
    adoption = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    _repair(raw, _intent(bundle), adoptions)
    head = graph.get_head(world_id)
    assert head is not None
    parent = graph.get_revision(world_id, head.head_revision_id)
    assert parent is not None
    target_evidence = next(
        item for item in parent.graph_payload["evidence_refs"]
        if item["evidence_ref_id"] == "ev:a"
    )
    command = AdoptedAssertionWithdrawalCommandV1(
        operation_id="withdrawal:test-1",
        world_id=world_id,
        adoption_id=adoption.adoption_id,
        expected_parent_revision_id=head.head_revision_id,
        relationship_id="rel:leads",
        assertion_id="asrt:leads",
        subject_object_id="obj:headmaster",
        predicate="test:leads",
        object_object_id="obj:college",
        evidence_ref_id="ev:a",
        source_artifact_id=target_evidence["source_artifact_id"],
        source_revision_id=target_evidence["source_revision_id"],
        source_span_ref_id=target_evidence["source_span_ref_id"],
        source_locator=target_evidence["source_locator"],
        parent_payload_sha256=canonical_sha256(parent.graph_payload),
        actor="reviewer:test",
        requested_at=NOW,
    )
    return graph, adoptions, command


def test_withdrawal_operation_id_is_globally_unique_across_worlds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stores = make_stores()
    graph, repository, first = _prepared(stores=stores)
    _same_graph, same_repository, second = _prepared(
        world_id="world:withdrawal-concurrency-other", stores=stores
    )
    assert repository is same_repository
    assert first.operation_id == second.operation_id
    assert first.world_id != second.world_id

    original_materialize = memory_repositories.materialize_withdrawal_payload
    first_inside_materialize = threading.Event()
    release_first = threading.Event()
    second_waiting_on_global_lock = threading.Event()
    call_count_lock = threading.Lock()
    materialize_calls = 0

    class ObservedLock:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._guard = threading.Lock()
            self._entrants = 0

        def __enter__(self):
            with self._guard:
                self._entrants += 1
                if self._entrants == 2:
                    second_waiting_on_global_lock.set()
            self._lock.acquire()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self._lock.release()
            return False

    def gated_materialize(*args, **kwargs):
        nonlocal materialize_calls
        with call_count_lock:
            materialize_calls += 1
            call_number = materialize_calls
        if call_number == 1:
            first_inside_materialize.set()
            assert release_first.wait(timeout=5)
        return original_materialize(*args, **kwargs)

    monkeypatch.setattr(
        memory_repositories, "materialize_withdrawal_payload", gated_materialize
    )
    repository._withdrawal_operation_lock = ObservedLock()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(repository.withdraw_adopted_assertion, first)
        assert first_inside_materialize.wait(timeout=5)
        second_future = pool.submit(repository.withdraw_adopted_assertion, second)
        assert second_waiting_on_global_lock.wait(timeout=5)
        assert not second_future.done()
        release_first.set()
        try:
            with pytest.raises(IdempotencyConflictError):
                second_future.result(timeout=5)
        finally:
            release_first.set()
        receipt = first_future.result(timeout=5)

    assert receipt.world_id == first.world_id
    assert materialize_calls == 1
    assert list(repository._withdrawal_receipts) == [(first.world_id, first.operation_id)]
    assert graph.get_head(first.world_id).head_revision_id == receipt.published_revision_id
    assert graph.get_head(second.world_id).head_revision_id == second.expected_parent_revision_id


def test_withdrawal_omits_only_bound_relationship_and_exact_replay_is_idempotent() -> None:
    graph, repository, command = _prepared()
    before = graph.get_revision(command.world_id, command.expected_parent_revision_id)
    assert before is not None
    policy = _authorized_policy(
        world_id=command.world_id,
        revision_id=command.expected_parent_revision_id,
    )
    receipt = withdraw_adopted_assertion(
        command, capability_policy=policy, repository=repository
    )
    after = graph.get_revision(command.world_id, receipt.published_revision_id)
    assert after is not None
    expected = copy.deepcopy(before.graph_payload)
    expected["relationships"] = [
        item for item in expected["relationships"]
        if item["relationship_id"] != command.relationship_id
    ]
    assert after.graph_payload == expected
    assert after.graph_payload["evidence_refs"] == before.graph_payload["evidence_refs"]
    assert graph.get_revision(command.world_id, command.expected_parent_revision_id) == before
    revision_count = len(graph._revisions)
    replay = withdraw_adopted_assertion(
        command, capability_policy=policy, repository=repository
    )
    assert replay == receipt
    assert len(graph._revisions) == revision_count

    conflicting = command.model_copy(update={"source_locator": "fixture://forged"})
    with pytest.raises(IdempotencyConflictError):
        withdraw_adopted_assertion(
            conflicting,
            capability_policy=policy,
            repository=repository,
        )
    assert len(graph._revisions) == revision_count


def test_withdrawal_requires_exact_commit_scope_and_stale_parent_does_not_mutate() -> None:
    graph, repository, command = _prepared()
    before_revisions = len(graph._revisions)
    denied = _authorized_policy(world_id=command.world_id, revision_id="rev:wrong")
    with pytest.raises(CapabilityDeniedError):
        withdraw_adopted_assertion(command, capability_policy=denied, repository=repository)
    assert len(graph._revisions) == before_revisions

    stale = command.model_copy(update={"expected_parent_revision_id": "rev:stale"})
    with pytest.raises(StaleParentRevisionError):
        repository.withdraw_adopted_assertion(stale)
    assert len(graph._revisions) == before_revisions


@pytest.mark.parametrize(
    "changes",
    [
        {"predicate": "test:forged"},
        {"source_span_ref_id": "span:forged"},
        {"source_artifact_id": "src:not-adopted"},
    ],
)
def test_repository_rejects_forged_target_and_source_bindings_before_mutation(changes) -> None:
    graph, repository, command = _prepared()
    before_revisions = len(graph._revisions)
    forged = command.model_copy(update=changes)
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(forged)
    assert len(graph._revisions) == before_revisions
    assert repository._withdrawal_receipts == {}
