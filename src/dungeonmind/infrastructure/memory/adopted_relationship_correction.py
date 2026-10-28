"""In-memory writer-excluding correction transaction and exact replay."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from ...application.adopted_relationship_correction import (
    make_correction_receipt,
    materialize_relationship_correction,
    validate_endpoint_identity,
    verify_correction_receipt,
)
from ...contracts.adopted_relationship_correction import (
    AdoptedRelationshipCorrectionCommandV1,
    AdoptedRelationshipCorrectionReceiptV1,
)
from ...contracts.existing_world_adoption import ExistingWorldAdoptionReceiptV4
from ...contracts.graph import PublishRevisionCommand
from ...contracts.semantic_profile import SemanticProfileRef
from ...domain.canonical import canonical_sha256
from ...domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)

if TYPE_CHECKING:
    from .repositories import InMemoryExistingWorldAdoptionRepository


def correct_relationship(
    repo: InMemoryExistingWorldAdoptionRepository, command: AdoptedRelationshipCorrectionCommandV1
) -> AdoptedRelationshipCorrectionReceiptV1:
    command = AdoptedRelationshipCorrectionCommandV1.model_validate(command.model_dump(mode="json"))
    world = command.world_id
    with (
        repo._withdrawal_operation_lock,
        repo._graph._lock_for(world),
        repo._sources._lock,
        repo._contributions._lock,
        repo._identity._lock,
    ):
        previous = repo._relationship_correction_receipts.get(command.operation_id)
        if previous and previous.request_sha256 != canonical_sha256(
            command.model_dump(mode="json")
        ):
            raise IdempotencyConflictError("relationship correction operation conflicts")
        stored_adoption = repo._receipts_by_adoption.get(command.adoption_id)
        if stored_adoption is None:
            raise PersistenceIntegrityError("relationship correction adoption missing")
        adoption = repo._reconstruct_unlocked(stored_adoption)
        if not isinstance(adoption, ExistingWorldAdoptionReceiptV4):
            raise PersistenceIntegrityError(
                "relationship correction requires exact adoption membership"
            )
        adopted = repo._graph._revisions.get((world, adoption.published_revision_id))
        parent = repo._graph._revisions.get((world, command.expected_parent_revision_id))
        if adopted is None or parent is None:
            raise PersistenceIntegrityError("relationship correction graph history missing")
        rules = repo._relationship_correction_rules.resolve(
            SemanticProfileRef.model_validate(parent.graph_payload["semantic_profile"])
        )
        history = [d.model_dump(mode="json") for d in repo._identity.list_for_world(world)]
        for binding in (*command.old_evidence_bindings, *command.replacement_evidence_bindings):
            artifact = repo._sources._artifacts.get(binding.source_artifact_id)
            revision = repo._sources._revisions.get(binding.source_revision_id)
            if (
                artifact is None
                or artifact.world_id != world
                or revision is None
                or revision.source_artifact_id != binding.source_artifact_id
                or str(artifact.status) != "active"
            ):
                raise PersistenceIntegrityError("relationship correction source lineage mismatch")
        refs = {r["evidence_ref_id"]: r for r in parent.graph_payload["evidence_refs"]}
        for binding in command.replacement_evidence_bindings:
            ref = refs.get(binding.evidence_ref_id)
            artifact = repo._sources._artifacts.get(binding.source_artifact_id)
            if (
                ref is None
                or artifact is None
                or artifact.source_domain is None
                or ref.get("source_domain") != artifact.source_domain.value
                or ref.get("source_domain_key") != getattr(artifact, "source_domain_key", None)
            ):
                raise PersistenceIntegrityError(
                    "replacement evidence domain differs from authority"
                )
        if previous:
            child = repo._graph._revisions.get((world, previous.published_revision_id))
            if child is None:
                raise PersistenceIntegrityError("relationship correction child missing")
            return verify_correction_receipt(
                previous,
                adoption=adoption,
                rules=rules,
                adopted=adopted,
                parent=parent,
                child=child,
                history=history,
            )
        head = repo._graph._heads.get(world)
        if head is None or head.head_revision_id != command.expected_parent_revision_id:
            raise StaleParentRevisionError(
                world_id=world,
                expected_parent_revision_id=command.expected_parent_revision_id,
                actual_head_revision_id=head.head_revision_id if head else None,
            )
        validate_endpoint_identity(command, history)
        payload = materialize_relationship_correction(
            command,
            adoption_receipt=adoption,
            adopted_payload=adopted.graph_payload,
            parent_payload=parent.graph_payload,
            rules=rules,
        )
        before_head = copy.deepcopy(head)
        before_revisions = set(repo._graph._revisions)
        try:
            revision = repo._graph._publish_revision_locked(
                PublishRevisionCommand(
                    world_id=world,
                    parent_revision_id=command.expected_parent_revision_id,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    operation_ids=[command.operation_id],
                    graph_schema="dm_union_graph_v6",
                    graph_payload=payload,
                    created_at=command.requested_at,
                )
            )
            if repo._failure_hook:
                repo._failure_hook("correction_graph")
            child = repo._graph._revisions[(world, revision.revision_id)]
            receipt = make_correction_receipt(command, adoption, rules, parent, child, history)
            repo._relationship_correction_receipts[command.operation_id] = receipt
            if repo._failure_hook:
                repo._failure_hook("correction_receipt")
            return receipt.model_copy(deep=True)
        except BaseException:
            for key in set(repo._graph._revisions) - before_revisions:
                repo._graph._revisions.pop(key)
            repo._graph._heads[world] = before_head
            repo._relationship_correction_receipts.pop(command.operation_id, None)
            raise
