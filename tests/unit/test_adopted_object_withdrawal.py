"""Governed object withdrawal reuses the append-only adoption authority."""

import copy

import pytest
from pydantic import ValidationError

import tests.unit.test_adopted_assertion_withdrawal as existing
from dungeonmind.application.adopted_assertion_withdrawal import withdraw_adopted_assertion
from dungeonmind.contracts.adopted_assertion_withdrawal import AdoptedAssertionWithdrawalCommandV3
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import IdempotencyConflictError, PersistenceIntegrityError

OBJECT_ID = "obj:unsupported-orphan"
ASSERTION_ID = "asrt:unsupported-orphan-exists"


def orphan_bundle(bundle):
    graph = copy.deepcopy(bundle.graph_payload)
    obj = copy.deepcopy(graph["objects"][0])
    obj.update(
        object_id=OBJECT_ID,
        label="Unsupported category duplicate",
        aliases=[],
        summary=None,
        properties=[],
        aspects=[],
    )
    obj["assertion_metadata"]["assertion_id"] = ASSERTION_ID
    obj["assertion_metadata"]["evidence_ref_ids"] = ["ev:a"]
    graph["objects"].append(obj)
    return bundle.model_copy(update={"graph_payload": graph})


def object_command(command):
    data = command.model_dump(mode="json")
    data.pop("schema_version")
    data.update(
        relationship_id=None,
        predicate=None,
        object_object_id=None,
        subject_object_id=OBJECT_ID,
        assertion_id=ASSERTION_ID,
    )
    return AdoptedAssertionWithdrawalCommandV3.model_validate(data)


def prepared(monkeypatch):
    original = existing._repairable_bundle
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: orphan_bundle(original()))
    graph, repository, command = existing._prepared(version=2)
    return graph, repository, object_command(command)


def test_object_withdrawal_preserves_every_other_record_and_exact_replay(monkeypatch):
    graph, repository, command = prepared(monkeypatch)
    before = graph.get_revision(command.world_id, command.expected_parent_revision_id)
    receipt = withdraw_adopted_assertion(
        command,
        capability_policy=existing._authorized_policy(
            world_id=command.world_id, revision_id=command.expected_parent_revision_id
        ),
        repository=repository,
    )
    after = graph.get_revision(command.world_id, receipt.published_revision_id)
    expected = copy.deepcopy(before.graph_payload)
    expected["objects"] = [o for o in expected["objects"] if o["object_id"] != OBJECT_ID]
    assert after.graph_payload == expected
    assert graph.get_revision(command.world_id, command.expected_parent_revision_id) == before
    assert repository.withdraw_adopted_assertion(command) == receipt
    with pytest.raises(IdempotencyConflictError):
        repository.withdraw_adopted_assertion(
            command.model_copy(update={"actor": "other-reviewer"})
        )


def test_object_withdrawal_refuses_incident_relationships_without_mutation(monkeypatch):
    graph, repository, command = prepared(monkeypatch)
    data = command.model_dump(mode="json")
    data.update(subject_object_id="obj:headmaster", assertion_id="asrt:headmaster-exists")
    request = AdoptedAssertionWithdrawalCommandV3.model_validate(data)
    with pytest.raises(PersistenceIntegrityError, match="incident relationships"):
        repository.withdraw_adopted_assertion(request)
    assert graph.get_head(command.world_id).head_revision_id == command.expected_parent_revision_id
    assert not repository._withdrawal_receipts


@pytest.mark.parametrize(
    "changes",
    [
        {"source_span_ref_id": "different-span"},
        {"evidence_ref_id": "different-evidence"},
        {"assertion_id": "different-assertion"},
        {"parent_payload_sha256": "0" * 64},
    ],
)
def test_object_withdrawal_refuses_forged_binding_without_mutation(monkeypatch, changes):
    graph, repository, command = prepared(monkeypatch)
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(command.model_copy(update=changes))
    assert graph.get_head(command.world_id).head_revision_id == command.expected_parent_revision_id
    assert not repository._withdrawal_receipts


def test_object_withdrawal_rolls_back_receipt_failure(monkeypatch):
    graph, repository, command = prepared(monkeypatch)
    before = canonical_sha256(
        graph.get_revision(command.world_id, command.expected_parent_revision_id).graph_payload
    )

    def fail(phase):
        if phase == "withdrawal_receipt":
            raise RuntimeError("injected receipt failure")

    repository._failure_hook = fail
    with pytest.raises(RuntimeError, match="injected"):
        repository.withdraw_adopted_assertion(command)
    assert graph.get_head(command.world_id).head_revision_id == command.expected_parent_revision_id
    assert (
        canonical_sha256(
            graph.get_revision(command.world_id, command.expected_parent_revision_id).graph_payload
        )
        == before
    )
    assert not repository._withdrawal_receipts


@pytest.mark.parametrize("field", ["relationship_id", "predicate", "object_object_id"])
def test_object_command_cannot_smuggle_relationship_target(monkeypatch, field):
    _, _, command = prepared(monkeypatch)
    data = command.model_dump(mode="json")
    data[field] = "not-null"
    with pytest.raises(ValidationError):
        AdoptedAssertionWithdrawalCommandV3.model_validate(data)
