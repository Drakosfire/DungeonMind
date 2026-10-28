"""A withdrawal proves every bound source, never a selected subset."""

import copy

import pytest
from pydantic import ValidationError

import tests.unit.test_adopted_assertion_withdrawal as existing
from dungeonmind.contracts.adopted_assertion_withdrawal import AdoptedAssertionWithdrawalCommandV4
from dungeonmind.domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from tests.unit.test_adopted_object_withdrawal import OBJECT_ID, object_command, orphan_bundle

FIELDS = (
    "evidence_ref_id",
    "source_artifact_id",
    "source_revision_id",
    "source_span_ref_id",
    "source_locator",
)


def complete_bundle(bundle):
    bundle = orphan_bundle(bundle)
    graph = copy.deepcopy(bundle.graph_payload)
    obj = next(o for o in graph["objects"] if o["object_id"] == OBJECT_ID)
    obj["assertion_metadata"]["evidence_ref_ids"] = ["ev:a", "ev:b", "ev:c"]
    second = next(e for e in graph["evidence_refs"] if e["evidence_ref_id"] == "ev:b")
    second.update(source_span_ref_id="span:adopted-b", source_locator="fixture://notes-b#span")
    third = copy.deepcopy(second)
    third.update(evidence_ref_id="ev:c", source_span_ref_id="span:adopted-c", source_locator=None)
    graph["evidence_refs"].append(third)
    return bundle.model_copy(update={"graph_payload": graph})


def complete_command(command, parent):
    data = object_command(command).model_dump(mode="json")
    data.pop("schema_version")
    target = next(o for o in parent.graph_payload["objects"] if o["object_id"] == OBJECT_ID)
    refs = {e["evidence_ref_id"]: e for e in parent.graph_payload["evidence_refs"]}
    data["evidence_bindings"] = [
        {key: refs[eid].get(key) for key in FIELDS}
        for eid in target["assertion_metadata"]["evidence_ref_ids"]
    ]
    return AdoptedAssertionWithdrawalCommandV4.model_validate(data)


def prepared(monkeypatch, version=2):
    original = existing._repairable_bundle
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: complete_bundle(original()))
    graph, repository, command = existing._prepared(version=version)
    parent = graph.get_revision(command.world_id, command.expected_parent_revision_id)
    return graph, repository, complete_command(command, parent), parent


@pytest.mark.parametrize("version", [1, 2])
def test_complete_cross_source_withdrawal_preserves_everything_else_and_replays(
    monkeypatch, version
):
    graph, repository, command, parent = prepared(monkeypatch, version)
    assert (
        command.evidence_bindings[0].source_artifact_id
        != command.evidence_bindings[1].source_artifact_id
    )
    receipt = repository.withdraw_adopted_assertion(command)
    assert receipt.evidence_bindings == command.evidence_bindings
    assert repository.withdraw_adopted_assertion(command) == receipt
    child = graph.get_revision(command.world_id, receipt.published_revision_id)
    expected = copy.deepcopy(parent.graph_payload)
    expected["objects"] = [o for o in expected["objects"] if o["object_id"] != OBJECT_ID]
    assert child.graph_payload == expected
    assert graph.get_revision(command.world_id, parent.revision.revision_id) == parent
    changed = command.model_copy(update={"actor": "other-reviewer"})
    with pytest.raises(IdempotencyConflictError):
        repository.withdraw_adopted_assertion(changed)


@pytest.mark.parametrize(
    "change", ["omit", "extra", "reorder", "span", "locator", "artifact", "revision"]
)
def test_complete_set_refuses_nonprimary_forgery_without_mutation(monkeypatch, change):
    graph, repository, command, parent = prepared(monkeypatch)
    data = command.model_dump(mode="json")
    bindings = data["evidence_bindings"]
    if change == "omit":
        bindings.pop(1)
    elif change == "extra":
        bindings.append(dict(bindings[1], evidence_ref_id="unbound-reference"))
    elif change == "reorder":
        bindings[1], bindings[2] = bindings[2], bindings[1]
    else:
        field = {
            "span": "source_span_ref_id",
            "locator": "source_locator",
            "artifact": "source_artifact_id",
            "revision": "source_revision_id",
        }[change]
        bindings[1][field] = "forged"
    request = AdoptedAssertionWithdrawalCommandV4.model_validate(data)
    with pytest.raises(PersistenceIntegrityError):
        repository.withdraw_adopted_assertion(request)
    assert graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id
    assert not repository._withdrawal_receipts


@pytest.mark.parametrize("change", ["duplicate", "indexed", "single"])
def test_complete_contract_rejects_ambiguous_or_incomplete_carrier(monkeypatch, change):
    _, _, command, _ = prepared(monkeypatch)
    data = command.model_dump(mode="json")
    if change == "duplicate":
        data["evidence_bindings"][1] = data["evidence_bindings"][0]
    elif change == "single":
        data["evidence_bindings"] = data["evidence_bindings"][:1]
    else:
        data["source_span_ref_id"] = "not-first-binding"
    with pytest.raises(ValidationError):
        AdoptedAssertionWithdrawalCommandV4.model_validate(data)


def test_every_source_revision_must_belong_to_adoption_not_only_first(monkeypatch):
    from dungeonmind.application.adopted_assertion_withdrawal import materialize_withdrawal_payload

    graph, repository, command, parent = prepared(monkeypatch)
    adoption = repository.get_for_world(command.world_id)
    secondary = command.evidence_bindings[1].source_revision_id
    manifest = adoption.membership_manifest.model_copy(
        update={
            "source_revision_ids": [
                r for r in adoption.membership_manifest.source_revision_ids if r != secondary
            ]
        }
    )
    forged = adoption.model_copy(update={"membership_manifest": manifest})
    adopted = graph.get_revision(command.world_id, adoption.published_revision_id)
    with pytest.raises(PersistenceIntegrityError, match="outside adoption membership"):
        materialize_withdrawal_payload(
            command,
            adoption_receipt=forged,
            adopted_payload=adopted.graph_payload,
            parent_payload=parent.graph_payload,
        )


def test_changed_nonprimary_parent_evidence_is_refused(monkeypatch):
    from dungeonmind.application.adopted_assertion_withdrawal import materialize_withdrawal_payload
    from dungeonmind.domain.canonical import canonical_sha256

    graph, repository, command, parent = prepared(monkeypatch)
    adoption = repository.get_for_world(command.world_id)
    adopted = graph.get_revision(command.world_id, adoption.published_revision_id)
    payload = copy.deepcopy(parent.graph_payload)
    secondary = command.evidence_bindings[1].evidence_ref_id
    next(e for e in payload["evidence_refs"] if e["evidence_ref_id"] == secondary)[
        "source_span_ref_id"
    ] = "changed"
    command = command.model_copy(update={"parent_payload_sha256": canonical_sha256(payload)})
    with pytest.raises(PersistenceIntegrityError, match="evidence changed"):
        materialize_withdrawal_payload(
            command,
            adoption_receipt=adoption,
            adopted_payload=adopted.graph_payload,
            parent_payload=payload,
        )
