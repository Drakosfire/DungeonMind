from __future__ import annotations

import copy

import pytest

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
    ART_A,
    NOW,
    REV_A,
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


def _prepared():
    bundle = _repairable_bundle()
    graph_payload = copy.deepcopy(bundle.graph_payload)
    for evidence in graph_payload["evidence_refs"]:
        if evidence["evidence_ref_id"] == "ev:a":
            evidence["source_span_ref_id"] = "span:adopted-a"
            evidence["source_locator"] = "fixture://notes-a#span-17"
            evidence["can_highlight_span"] = True
    bundle = bundle.model_copy(update={"graph_payload": graph_payload})
    raw = v2_bundle_bytes(bundle)
    graph, _sources, _contributions, _identity, adoptions = make_stores()
    adoption = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    _repair(raw, _intent(bundle), adoptions)
    head = graph.get_head(WORLD_ID)
    assert head is not None
    parent = graph.get_revision(WORLD_ID, head.head_revision_id)
    assert parent is not None
    command = AdoptedAssertionWithdrawalCommandV1(
        operation_id="withdrawal:test-1",
        world_id=WORLD_ID,
        adoption_id=adoption.adoption_id,
        expected_parent_revision_id=head.head_revision_id,
        relationship_id="rel:leads",
        assertion_id="asrt:leads",
        subject_object_id="obj:headmaster",
        predicate="test:leads",
        object_object_id="obj:college",
        evidence_ref_id="ev:a",
        source_artifact_id=ART_A,
        source_revision_id=REV_A,
        source_span_ref_id="span:adopted-a",
        source_locator="fixture://notes-a#span-17",
        parent_payload_sha256=canonical_sha256(parent.graph_payload),
        actor="reviewer:test",
        requested_at=NOW,
    )
    return graph, adoptions, command


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
