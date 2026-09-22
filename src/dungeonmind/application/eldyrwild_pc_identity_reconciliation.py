"""Bounded six-PC identity reconciliation for the live Eldyrwild World.

This module composes the generic atomic identity-reconciliation publisher with
the one known Eldyrwild cohort.  It deliberately does not introduce a new
identity primitive or translate IDs for consumers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NoReturn

from ..contracts.graph import StoredGraphRevision
from ..contracts.identity import IdentityReconciliationDecision
from ..contracts.vocabulary import CanonState
from ..domain.errors import PersistenceIntegrityError, RevisionNotFoundError
from .graph_snapshot import GRAPH_SCHEMA_V6
from .graph_snapshot_v6 import GraphObjectV6Record, UnionGraphV6Payload
from .repositories import WorldGraphRepository, WorldIdentityReconciliationRepository
from .world_identity_reconciliation import (
    CanonicalRebindRequest,
    IdentityReconciliationMaterialization,
    IdentityReconciliationPublicationResult,
    materialize_identity_reconciliation,
    publish_identity_reconciliation,
)

ELDYRWILD_WORLD_ID = "eldyrwild"
ELDYRWILD_PC_IDENTITY_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("Baergrom", "node:baergrom", "pc:baergrom"),
    ("Bonogo", "node:bonogo", "pc:bonogo"),
    ("Caelynn", "node:caelynn", "pc:caelynn"),
    ("Ephanna", "node:ephanna", "pc:ephanna"),
    ("Karsemine", "node:karsemine", "pc:karsemine"),
    ("Stafl", "node:stafl", "pc:stafl"),
)
ELDYRWILD_PC_OPERATION_PREFIX = "op:eldyrwild-pc-identity-reconciliation"


@dataclass(frozen=True)
class EldyrwildPcIdentityMapping:
    display_name: str
    source_object_id: str
    target_object_id: str

    def as_request(self) -> CanonicalRebindRequest:
        return CanonicalRebindRequest(self.source_object_id, self.target_object_id)


ELDYRWILD_PC_MAPPINGS: tuple[EldyrwildPcIdentityMapping, ...] = tuple(
    EldyrwildPcIdentityMapping(*values) for values in ELDYRWILD_PC_IDENTITY_MAPPINGS
)


@dataclass(frozen=True)
class EldyrwildPcIdentityPreflight:
    """Read-only materialization result presented before the live apply gate."""

    world_id: str
    parent_revision_id: str
    parent_payload_sha256: str
    object_count: int
    relationship_count: int
    evidence_ref_count: int
    affected_relationship_ids: tuple[str, ...]
    affected_evidence_ref_ids: tuple[str, ...]
    existing_reconciliation_count: int
    materialization: IdentityReconciliationMaterialization

    @property
    def mappings(self) -> tuple[EldyrwildPcIdentityMapping, ...]:
        return ELDYRWILD_PC_MAPPINGS

    @property
    def ready_to_apply(self) -> bool:
        return self.existing_reconciliation_count == 0

    @property
    def expected_child_revision_id(self) -> str:
        return self.materialization.expected_published_revision_id

    def summary(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "parent_revision": self.parent_revision_id,
            "parent_payload_sha256": self.parent_payload_sha256,
            "mappings": [
                {
                    "display_name": item.display_name,
                    "source": item.source_object_id,
                    "target": item.target_object_id,
                }
                for item in self.mappings
            ],
            "objects_affected": len(self.mappings),
            "relationships_affected": len(self.affected_relationship_ids),
            "relationship_ids": list(self.affected_relationship_ids),
            "evidence_preserved": len(self.affected_evidence_ref_ids),
            "evidence_ref_ids": list(self.affected_evidence_ref_ids),
            "parent_objects": self.object_count,
            "parent_relationships": self.relationship_count,
            "parent_evidence_refs": self.evidence_ref_count,
            "existing_reconciliation_count": self.existing_reconciliation_count,
            "expected_child": self.expected_child_revision_id,
            "decision_ids": [decision.decision_id for decision in self.materialization.decisions],
            "ready_to_apply": self.ready_to_apply,
        }


def _fail(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "Eldyrwild PC reconciliation preflight failed",
        details={"reason": reason, **details},
    )


def _source_evidence_ids(record: GraphObjectV6Record) -> set[str]:
    evidence_ids = set(record.assertion_metadata.evidence_ref_ids)
    for alias in record.aliases:
        evidence_ids.update(alias.assertion_metadata.evidence_ref_ids)
    if record.summary is not None:
        evidence_ids.update(record.summary.assertion_metadata.evidence_ref_ids)
    for prop in record.properties:
        evidence_ids.update(prop.assertion_metadata.evidence_ref_ids)
    for aspect in record.aspects:
        evidence_ids.update(aspect.assertion_metadata.evidence_ref_ids)
    return evidence_ids


def _load_parent(
    world_graph_repository: WorldGraphRepository,
    *,
    world_id: str,
) -> StoredGraphRevision:
    head = world_graph_repository.get_head(world_id)
    if head is None:
        _fail("world_head_missing", world_id=world_id)
    parent = world_graph_repository.get_revision(world_id, head.head_revision_id)
    if parent is None:
        raise RevisionNotFoundError(
            f"head revision {head.head_revision_id!r} not found for world {world_id!r}"
        )
    if parent.revision.graph_schema != GRAPH_SCHEMA_V6:
        _fail("unsupported_parent_graph_schema", graph_schema=parent.revision.graph_schema)
    return parent


def _operation_id(parent_revision_id: str) -> str:
    return f"{ELDYRWILD_PC_OPERATION_PREFIX}:{parent_revision_id}"


def _requests() -> tuple[CanonicalRebindRequest, ...]:
    return tuple(item.as_request() for item in ELDYRWILD_PC_MAPPINGS)


def preflight_eldyrwild_pc_identity_reconciliation(
    world_graph_repository: WorldGraphRepository,
    reconciliation_repository: WorldIdentityReconciliationRepository,
    *,
    world_id: str = ELDYRWILD_WORLD_ID,
    operation_id: str | None = None,
    actor: str = "steward",
    reason: str = "reconcile Eldyrwild PC identities to the canonical pc namespace",
    created_at: datetime | None = None,
) -> EldyrwildPcIdentityPreflight:
    """Inspect the current head and materialize the exact six-PC child in memory."""
    if world_id != ELDYRWILD_WORLD_ID:
        _fail("unexpected_world", expected=ELDYRWILD_WORLD_ID, actual=world_id)

    parent = _load_parent(world_graph_repository, world_id=world_id)
    operation = operation_id or _operation_id(parent.revision.revision_id)
    timestamp = created_at or datetime.now(tz=UTC)
    typed_parent = UnionGraphV6Payload.model_validate(parent.graph_payload)
    source_ids = {item.source_object_id for item in ELDYRWILD_PC_MAPPINGS}
    target_ids = {item.target_object_id for item in ELDYRWILD_PC_MAPPINGS}
    objects_by_id = {record.object_id: record for record in typed_parent.objects}
    current_object_ids = set(objects_by_id)
    missing_sources = sorted(source_ids - current_object_ids)
    present_targets = sorted(target_ids & current_object_ids)
    if missing_sources or present_targets:
        _fail(
            "unexpected_cohort_identity_state",
            missing_source_object_ids=missing_sources,
            present_target_object_ids=present_targets,
            current_head_revision_id=parent.revision.revision_id,
        )
    affected_relationships = tuple(
        relationship.relationship_id
        for relationship in typed_parent.relationships
        if relationship.source_object_id in source_ids
        or relationship.target_object_id in source_ids
    )
    affected_evidence = set()
    for record in typed_parent.objects:
        if record.object_id in source_ids:
            affected_evidence.update(_source_evidence_ids(record))
    for relationship in typed_parent.relationships:
        if relationship.relationship_id in affected_relationships:
            affected_evidence.update(relationship.assertion_metadata.evidence_ref_ids)

    for mapping in ELDYRWILD_PC_MAPPINGS:
        record = objects_by_id.get(mapping.source_object_id)
        if record is not None and record.assertion_metadata.canon_state is not CanonState.CANONICAL:
            _fail(
                "source_identity_not_current_canonical",
                source_object_id=mapping.source_object_id,
            )

    existing_history = reconciliation_repository.list_for_world(world_id)
    materialization = materialize_identity_reconciliation(
        parent,
        world_id=world_id,
        operation_id=operation,
        reconciliation_decisions=_requests(),
        actor=actor,
        reason=reason,
        created_at=timestamp,
    )
    return EldyrwildPcIdentityPreflight(
        world_id=world_id,
        parent_revision_id=parent.revision.revision_id,
        parent_payload_sha256=parent.revision.graph_payload_sha256,
        object_count=len(typed_parent.objects),
        relationship_count=len(typed_parent.relationships),
        evidence_ref_count=len(typed_parent.evidence_refs),
        affected_relationship_ids=affected_relationships,
        affected_evidence_ref_ids=tuple(sorted(affected_evidence)),
        existing_reconciliation_count=len(existing_history),
        materialization=materialization,
    )


def apply_eldyrwild_pc_identity_reconciliation(
    preflight: EldyrwildPcIdentityPreflight,
    world_graph_repository: WorldGraphRepository,
    reconciliation_repository: WorldIdentityReconciliationRepository,
    *,
    actor: str = "steward",
    reason: str = "reconcile Eldyrwild PC identities to the canonical pc namespace",
    published_at: datetime | None = None,
) -> IdentityReconciliationPublicationResult:
    """Publish the preflighted batch through the existing atomic publisher."""
    if not preflight.ready_to_apply:
        _fail(
            "unexpected_existing_reconciliation_history",
            count=preflight.existing_reconciliation_count,
        )
    return publish_identity_reconciliation(
        preflight.world_id,
        preflight.parent_revision_id,
        preflight.materialization.decisions[0].operation_id,
        _requests(),
        actor=actor,
        reason=reason,
        published_at=published_at,
        world_graph_repository=world_graph_repository,
        reconciliation_repository=reconciliation_repository,
    )


def materialize_from_persisted_reconciliation(
    parent: StoredGraphRevision,
    decisions: Sequence[IdentityReconciliationDecision],
) -> IdentityReconciliationMaterialization:
    """Rebuild the child from persisted reconciliation decisions, not a fixture."""
    if len(decisions) != len(ELDYRWILD_PC_MAPPINGS):
        _fail("unexpected_reconciliation_decision_count", count=len(decisions))
    ordered = tuple(sorted(decisions, key=lambda decision: decision.decision_id))
    if any(decision.world_id != ELDYRWILD_WORLD_ID for decision in ordered):
        _fail("reconciliation_world_mismatch")
    operation_ids = {decision.operation_id for decision in ordered}
    if len(operation_ids) != 1:
        _fail("reconciliation_operation_mismatch")
    return materialize_identity_reconciliation(
        parent,
        world_id=ELDYRWILD_WORLD_ID,
        operation_id=ordered[0].operation_id,
        reconciliation_decisions=tuple(
            CanonicalRebindRequest(
                decision.source_object_id,
                decision.target_object_id,
            )
            for decision in ordered
        ),
        actor=ordered[0].actor,
        reason=ordered[0].reason,
        created_at=ordered[0].created_at,
    )
