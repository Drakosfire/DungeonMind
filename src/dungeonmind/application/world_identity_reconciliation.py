"""Pure materialization and orchestration for current-World identity rebinds.

The application boundary owns validation and deterministic graph transformation.
The PostgreSQL adapter owns the single transaction that persists the resulting
identity history, immutable graph child, and World head CAS.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.graph import StoredGraphRevision
from ..contracts.identity import IdentityReconciliationDecision
from ..contracts.vocabulary import CanonState
from ..domain.canonical import canonical_sha256
from ..domain.errors import PersistenceIntegrityError, RevisionNotFoundError
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GRAPH_SCHEMA_V6
from .graph_snapshot_v6 import (
    GraphObjectV6Record,
    GraphRelationshipV6Record,
    UnionGraphV6Payload,
)
from .repositories import WorldGraphRepository, WorldIdentityReconciliationRepository

_OPERATION_TOKEN_PREFIX = "identity-reconciliation"


def _fail(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "identity reconciliation failed validation",
        details={"reason": reason, **details},
    ) from None


@dataclass(frozen=True)
class CanonicalRebindRequest:
    """Explicit one-to-one current identity replacement requested by a caller."""

    source_object_id: str
    target_object_id: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source_object_id", self.source_object_id),
            ("target_object_id", self.target_object_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-blank string")
        if self.source_object_id == self.target_object_id:
            raise ValueError("canonical rebind source and target must differ")


@dataclass(frozen=True)
class IdentityReconciliationPublicationCommand:
    """Fully materialized command handed to the atomic persistence adapter."""

    world_id: str
    operation_id: str
    expected_parent_revision_id: str
    parent_graph_payload_sha256: str
    graph_schema: str
    graph_payload: dict[str, Any]
    operation_ids: tuple[str, ...]
    decisions: tuple[IdentityReconciliationDecision, ...]
    request_digest: str
    expected_published_revision_id: str
    requested_published_at: datetime


@dataclass(frozen=True)
class IdentityReconciliationPublicationResult:
    """Durable terminal result; exact retries return the same identifiers."""

    world_id: str
    operation_id: str
    parent_revision_id: str
    published_revision_id: str
    decision_ids: tuple[str, ...]
    already_applied: bool = False


@dataclass(frozen=True)
class IdentityReconciliationMaterialization:
    graph_schema: str
    graph_payload: dict[str, Any]
    parent_graph_payload_sha256: str
    operation_ids: tuple[str, ...]
    request_digest: str
    decisions: tuple[IdentityReconciliationDecision, ...]
    expected_published_revision_id: str


def _reload_parent(parent: StoredGraphRevision, *, world_id: str) -> UnionGraphV6Payload:
    if parent.revision.world_id != world_id:
        _fail(
            "parent_world_mismatch",
            parent_world_id=parent.revision.world_id,
            world_id=world_id,
        )
    if parent.revision.graph_schema != GRAPH_SCHEMA_V6:
        _fail("unsupported_graph_schema", graph_schema=parent.revision.graph_schema)
    if canonical_sha256(parent.graph_payload) != parent.revision.graph_payload_sha256:
        _fail("parent_payload_hash_mismatch", revision_id=parent.revision.revision_id)
    try:
        typed = UnionGraphV6Payload.model_validate(copy.deepcopy(parent.graph_payload))
    except (TypeError, ValidationError, ValueError):
        _fail("parent_payload_validation", revision_id=parent.revision.revision_id)
    if typed.world_id != world_id:
        _fail("parent_payload_world_mismatch", payload_world_id=typed.world_id, world_id=world_id)
    return typed


def materialize_identity_reconciliation(
    parent: StoredGraphRevision,
    *,
    world_id: str,
    operation_id: str,
    reconciliation_decisions: Sequence[CanonicalRebindRequest],
    actor: str,
    reason: str | None,
    created_at: datetime,
) -> IdentityReconciliationMaterialization:
    """Validate and deterministically transform one exact v6 graph parent."""
    if not operation_id.strip():
        raise ValueError("operation_id must be a non-blank string")
    if not actor.strip():
        raise ValueError("actor must be a non-blank string")
    if not reconciliation_decisions:
        raise ValueError("at least one identity reconciliation decision is required")

    ordered = tuple(
        sorted(
            reconciliation_decisions,
            key=lambda item: (item.source_object_id, item.target_object_id),
        )
    )
    sources = [item.source_object_id for item in ordered]
    targets = [item.target_object_id for item in ordered]
    if len(set(sources)) != len(sources):
        _fail("duplicate_source_identity")
    if len(set(targets)) != len(targets):
        _fail("duplicate_target_identity")
    if set(sources) & set(targets):
        _fail("cyclic_or_composed_identity_mapping")

    typed_parent = _reload_parent(parent, world_id=world_id)
    current_ids = {record.object_id for record in typed_parent.objects}
    missing_sources = sorted(set(sources) - current_ids)
    if missing_sources:
        _fail("unknown_source_identity", source_object_ids=missing_sources)
    noncanonical_sources = sorted(
        record.object_id
        for record in typed_parent.objects
        if record.object_id in set(sources)
        and record.assertion_metadata.canon_state is not CanonState.CANONICAL
    )
    if noncanonical_sources:
        _fail("source_identity_not_current_canonical", source_object_ids=noncanonical_sources)
    colliding_targets = sorted(set(targets) & current_ids)
    if colliding_targets:
        _fail("target_identity_collision", target_object_ids=colliding_targets)

    mapping = dict(zip(sources, targets, strict=True))
    raw_parent = copy.deepcopy(parent.graph_payload)
    transformed_object_rows: list[dict[str, Any]] = []
    for raw_record, record in zip(raw_parent["objects"], typed_parent.objects, strict=True):
        transformed_record = {
            **raw_record,
            "object_id": mapping.get(record.object_id, record.object_id),
        }
        GraphObjectV6Record.model_validate(transformed_record)
        transformed_object_rows.append(transformed_record)
    transformed_relationship_rows: list[dict[str, Any]] = []
    for raw_relationship, relationship in zip(
        raw_parent["relationships"], typed_parent.relationships, strict=True
    ):
        transformed_relationship = {
            **raw_relationship,
            "source_object_id": mapping.get(
                relationship.source_object_id, relationship.source_object_id
            ),
            "target_object_id": mapping.get(
                relationship.target_object_id, relationship.target_object_id
            ),
        }
        GraphRelationshipV6Record.model_validate(transformed_relationship)
        transformed_relationship_rows.append(transformed_relationship)

    transformed_payload = {
        **raw_parent,
        "objects": transformed_object_rows,
        "relationships": transformed_relationship_rows,
    }
    transformed = UnionGraphV6Payload.model_validate(transformed_payload)
    transformed_ids = [record.object_id for record in transformed.objects]
    if len(set(transformed_ids)) != len(transformed_ids):
        _fail("transformed_identity_collision")
    current_transformed_ids = set(transformed_ids)
    dangling = sorted(
        {
            endpoint
            for relationship in transformed.relationships
            for endpoint in (relationship.source_object_id, relationship.target_object_id)
            if endpoint not in current_transformed_ids
        }
    )
    if dangling:
        _fail("dangling_relationship_identity", object_ids=dangling)

    request_digest = canonical_sha256(
        {
            "world_id": world_id,
            "parent_revision_id": parent.revision.revision_id,
            "operation_id": operation_id,
            "actor": actor,
            "reason": reason,
            "reconciliation_decisions": [
                {
                    "source_object_id": item.source_object_id,
                    "target_object_id": item.target_object_id,
                }
                for item in ordered
            ],
        }
    )
    decisions = tuple(
        IdentityReconciliationDecision(
            decision_id=(
                "dec:rebind:"
                + canonical_sha256(
                    {
                        "operation_id": operation_id,
                        "source_object_id": item.source_object_id,
                        "target_object_id": item.target_object_id,
                    }
                )[:32]
            ),
            world_id=world_id,
            operation_id=operation_id,
            source_object_id=item.source_object_id,
            target_object_id=item.target_object_id,
            actor=actor,
            reason=reason,
            created_at=created_at,
        )
        for item in ordered
    )
    operation_ids = (
        f"{_OPERATION_TOKEN_PREFIX}:{operation_id}",
        f"{_OPERATION_TOKEN_PREFIX}-request:{request_digest}",
    )
    graph_payload = transformed_payload
    expected_published_revision_id = compute_revision_id(
        world_id=world_id,
        parent_revision_id=parent.revision.revision_id,
        operation_ids=list(operation_ids),
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload_sha256=canonical_sha256(graph_payload),
    )
    return IdentityReconciliationMaterialization(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=graph_payload,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        operation_ids=operation_ids,
        request_digest=request_digest,
        decisions=decisions,
        expected_published_revision_id=expected_published_revision_id,
    )


def publish_identity_reconciliation(
    world_id: str,
    expected_parent_revision_id: str,
    operation_id: str,
    reconciliation_decisions: Sequence[CanonicalRebindRequest],
    *,
    actor: str,
    reason: str | None,
    published_at: datetime | None = None,
    world_graph_repository: WorldGraphRepository,
    reconciliation_repository: WorldIdentityReconciliationRepository,
) -> IdentityReconciliationPublicationResult:
    """Prepare one deterministic child and delegate its atomic publication."""
    parent = world_graph_repository.get_revision(world_id, expected_parent_revision_id)
    if parent is None:
        raise RevisionNotFoundError(
            f"revision {expected_parent_revision_id!r} not found for world {world_id!r}"
        )
    publication_time = published_at or datetime.now(tz=UTC)
    materialization = materialize_identity_reconciliation(
        parent,
        world_id=world_id,
        operation_id=operation_id,
        reconciliation_decisions=reconciliation_decisions,
        actor=actor,
        reason=reason,
        created_at=publication_time,
    )
    command = IdentityReconciliationPublicationCommand(
        world_id=world_id,
        operation_id=operation_id,
        expected_parent_revision_id=expected_parent_revision_id,
        parent_graph_payload_sha256=materialization.parent_graph_payload_sha256,
        graph_schema=materialization.graph_schema,
        graph_payload=materialization.graph_payload,
        operation_ids=materialization.operation_ids,
        decisions=materialization.decisions,
        request_digest=materialization.request_digest,
        expected_published_revision_id=materialization.expected_published_revision_id,
        requested_published_at=publication_time,
    )
    result = reconciliation_repository.publish(command)
    if (
        result.world_id != world_id
        or result.operation_id != operation_id
        or result.parent_revision_id != expected_parent_revision_id
        or result.published_revision_id != materialization.expected_published_revision_id
        or result.decision_ids
        != tuple(decision.decision_id for decision in materialization.decisions)
    ):
        _fail("publication_result_binding_mismatch")
    return result
