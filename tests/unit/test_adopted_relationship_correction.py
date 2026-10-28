"""Atomic correction proofs are distinct from graph-wide quality claims."""

import copy

import pytest
from pydantic import ValidationError

import tests.unit.test_adopted_assertion_withdrawal as existing
from dungeonmind.application.adopted_relationship_correction import (
    RelationshipCorrectionRuleRegistry,
)
from dungeonmind.contracts.adopted_relationship_correction import (
    AdoptedRelationshipCorrectionCommandV1,
    PredicateEndpointRuleV1,
    RelationshipCorrectionRulesV1,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from dungeonmind.infrastructure.memory.repositories import InMemoryExistingWorldAdoptionRepository
from tests.unit.test_existing_world_adoption import make_stores

FIELDS = (
    "evidence_ref_id",
    "source_artifact_id",
    "source_revision_id",
    "source_span_ref_id",
    "source_locator",
)


def repairable_bundle(bundle):
    payload = copy.deepcopy(bundle.graph_payload)
    next(r for r in payload["relationships"] if r["relationship_id"] == "rel:leads")[
        "assertion_metadata"
    ]["evidence_ref_ids"] = ["ev:a", "ev:b"]
    for ref in payload["evidence_refs"]:
        if ref["evidence_ref_id"] == "ev:b":
            ref.update(
                source_span_ref_id="span:correction-b", source_locator="fixture://correction-b"
            )
    return bundle.model_copy(update={"graph_payload": payload})


def rules_for(payload):
    old = next(r for r in payload["relationships"] if r["relationship_id"] == "rel:leads")
    objects = {o["object_id"]: o for o in payload["objects"]}

    def kind(oid, aspect):
        obj = objects[oid]
        if aspect is None:
            return obj["kind"]
        return next(
            a["kind"] for a in obj["aspects"] if a["assertion_metadata"]["assertion_id"] == aspect
        )

    return RelationshipCorrectionRulesV1(
        profile_ref=SemanticProfileRef.model_validate(payload["semantic_profile"]),
        catalog_id="synthetic.relationships",
        catalog_version="v1",
        catalog_sha256="c" * 64,
        predicates=(
            PredicateEndpointRuleV1(
                predicate=old["predicate"],
                subject_kinds=(
                    kind(old["source_object_id"], old.get("source_aspect_assertion_id")),
                ),
                object_kinds=(
                    kind(old["target_object_id"], old.get("target_aspect_assertion_id")),
                ),
            ),
        ),
    )


def command_for(legacy, parent):
    payload = parent.graph_payload
    old = next(r for r in payload["relationships"] if r["relationship_id"] == "rel:leads")
    objects = {o["object_id"]: o for o in payload["objects"]}
    refs = {e["evidence_ref_id"]: e for e in payload["evidence_refs"]}

    def bindings(ids):
        return [{k: refs[eid].get(k) for k in FIELDS} for eid in ids]

    return AdoptedRelationshipCorrectionCommandV1(
        operation_id="correction:synthetic",
        world_id=legacy.world_id,
        adoption_id=legacy.adoption_id,
        expected_parent_revision_id=legacy.expected_parent_revision_id,
        parent_payload_sha256=canonical_sha256(payload),
        relationship_id=old["relationship_id"],
        relationship_sha256=canonical_sha256(old),
        old_evidence_bindings=bindings(old["assertion_metadata"]["evidence_ref_ids"]),
        replacement_source_object_id="obj:pc-alpha",
        replacement_source_object_sha256=canonical_sha256(objects["obj:pc-alpha"]),
        replacement_target_object_id=old["target_object_id"],
        replacement_target_object_sha256=canonical_sha256(objects[old["target_object_id"]]),
        replacement_predicate=old["predicate"],
        replacement_evidence_bindings=bindings(["ev:b"]),
        actor="reviewer:synthetic",
        rationale="Synthetic endpoint and complete citation correction",
        requested_at=legacy.requested_at,
    )


def prepared(monkeypatch):
    original = existing._repairable_bundle
    bundle = repairable_bundle(original())
    monkeypatch.setattr(existing, "_repairable_bundle", lambda: bundle)
    stores = make_stores()
    graph, sources, contributions, identity, _ = stores
    rules = rules_for(bundle.graph_payload)
    repository = InMemoryExistingWorldAdoptionRepository(
        graph,
        sources,
        contributions,
        identity,
        correction_rule_registry=RelationshipCorrectionRuleRegistry([rules]),
    )
    _, _, legacy = existing._prepared(
        version=2, stores=(graph, sources, contributions, identity, repository)
    )
    parent = graph.get_revision(legacy.world_id, legacy.expected_parent_revision_id)
    return graph, repository, command_for(legacy, parent), parent, rules


def test_correction_is_atomic_preserves_qualifiers_and_replays(monkeypatch):
    graph, repository, command, parent, _ = prepared(monkeypatch)
    before = copy.deepcopy(parent.graph_payload)
    receipt = repository.correct_adopted_relationship(command)
    assert repository.correct_adopted_relationship(command) == receipt
    child = graph.get_revision(command.world_id, receipt.published_revision_id).graph_payload
    assert child["objects"] == before["objects"]
    assert child["evidence_refs"] == before["evidence_refs"]
    old = next(
        r for r in before["relationships"] if r["relationship_id"] == command.relationship_id
    )
    new = next(
        r
        for r in child["relationships"]
        if r["relationship_id"] == receipt.replacement_relationship_id
    )
    assert new["source_object_id"] == "obj:pc-alpha"
    for key, value in old["assertion_metadata"].items():
        if key not in {"assertion_id", "evidence_ref_ids"}:
            assert new["assertion_metadata"][key] == value
    assert new["assertion_metadata"]["evidence_ref_ids"] == ["ev:b"]
    assert [
        r for r in child["relationships"] if r["relationship_id"] != new["relationship_id"]
    ] == [r for r in before["relationships"] if r["relationship_id"] != old["relationship_id"]]
    assert graph.get_revision(command.world_id, parent.revision.revision_id).graph_payload == before
    with pytest.raises(IdempotencyConflictError):
        repository.correct_adopted_relationship(
            command.model_copy(update={"rationale": "different"})
        )


@pytest.mark.parametrize(
    "change",
    ["old_hash", "endpoint_hash", "predicate", "binding", "kind", "old_omit", "old_reorder"],
)
def test_correction_refuses_forgery_without_mutation(monkeypatch, change):
    graph, repository, command, parent, _ = prepared(monkeypatch)
    data = command.model_dump(mode="json")
    if change == "old_hash":
        data["relationship_sha256"] = "0" * 64
    elif change == "endpoint_hash":
        data["replacement_source_object_sha256"] = "0" * 64
    elif change == "predicate":
        data["replacement_predicate"] = "test:unknown"
    elif change == "binding":
        data["replacement_evidence_bindings"][0]["source_span_ref_id"] = "forged"
    elif change == "old_omit":
        data["old_evidence_bindings"].pop()
    elif change == "old_reorder":
        data["old_evidence_bindings"].reverse()
    else:
        target = next(
            o
            for o in parent.graph_payload["objects"]
            if o["object_id"] == command.replacement_target_object_id
        )
        data.update(
            replacement_source_object_id=target["object_id"],
            replacement_source_object_sha256=canonical_sha256(target),
        )
    with pytest.raises(PersistenceIntegrityError):
        repository.correct_adopted_relationship(
            AdoptedRelationshipCorrectionCommandV1.model_validate(data)
        )
    assert graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id
    assert not repository._relationship_correction_receipts


@pytest.mark.parametrize("stage", ["correction_graph", "correction_receipt"])
def test_correction_rolls_back_both_stages(monkeypatch, stage):
    graph, repository, command, parent, _ = prepared(monkeypatch)

    def fail(phase):
        if phase == stage:
            raise RuntimeError("injected correction failure")

    repository._failure_hook = fail
    with pytest.raises(RuntimeError, match="injected"):
        repository.correct_adopted_relationship(command)
    assert graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id
    assert len(graph._revisions) == 1
    assert not repository._relationship_correction_receipts


def test_caller_cannot_supply_rules_and_registry_is_immutable(monkeypatch):
    _, _, command, parent, rules = prepared(monkeypatch)
    data = command.model_dump(mode="json") | {"rules": rules.model_dump(mode="json")}
    with pytest.raises(ValidationError):
        AdoptedRelationshipCorrectionCommandV1.model_validate(data)
    registry = RelationshipCorrectionRuleRegistry([rules])
    rules.profile_ref.profile_revision = "changed"
    assert (
        registry.resolve(
            SemanticProfileRef.model_validate(parent.graph_payload["semantic_profile"])
        ).profile_ref.profile_revision
        != "changed"
    )
    with pytest.raises(PersistenceIntegrityError):
        RelationshipCorrectionRuleRegistry().resolve(
            SemanticProfileRef.model_validate(parent.graph_payload["semantic_profile"])
        )


def redirect_source(repository, command):
    from dungeonmind.contracts.identity import IdentityDecisionRecordV2

    repository._identity.append(
        IdentityDecisionRecordV2(
            decision_id="decision:later-source-merge",
            world_id=command.world_id,
            decision_kind="merge",
            subject_object_ids=[command.replacement_source_object_id, "obj:pc-beta"],
            target_object_ids=["obj:pc-beta"],
            merge_side_effects={},
            actor="reviewer:synthetic",
            created_at=command.requested_at,
        )
    )


def test_redirected_identity_refuses_publication_but_surviving_merge_target_is_usable(monkeypatch):
    graph, repository, command, parent, _ = prepared(monkeypatch)
    redirect_source(repository, command)
    with pytest.raises(PersistenceIntegrityError, match="redirected"):
        repository.correct_adopted_relationship(command)
    assert graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id
    assert not repository._relationship_correction_receipts


def test_later_identity_change_does_not_rewrite_publication_time_authority(monkeypatch):
    graph, repository, command, _, _ = prepared(monkeypatch)
    receipt = repository.correct_adopted_relationship(command)
    redirect_source(repository, command)
    assert repository.correct_adopted_relationship(command) == receipt
    assert graph.get_head(command.world_id).head_revision_id == receipt.published_revision_id


@pytest.mark.parametrize("change", ["world", "revision", "admissibility"])
def test_application_requires_exact_gm_scope(monkeypatch, change):
    from dungeonmind.application.adopted_relationship_correction import correct_adopted_relationship
    from dungeonmind.contracts.adopted_relationship_correction import (
        CORRECT_ADOPTED_RELATIONSHIP_TOOL,
    )
    from dungeonmind.contracts.capability import CapabilityPolicy
    from dungeonmind.domain.errors import CapabilityDeniedError

    graph, repository, command, parent, _ = prepared(monkeypatch)
    policy_data = existing._authorized_policy(
        world_id=command.world_id, revision_id=command.expected_parent_revision_id
    ).model_dump(mode="json")
    policy_data["enabled_tools"] = [CORRECT_ADOPTED_RELATIONSHIP_TOOL]
    policy_data["tool_rules"][0]["tool_name"] = CORRECT_ADOPTED_RELATIONSHIP_TOOL
    if change == "world":
        policy_data["graph_scope"]["world_id"] = "other-world"
    elif change == "revision":
        policy_data["graph_scope"]["revision_pin"] = "other-revision"
    else:
        policy_data["graph_scope"]["admissibility"] = "player"
    with pytest.raises(CapabilityDeniedError):
        correct_adopted_relationship(
            command,
            capability_policy=CapabilityPolicy.model_validate(policy_data),
            repository=repository,
        )
    assert graph.get_head(command.world_id).head_revision_id == parent.revision.revision_id


def test_pinned_dnd_rules_do_not_allow_recruitment_for_an_npc():
    from dungeonmind_dnd.application.relationship_correction_rules import (
        builtin_v3_relationship_correction_rules,
    )

    rules = builtin_v3_relationship_correction_rules()
    recruitment = next(p for p in rules.predicates if p.predicate == "dnd5e:recruits_for")
    assert "dnd5e:npc" not in recruitment.object_kinds
    assert "dnd5e:group" in recruitment.object_kinds
    presence = next(p for p in rules.predicates if p.predicate == "dnd5e:present_at")
    assert "dnd5e:creature" in presence.subject_kinds
    assert "dnd5e:encounter" in presence.object_kinds


@pytest.mark.parametrize(
    "field", ["rules_sha256", "identity_history_sha256", "published_payload_sha256"]
)
def test_receipt_proof_tampering_is_not_accepted_as_replay(monkeypatch, field):
    graph, repository, command, _, _ = prepared(monkeypatch)
    receipt = repository.correct_adopted_relationship(command)
    repository._relationship_correction_receipts[command.operation_id] = receipt.model_copy(
        update={field: "0" * 64}
    )
    with pytest.raises(PersistenceIntegrityError):
        repository.correct_adopted_relationship(command)
    assert graph.get_head(command.world_id).head_revision_id == receipt.published_revision_id
