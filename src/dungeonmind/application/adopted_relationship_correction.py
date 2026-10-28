"""Pure correction proof and immutable server-owned predicate rule registry."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NoReturn

from pydantic import ValidationError

from ..contracts.adopted_relationship_correction import (
    AdoptedRelationshipCorrectionCommandV1,
    AdoptedRelationshipCorrectionReceiptV1,
    RelationshipCorrectionRulesV1,
)
from ..contracts.capability import CapabilityPolicy
from ..contracts.existing_world_adoption import ExistingWorldAdoptionReceiptV4
from ..contracts.graph import StoredGraphRevision
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.canonical import canonical_sha256
from ..domain.errors import PersistenceIntegrityError
from .adopted_assertion_withdrawal import _all_assertion_metadata
from .graph_snapshot_v6 import UnionGraphV6Payload

if TYPE_CHECKING:
    from .repositories import ExistingWorldAdoptionRepository


class RelationshipCorrectionRuleRegistry:
    """Composition-root data only; no correction wire value can select rules."""

    def __init__(self, rules: Sequence[RelationshipCorrectionRulesV1] = ()) -> None:
        encoded = {}
        for supplied in rules:
            checked = RelationshipCorrectionRulesV1.model_validate(supplied.model_dump(mode="json"))
            key = (checked.profile_ref.profile_id, checked.profile_ref.profile_revision)
            if key in encoded:
                raise ValueError("duplicate correction profile policy")
            # Retain bytes, not mutable nested profile objects supplied by caller.
            encoded[key] = checked.model_dump_json().encode()
        self._rules = MappingProxyType(encoded)

    def resolve(self, profile: SemanticProfileRef) -> RelationshipCorrectionRulesV1:
        raw = self._rules.get((profile.profile_id, profile.profile_revision))
        if raw is None:
            raise PersistenceIntegrityError("relationship correction rules unavailable")
        rules = RelationshipCorrectionRulesV1.model_validate_json(raw)
        if rules.profile_ref != profile:
            raise PersistenceIntegrityError("relationship correction profile mismatch")
        return rules


def replacement_relationship_id(command: AdoptedRelationshipCorrectionCommandV1) -> str:
    digest = canonical_sha256(
        {
            "world_id": command.world_id,
            "operation_id": command.operation_id,
            "relationship_id": command.relationship_id,
        }
    )
    return "rel:adopted-correction:" + digest


def materialize_relationship_correction(
    command: AdoptedRelationshipCorrectionCommandV1,
    *,
    adoption_receipt: ExistingWorldAdoptionReceiptV4,
    adopted_payload: dict[str, Any],
    parent_payload: dict[str, Any],
    rules: RelationshipCorrectionRulesV1,
) -> dict[str, Any]:
    """Validate complete provenance and replace exactly one raw relationship."""

    def fail(reason: str) -> NoReturn:
        raise PersistenceIntegrityError(
            "adopted relationship correction refused", details={"reason": reason}
        )

    command = AdoptedRelationshipCorrectionCommandV1.model_validate(command.model_dump(mode="json"))
    adopted = UnionGraphV6Payload.model_validate(adopted_payload)
    parent = UnionGraphV6Payload.model_validate(parent_payload)
    if (
        adoption_receipt.world_id != command.world_id
        or adoption_receipt.adoption_id != command.adoption_id
        or adopted.world_id != command.world_id
        or parent.world_id != command.world_id
    ):
        fail("world_or_adoption_mismatch")
    if canonical_sha256(parent_payload) != command.parent_payload_sha256:
        fail("parent_payload_mismatch")
    if (
        adopted.semantic_profile != parent.semantic_profile
        or parent.semantic_profile != rules.profile_ref
    ):
        fail("profile_mismatch")
    original = [
        r
        for r in adopted_payload["relationships"]
        if r["relationship_id"] == command.relationship_id
    ]
    current = [
        r
        for r in parent_payload["relationships"]
        if r["relationship_id"] == command.relationship_id
    ]
    if len(original) != 1 or len(current) != 1 or original != current:
        fail("old_relationship_changed_or_missing")
    old = current[0]
    if canonical_sha256(old) != command.relationship_sha256:
        fail("old_relationship_fingerprint_mismatch")
    metadata = old["assertion_metadata"]
    if metadata.get("canon_state") != "canonical":
        fail("old_relationship_not_canonical")
    for graph in (adopted, parent):
        if (
            sum(m.assertion_id == metadata["assertion_id"] for m in _all_assertion_metadata(graph))
            != 1
        ):
            fail("old_assertion_not_unique")
    objects = {o["object_id"]: o for o in parent_payload["objects"]}
    if len(objects) != len(parent_payload["objects"]):
        fail("ambiguous_endpoint_identity")
    source = objects.get(command.replacement_source_object_id)
    target = objects.get(command.replacement_target_object_id)
    if source is None or target is None:
        fail("replacement_endpoint_missing")
    for obj, digest in [
        (source, command.replacement_source_object_sha256),
        (target, command.replacement_target_object_sha256),
    ]:
        if (
            obj is None
            or canonical_sha256(obj) != digest
            or obj["assertion_metadata"].get("canon_state") != "canonical"
        ):
            fail("replacement_endpoint_mismatch")
    for field, old_endpoint, new_endpoint in [
        (
            "source_aspect_assertion_id",
            old["source_object_id"],
            command.replacement_source_object_id,
        ),
        (
            "target_aspect_assertion_id",
            old["target_object_id"],
            command.replacement_target_object_id,
        ),
    ]:
        if old.get(field) is not None and old_endpoint != new_endpoint:
            fail("aspect_scoped_endpoint_move")

    def endpoint_kind(obj: dict[str, Any], aspect_id: str | None) -> str:
        if aspect_id is None:
            return obj["kind"]
        aspects = [
            a
            for a in obj.get("aspects", [])
            if a["assertion_metadata"]["assertion_id"] == aspect_id
        ]
        if len(aspects) != 1 or aspects[0]["assertion_metadata"].get("canon_state") != "canonical":
            fail("endpoint_aspect_not_canonical_or_owned")
        return aspects[0]["kind"]

    source_kind = endpoint_kind(source, old.get("source_aspect_assertion_id"))
    target_kind = endpoint_kind(target, old.get("target_aspect_assertion_id"))
    policy = next(
        (r for r in rules.predicates if r.predicate == command.replacement_predicate), None
    )
    if (
        policy is None
        or source_kind not in policy.subject_kinds
        or target_kind not in policy.object_kinds
    ):
        fail("predicate_endpoint_policy_refused")
    if metadata["evidence_ref_ids"] != [b.evidence_ref_id for b in command.old_evidence_bindings]:
        fail("incomplete_old_evidence")
    for binding in (*command.old_evidence_bindings, *command.replacement_evidence_bindings):
        original_refs = [
            e for e in adopted.evidence_refs if e.evidence_ref_id == binding.evidence_ref_id
        ]
        current_refs = [
            e for e in parent.evidence_refs if e.evidence_ref_id == binding.evidence_ref_id
        ]
        if len(original_refs) != 1 or len(current_refs) != 1 or original_refs != current_refs:
            fail("evidence_missing_or_changed")
        ref = current_refs[0]
        if any(
            getattr(ref, key) != getattr(binding, key)
            for key in (
                "source_artifact_id",
                "source_revision_id",
                "source_span_ref_id",
                "source_locator",
            )
        ):
            fail("evidence_binding_mismatch")
        manifest = adoption_receipt.membership_manifest
        if (
            binding.source_artifact_id not in manifest.source_artifact_ids
            or binding.source_revision_id not in manifest.source_revision_ids
        ):
            fail("evidence_outside_adoption_membership")
    new_refs = [b.evidence_ref_id for b in command.replacement_evidence_bindings]
    if (
        old["source_object_id"] == command.replacement_source_object_id
        and old["target_object_id"] == command.replacement_target_object_id
        and old["predicate"] == command.replacement_predicate
        and set(metadata["evidence_ref_ids"]) == set(new_refs)
    ):
        fail("no_semantic_correction")
    replacement = copy.deepcopy(old)
    replacement.update(
        relationship_id=replacement_relationship_id(command),
        source_object_id=command.replacement_source_object_id,
        target_object_id=command.replacement_target_object_id,
        predicate=command.replacement_predicate,
    )
    replacement["assertion_metadata"].update(
        assertion_id="assertion:adopted-correction:"
        + replacement["relationship_id"].split(":")[-1],
        evidence_ref_ids=new_refs,
    )
    if any(
        r["relationship_id"] == replacement["relationship_id"]
        for r in parent_payload["relationships"]
    ):
        fail("replacement_relationship_identity_collision")
    if any(
        m.assertion_id == replacement["assertion_metadata"]["assertion_id"]
        for m in _all_assertion_metadata(parent)
    ):
        fail("replacement_assertion_identity_collision")
    child = copy.deepcopy(parent_payload)
    child["relationships"] = [
        replacement if r["relationship_id"] == command.relationship_id else r
        for r in child["relationships"]
    ]
    UnionGraphV6Payload.model_validate(child)
    return child


def validate_endpoint_identity(
    command: AdoptedRelationshipCorrectionCommandV1, history: Sequence[dict[str, Any]]
) -> None:
    endpoints = {command.replacement_source_object_id, command.replacement_target_object_id}
    superseded = {
        identifier
        for d in history
        if d.get("status", "active") == "active"
        for identifier in d.get("supersedes_decision_ids", [])
    }
    for decision in history:
        if decision.get("world_id") != command.world_id:
            raise PersistenceIntegrityError("correction identity history World mismatch")
        if decision.get("status", "active") != "active" or decision["decision_id"] in superseded:
            continue
        if decision.get("source_object_id") in endpoints or (
            decision.get("decision_kind") in {"merge", "split"}
            and any(
                oid in decision.get("subject_object_ids", [])
                and decision.get("target_object_ids") != [oid]
                for oid in endpoints
            )
        ):
            raise PersistenceIntegrityError("correction endpoint identity is redirected")


def make_correction_receipt(
    command: AdoptedRelationshipCorrectionCommandV1,
    adoption: ExistingWorldAdoptionReceiptV4,
    rules: RelationshipCorrectionRulesV1,
    parent: StoredGraphRevision,
    child: StoredGraphRevision,
    history: Sequence[dict[str, Any]],
) -> AdoptedRelationshipCorrectionReceiptV1:
    from ..contracts.adopted_relationship_correction import AdoptedRelationshipCorrectionReceiptV1

    replacement = next(
        r
        for r in child.graph_payload["relationships"]
        if r["relationship_id"] == replacement_relationship_id(command)
    )
    return AdoptedRelationshipCorrectionReceiptV1(
        command=command,
        request_sha256=canonical_sha256(command.model_dump(mode="json")),
        adoption_receipt_fingerprint=canonical_sha256(adoption.model_dump(mode="json")),
        rules_sha256=canonical_sha256(rules.model_dump(mode="json")),
        identity_history=tuple(history),
        identity_history_sha256=canonical_sha256(history),
        published_revision_id=child.revision.revision_id,
        published_payload_sha256=canonical_sha256(child.graph_payload),
        replacement_relationship_id=replacement["relationship_id"],
        replacement_relationship_sha256=canonical_sha256(replacement),
    )


def verify_correction_receipt(
    receipt: AdoptedRelationshipCorrectionReceiptV1,
    *,
    adoption: ExistingWorldAdoptionReceiptV4,
    rules: RelationshipCorrectionRulesV1,
    adopted: StoredGraphRevision,
    parent: StoredGraphRevision,
    child: StoredGraphRevision,
    history: Sequence[dict[str, Any]],
) -> AdoptedRelationshipCorrectionReceiptV1:
    from ..contracts.adopted_relationship_correction import AdoptedRelationshipCorrectionReceiptV1

    try:
        receipt = AdoptedRelationshipCorrectionReceiptV1.model_validate(
            receipt.model_dump(mode="json")
        )
    except (ValidationError, ValueError, TypeError):
        raise PersistenceIntegrityError("relationship correction receipt shape invalid") from None
    command = receipt.command
    if len({r["decision_id"] for r in receipt.identity_history}) != len(receipt.identity_history):
        raise PersistenceIntegrityError("relationship correction identity snapshot is ambiguous")
    current_history = {r["decision_id"]: r for r in history}
    if len(current_history) != len(history) or any(
        current_history.get(r["decision_id"]) != r for r in receipt.identity_history
    ):
        raise PersistenceIntegrityError("correction historical identity authority changed")
    validate_endpoint_identity(command, receipt.identity_history)
    expected = materialize_relationship_correction(
        command,
        adoption_receipt=adoption,
        adopted_payload=adopted.graph_payload,
        parent_payload=parent.graph_payload,
        rules=rules,
    )
    if (
        child.graph_payload != expected
        or child.revision.parent_revision_id != parent.revision.revision_id
        or parent.revision.revision_id != command.expected_parent_revision_id
        or child.revision.world_id != command.world_id
        or child.revision.operation_ids != [command.operation_id]
    ):
        raise PersistenceIntegrityError("correction receipt graph lineage mismatch")
    rebuilt = make_correction_receipt(
        command, adoption, rules, parent, child, list(receipt.identity_history)
    )
    if rebuilt != receipt:
        raise PersistenceIntegrityError("correction receipt proof mismatch")
    return receipt.model_copy(deep=True)


def correct_adopted_relationship(
    command: AdoptedRelationshipCorrectionCommandV1,
    *,
    capability_policy: CapabilityPolicy,
    repository: ExistingWorldAdoptionRepository,
) -> AdoptedRelationshipCorrectionReceiptV1:
    from ..contracts.adopted_relationship_correction import CORRECT_ADOPTED_RELATIONSHIP_TOOL
    from ..contracts.capability import CapabilityEffect
    from ..contracts.projection import Admissibility
    from ..domain.capability import evaluate_capability
    from ..domain.errors import CapabilityDeniedError

    command = AdoptedRelationshipCorrectionCommandV1.model_validate(command.model_dump(mode="json"))
    evaluate_capability(
        capability_policy,
        tool_name=CORRECT_ADOPTED_RELATIONSHIP_TOOL,
        effect=CapabilityEffect.COMMIT,
    )
    scope = capability_policy.graph_scope
    if (
        scope is None
        or scope.admissibility != Admissibility.GM
        or scope.world_id != command.world_id
        or scope.revision_pin != command.expected_parent_revision_id
    ):
        raise CapabilityDeniedError(
            "relationship correction requires exact GM World/revision scope"
        )
    return repository.correct_adopted_relationship(command)
