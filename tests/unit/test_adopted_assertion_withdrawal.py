from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

import dungeonmind.infrastructure.memory.repositories as memory_repositories
from dungeonmind.application.adopted_assertion_withdrawal import (
    withdraw_adopted_assertion,
)
from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.contracts.adopted_assertion_withdrawal import (
    ADOPTED_ASSERTION_WITHDRAWAL_TOOL,
    AdoptedAssertionWithdrawalCommandV1,
    AdoptedAssertionWithdrawalCommandV2,
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


def _add_three_pc_commands(payload):
    """Synthetic shared-evidence witness; no campaign IDs or production content."""
    person = next(item for item in payload["objects"] if item["object_id"] == "obj:headmaster")
    target = next(
        item for item in payload["relationships"] if item["relationship_id"] == "rel:leads"
    )
    for suffix in ("alpha", "beta", "gamma"):
        pc = copy.deepcopy(person)
        pc["object_id"] = f"obj:pc-{suffix}"
        pc["label"] = f"Synthetic PC {suffix}"
        pc["assertion_metadata"]["assertion_id"] = f"asrt:pc-{suffix}-exists"
        payload["objects"].append(pc)
        edge = copy.deepcopy(target)
        edge.update(
            relationship_id=f"rel:pc-command-{suffix}",
            target_object_id=pc["object_id"],
            predicate="test:commands",
            target_aspect_assertion_id=None,
        )
        edge["assertion_metadata"]["assertion_id"] = f"asrt:pc-command-{suffix}"
        payload["relationships"].append(edge)


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


def _prepared(*, world_id: str = WORLD_ID, stores=None, version=1, repair=True):
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
            evidence["source_locator"] = None if version == 2 else "fixture://notes-a#span-17"
            evidence["can_highlight_span"] = True
    _add_three_pc_commands(graph_payload)
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
    if repair:
        _repair(raw, _intent(bundle), adoptions)
    head = graph.get_head(world_id)
    assert head is not None
    parent = graph.get_revision(world_id, head.head_revision_id)
    assert parent is not None
    target_evidence = next(
        item for item in parent.graph_payload["evidence_refs"] if item["evidence_ref_id"] == "ev:a"
    )
    command_type = (
        AdoptedAssertionWithdrawalCommandV2 if version == 2 else AdoptedAssertionWithdrawalCommandV1
    )
    command = command_type.model_validate(
        dict(
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
    )
    return graph, adoptions, command


def test_withdrawal_operation_id_is_globally_unique_across_worlds(
    monkeypatch: pytest.MonkeyPatch,
    withdrawal_version,
) -> None:
    stores = make_stores()
    graph, repository, first = _prepared(stores=stores, version=withdrawal_version)
    _same_graph, same_repository, second = _prepared(
        world_id="world:withdrawal-concurrency-other", stores=stores, version=withdrawal_version
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

    monkeypatch.setattr(memory_repositories, "materialize_withdrawal_payload", gated_materialize)
    repository._withdrawal_operation_lock = ObservedLock()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(repository.withdraw_adopted_assertion, first)
        assert first_inside_materialize.wait(timeout=5)
        second_future = pool.submit(repository.withdraw_adopted_assertion, second)
        assert second_waiting_on_global_lock.wait(timeout=5)
        assert not second_future.done()
        release_first.set()
        try:
            with pytest.raises((IdempotencyConflictError, ValidationError)):
                second_future.result(timeout=5)
        finally:
            release_first.set()
        receipt = first_future.result(timeout=5)

    assert receipt.world_id == first.world_id
    assert materialize_calls == 1
    assert list(repository._withdrawal_receipts) == [(first.world_id, first.operation_id)]
    assert graph.get_head(first.world_id).head_revision_id == receipt.published_revision_id
    assert graph.get_head(second.world_id).head_revision_id == second.expected_parent_revision_id


def test_withdrawal_omits_only_bound_relationship_and_exact_replay_is_idempotent(
    withdrawal_version,
) -> None:
    graph, repository, command = _prepared(version=withdrawal_version)
    before = graph.get_revision(command.world_id, command.expected_parent_revision_id)
    assert before is not None
    policy = _authorized_policy(
        world_id=command.world_id,
        revision_id=command.expected_parent_revision_id,
    )
    receipt = withdraw_adopted_assertion(command, capability_policy=policy, repository=repository)
    after = graph.get_revision(command.world_id, receipt.published_revision_id)
    assert after is not None
    expected = copy.deepcopy(before.graph_payload)
    expected["relationships"] = [
        item
        for item in expected["relationships"]
        if item["relationship_id"] != command.relationship_id
    ]
    assert after.graph_payload == expected
    assert {
        edge["relationship_id"]
        for edge in after.graph_payload["relationships"]
        if edge["predicate"] == "test:commands"
    } == {f"rel:pc-command-{suffix}" for suffix in ("alpha", "beta", "gamma")}
    assert after.graph_payload["evidence_refs"] == before.graph_payload["evidence_refs"]
    assert graph.get_revision(command.world_id, command.expected_parent_revision_id) == before
    revision_count = len(graph._revisions)
    replay = withdraw_adopted_assertion(command, capability_policy=policy, repository=repository)
    assert replay == receipt
    assert len(graph._revisions) == revision_count

    other_type = (
        AdoptedAssertionWithdrawalCommandV1
        if withdrawal_version == 2
        else AdoptedAssertionWithdrawalCommandV2
    )
    other_payload = command.model_dump(mode="json")
    other_payload["schema_version"] = other_type.model_fields["schema_version"].default
    other_payload["source_locator"] = "fixture://other-version" if withdrawal_version == 2 else None
    with pytest.raises(IdempotencyConflictError):
        repository.withdraw_adopted_assertion(other_type.model_validate(other_payload))
    assert len(graph._revisions) == revision_count

    conflicting = command.model_copy(update={"actor": "reviewer:changed"})
    with pytest.raises(IdempotencyConflictError):
        withdraw_adopted_assertion(
            conflicting,
            capability_policy=policy,
            repository=repository,
        )
    assert len(graph._revisions) == revision_count


def test_withdrawal_requires_exact_commit_scope_and_stale_parent_does_not_mutate(
    withdrawal_version,
) -> None:
    graph, repository, command = _prepared(version=withdrawal_version)
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
def test_repository_rejects_forged_target_and_source_bindings_before_mutation(
    changes, withdrawal_version
) -> None:
    graph, repository, command = _prepared(version=withdrawal_version)
    before_revisions = len(graph._revisions)
    forged = command.model_copy(update=changes)
    with pytest.raises((PersistenceIntegrityError, ValidationError)):
        repository.withdraw_adopted_assertion(forged)
    assert len(graph._revisions) == before_revisions
    assert repository._withdrawal_receipts == {}


@pytest.fixture(params=[1, 2])
def withdrawal_version(request):
    return request.param


@pytest.mark.parametrize("version,locator", [(1, None), (2, "fixture://forged")])
def test_locator_contracts_are_disjoint_and_v2_null_must_be_explicit(version, locator):
    _graph, _repository, command = _prepared(version=version)
    payload = command.model_dump(mode="json")
    payload["source_locator"] = locator
    with pytest.raises(ValidationError):
        type(command).model_validate(payload)
    payload.pop("source_locator")
    with pytest.raises(ValidationError):
        type(command).model_validate(payload)


def test_v2_cannot_withdraw_locator_bearing_adopted_evidence():
    graph, repository, v1 = _prepared(version=1)
    payload = v1.model_dump(mode="json")
    payload.update(schema_version="dm_adopted_assertion_withdrawal_command_v2", source_locator=None)
    command = AdoptedAssertionWithdrawalCommandV2.model_validate(payload)
    before = copy.deepcopy((graph._revisions, graph._heads))
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(command)
    assert (graph._revisions, graph._heads) == before
    assert repository._withdrawal_receipts == {}


def test_receipt_locator_contract_is_required_and_version_bound(withdrawal_version):
    _graph, repository, command = _prepared(version=withdrawal_version)
    receipt = repository.withdraw_adopted_assertion(command)
    payload = receipt.model_dump(mode="json")
    payload["source_locator"] = None if withdrawal_version == 1 else "fixture://forged"
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)
    payload.pop("source_locator")
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)


def test_withdrawal_requires_durable_v4_membership(withdrawal_version):
    graph, repository, command = _prepared(version=withdrawal_version, repair=False)
    before = copy.deepcopy(graph._revisions)
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(command)
    assert graph._revisions == before
    assert repository._withdrawal_receipts == {}


@pytest.mark.parametrize("stage", ["withdrawal_graph", "withdrawal_receipt"])
def test_memory_withdrawal_rolls_back_at_each_mutation_boundary(stage, withdrawal_version):
    graph, repository, command = _prepared(version=withdrawal_version)
    before = copy.deepcopy((graph._revisions, graph._heads))

    def fail(observed):
        if observed == stage:
            raise RuntimeError("injected withdrawal failure")

    repository._failure_hook = fail
    with pytest.raises(RuntimeError, match="injected withdrawal failure"):
        repository.withdraw_adopted_assertion(command)
    assert (graph._revisions, graph._heads) == before
    assert repository._withdrawal_receipts == {}


def _drift_parent(payload, command, drift):
    target = next(
        item
        for item in payload["relationships"]
        if item["relationship_id"] == command.relationship_id
    )
    evidence = next(
        item
        for item in payload["evidence_refs"]
        if item["evidence_ref_id"] == command.evidence_ref_id
    )
    if drift == "locator":
        evidence["source_locator"] = "fixture://must-not-infer"
    elif drift == "span":
        evidence["source_span_ref_id"] = None
    elif drift == "revision":
        evidence["source_revision_id"] = "srcrev:forged"
    elif drift == "profile":
        payload["semantic_profile"]["descriptor_sha256"] = "f" * 64
    elif drift == "duplicate":
        payload["relationships"].append(copy.deepcopy(target))
    elif drift == "assertion":
        payload["objects"][0]["assertion_metadata"]["assertion_id"] = command.assertion_id
    else:
        target["assertion_metadata"]["evidence_ref_ids"].append("ev:b")
    return payload


@pytest.mark.parametrize(
    "drift", ["locator", "span", "revision", "profile", "duplicate", "assertion", "evidence"]
)
def test_v2_rejects_parent_drift_without_mutation(drift):
    from dungeonmind.contracts.graph import PublishRevisionCommand

    graph, repository, command = _prepared(version=2)
    parent = graph.get_revision(command.world_id, command.expected_parent_revision_id)
    payload = _drift_parent(copy.deepcopy(parent.graph_payload), command, drift)
    changed = graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            operation_ids=[f"test-drift:{drift}"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=NOW,
        )
    )
    changed_command = command.model_copy(
        update={
            "expected_parent_revision_id": changed.revision_id,
            "parent_payload_sha256": canonical_sha256(payload),
        }
    )
    before = copy.deepcopy((graph._revisions, graph._heads))
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(changed_command)
    assert (graph._revisions, graph._heads) == before
    assert repository._withdrawal_receipts == {}
