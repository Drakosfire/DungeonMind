"""Governed withdrawal of one unsupported existing-world assertion."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from ..contracts.adopted_assertion_withdrawal import (
    ADOPTED_ASSERTION_WITHDRAWAL_TOOL,
    AdoptedAssertionWithdrawalCommand,
    AdoptedAssertionWithdrawalCommandV1,
    AdoptedAssertionWithdrawalReceipt,
)
from ..contracts.capability import CapabilityEffect, CapabilityPolicy
from ..contracts.existing_world_adoption import ExistingWorldAdoptionReceiptV4
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.projection import Admissibility
from ..domain.canonical import canonical_sha256
from ..domain.capability import evaluate_capability
from ..domain.errors import CapabilityDeniedError, PersistenceIntegrityError
from .graph_snapshot_v6 import UnionGraphV6Payload
from .repositories import ExistingWorldAdoptionRepository


def _all_assertion_metadata(
    payload: UnionGraphV6Payload,
) -> Iterator[KnowledgeAssertionMetadataV1]:
    for object_record in payload.objects:
        yield object_record.assertion_metadata
        for item in object_record.aliases:
            yield item.assertion_metadata
        if object_record.summary is not None:
            yield object_record.summary.assertion_metadata
        for item in object_record.properties:
            yield item.assertion_metadata
        for item in object_record.aspects:
            yield item.assertion_metadata
    for relationship in payload.relationships:
        yield relationship.assertion_metadata


def withdrawal_request_sha256(command: AdoptedAssertionWithdrawalCommand) -> str:
    return canonical_sha256(command.model_dump(mode="json"))


def materialize_withdrawal_payload(
    command: AdoptedAssertionWithdrawalCommand,
    *,
    adoption_receipt: ExistingWorldAdoptionReceiptV4,
    adopted_payload: dict[str, Any],
    parent_payload: dict[str, Any],
) -> dict[str, Any]:
    """Verify the exact adoption-bound relationship and remove only that record."""
    if (
        adoption_receipt.world_id != command.world_id
        or adoption_receipt.adoption_id != command.adoption_id
    ):
        raise PersistenceIntegrityError("withdrawal adoption receipt identity mismatch")
    manifest = adoption_receipt.membership_manifest
    evidence_revision_ids = set(manifest.source_revision_ids)
    evidence_artifact_ids = set(manifest.source_artifact_ids)
    if not evidence_revision_ids:
        raise PersistenceIntegrityError("adoption receipt has no source-revision membership")

    try:
        adopted = UnionGraphV6Payload.model_validate(copy.deepcopy(adopted_payload))
        parent = UnionGraphV6Payload.model_validate(copy.deepcopy(parent_payload))
    except Exception as exc:
        raise PersistenceIntegrityError(
            "withdrawal requires valid dm_union_graph_v6 payloads"
        ) from exc
    if adopted.world_id != command.world_id or parent.world_id != command.world_id:
        raise PersistenceIntegrityError("withdrawal graph world identity mismatch")
    if adopted.semantic_profile != parent.semantic_profile:
        raise PersistenceIntegrityError("withdrawal cannot change the semantic profile")

    original = [r for r in adopted.relationships if r.relationship_id == command.relationship_id]
    current = [r for r in parent.relationships if r.relationship_id == command.relationship_id]
    if len(original) != 1 or len(current) != 1:
        raise PersistenceIntegrityError("withdrawal target relationship is not unique")
    target = original[0]
    matching_assertions = [
        metadata
        for metadata in _all_assertion_metadata(adopted)
        if metadata.assertion_id == command.assertion_id
    ]
    if len(matching_assertions) != 1 or matching_assertions[0] != target.assertion_metadata:
        raise PersistenceIntegrityError("withdrawal assertion identity is not unique in adoption")
    if target.assertion_metadata.assertion_id != command.assertion_id:
        raise PersistenceIntegrityError("withdrawal assertion does not match adoption")
    if (
        target.source_object_id != command.subject_object_id
        or target.predicate != command.predicate
        or target.target_object_id != command.object_object_id
    ):
        raise PersistenceIntegrityError("withdrawal target tuple differs from the bound request")
    if target != current[0]:
        raise PersistenceIntegrityError("withdrawal target changed since adoption")
    current_matching_assertions = [
        metadata
        for metadata in _all_assertion_metadata(parent)
        if metadata.assertion_id == command.assertion_id
    ]
    if (
        len(current_matching_assertions) != 1
        or current_matching_assertions[0] != current[0].assertion_metadata
    ):
        raise PersistenceIntegrityError("withdrawal assertion identity is ambiguous in parent")
    if target.assertion_metadata.evidence_ref_ids != [command.evidence_ref_id]:
        raise PersistenceIntegrityError(
            "withdrawal requires the complete, single-reference target evidence binding"
        )

    evidence = [e for e in adopted.evidence_refs if e.evidence_ref_id == command.evidence_ref_id]
    if len(evidence) != 1:
        raise PersistenceIntegrityError("withdrawal evidence reference is not unique")
    parent_evidence = [
        e for e in parent.evidence_refs if e.evidence_ref_id == command.evidence_ref_id
    ]
    if len(parent_evidence) != 1 or parent_evidence[0] != evidence[0]:
        raise PersistenceIntegrityError("withdrawal evidence changed since adoption")
    bound = evidence[0]
    if (
        bound.source_revision_id is None
        or bound.source_span_ref_id is None
        or (
            isinstance(command, AdoptedAssertionWithdrawalCommandV1)
            and bound.source_locator is None
        )
    ):
        raise PersistenceIntegrityError("withdrawal requires exact source revision and span")
    if (
        bound.source_revision_id != command.source_revision_id
        or bound.source_artifact_id != command.source_artifact_id
        or bound.source_span_ref_id != command.source_span_ref_id
        or bound.source_locator != command.source_locator
    ):
        raise PersistenceIntegrityError("withdrawal source binding differs from the request")
    if bound.source_revision_id not in evidence_revision_ids:
        raise PersistenceIntegrityError("withdrawal source revision is outside adoption membership")
    if bound.source_artifact_id not in evidence_artifact_ids:
        raise PersistenceIntegrityError("withdrawal source artifact is outside adoption membership")
    if canonical_sha256(parent_payload) != command.parent_payload_sha256:
        raise PersistenceIntegrityError("withdrawal parent payload digest mismatch")

    # Preserve the exact stored JSON representation for every retained record;
    # Pydantic serialization would add defaults to historical sparse payloads.
    child_payload = copy.deepcopy(parent_payload)
    child_payload["relationships"] = [
        record
        for record in child_payload["relationships"]
        if record.get("relationship_id") != command.relationship_id
    ]
    return child_payload


def withdraw_adopted_assertion(
    command: AdoptedAssertionWithdrawalCommand,
    *,
    capability_policy: CapabilityPolicy,
    repository: ExistingWorldAdoptionRepository,
) -> AdoptedAssertionWithdrawalReceipt:
    """Publish an append-only neutral withdrawal through the adoption UoW."""
    command = type(command).model_validate(command.model_dump(mode="json"))
    evaluate_capability(
        capability_policy,
        tool_name=ADOPTED_ASSERTION_WITHDRAWAL_TOOL,
        effect=CapabilityEffect.COMMIT,
    )
    scope = capability_policy.graph_scope
    if scope is None:
        raise CapabilityDeniedError(
            "adopted assertion withdrawal requires a graph scope",
            details={"reason": "missing_graph_scope"},
        )
    if scope.admissibility is not Admissibility.GM:
        raise CapabilityDeniedError(
            "adopted assertion withdrawal requires GM admissibility",
            details={"reason": "non_gm_admissibility"},
        )
    if scope.world_id != command.world_id:
        raise CapabilityDeniedError(
            "capability world scope does not match withdrawal",
            details={"reason": "world_scope_mismatch"},
        )
    if scope.revision_pin != command.expected_parent_revision_id:
        raise CapabilityDeniedError(
            "capability revision pin does not match withdrawal parent",
            details={"reason": "revision_pin_mismatch"},
        )
    return repository.withdraw_adopted_assertion(command)
