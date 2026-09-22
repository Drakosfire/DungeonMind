"""Bounded repair for Eldyrwild's immutable party-registry genesis evidence.

The historical D0 graph stamped six party-registry evidence records as
``OTHER/other``.  Their registered ``SourceArtifactV2`` records are
``OTHER/party_registry``.  This module publishes one immutable child that
repairs only those six existence-evidence domain keys; it never changes
identities, objects, relationships, or source records.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.evidence import SourceArtifactV2, SourceDomain, SourceStatus
from ..contracts.graph import PublishRevisionCommand, StoredGraphRevision
from ..domain.canonical import canonical_sha256
from ..domain.errors import PersistenceIntegrityError, StaleParentRevisionError
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GRAPH_SCHEMA_V6
from .graph_snapshot_v6 import UnionGraphV6Payload
from .repositories import SourceRepository, WorldGraphRepository

ELDYRWILD_WORLD_ID = "eldyrwild"
PARTY_REGISTRY_ARTIFACT_ID = "artifact:party-registry:longmont-c1"
EXPECTED_PARENT_REVISION_ID = "rev:bd1d6a17747566fc8955b3c17f9cf680"
OPERATION_ID = "recovery:eldyrwild:party-registry-pc-provenance:v1"
PC_OBJECT_IDS = (
    "pc:baergrom",
    "pc:bonogo",
    "pc:caelynn",
    "pc:ephanna",
    "pc:karsemine",
    "pc:stafl",
)


def _fail(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "Eldyrwild party-registry provenance repair failed validation",
        details={"reason": reason, **details},
    ) from None


@dataclass(frozen=True)
class PartyRegistryProvenanceMaterialization:
    parent_revision_id: str
    graph_schema: str
    graph_payload: dict[str, Any]
    corrected_evidence_ref_ids: tuple[str, ...]
    expected_child_revision_id: str


@dataclass(frozen=True)
class PartyRegistryProvenanceRepairResult:
    parent_revision_id: str
    child_revision_id: str
    corrected_evidence_ref_ids: tuple[str, ...]
    already_applied: bool


def _typed_parent(parent: StoredGraphRevision) -> UnionGraphV6Payload:
    if parent.revision.world_id != ELDYRWILD_WORLD_ID:
        _fail("parent_world_mismatch", world_id=parent.revision.world_id)
    if parent.revision.graph_schema != GRAPH_SCHEMA_V6:
        _fail("unsupported_graph_schema", graph_schema=parent.revision.graph_schema)
    if canonical_sha256(parent.graph_payload) != parent.revision.graph_payload_sha256:
        _fail("parent_payload_hash_mismatch", revision_id=parent.revision.revision_id)
    try:
        parsed = UnionGraphV6Payload.model_validate(copy.deepcopy(parent.graph_payload))
    except (TypeError, ValidationError, ValueError):
        _fail("parent_payload_validation", revision_id=parent.revision.revision_id)
    if parsed.world_id != ELDYRWILD_WORLD_ID:
        _fail("payload_world_mismatch", world_id=parsed.world_id)
    return parsed


def materialize_party_registry_provenance_repair(
    parent: StoredGraphRevision, *, sources: SourceRepository
) -> PartyRegistryProvenanceMaterialization:
    """Produce the exact child, or fail closed outside the six-PC cohort."""
    typed = _typed_parent(parent)
    object_by_id = {record.object_id: record for record in typed.objects}
    evidence_by_id = {record.evidence_ref_id: record for record in typed.evidence_refs}
    if set(PC_OBJECT_IDS) - set(object_by_id):
        _fail("missing_pc_objects", object_ids=sorted(set(PC_OBJECT_IDS) - set(object_by_id)))
    artifact = sources.get_artifact(PARTY_REGISTRY_ARTIFACT_ID)
    if not isinstance(artifact, SourceArtifactV2):
        _fail("party_registry_artifact_missing_or_legacy")
    if (
        artifact.world_id != ELDYRWILD_WORLD_ID
        or artifact.campaign_id != "longmont-c1"
        or artifact.status is not SourceStatus.ACTIVE
        or artifact.source_domain is not SourceDomain.OTHER
        or artifact.source_domain_key != "party_registry"
    ):
        _fail("party_registry_artifact_unexpected", artifact_id=artifact.source_artifact_id)
    if artifact.current_revision_id is None:
        _fail("party_registry_current_revision_missing")
    revision = sources.get_revision(artifact.current_revision_id)
    if revision is None:
        _fail("party_registry_source_revision_missing", revision_id=artifact.current_revision_id)
    if revision.source_artifact_id != PARTY_REGISTRY_ARTIFACT_ID:
        _fail(
            "party_registry_source_revision_artifact_mismatch",
            revision_id=artifact.current_revision_id,
        )

    target_ids: list[str] = []
    for object_id in PC_OBJECT_IDS:
        metadata = object_by_id[object_id].assertion_metadata
        if len(metadata.evidence_ref_ids) != 1:
            _fail("unexpected_existence_evidence", object_id=object_id)
        evidence_id = metadata.evidence_ref_ids[0]
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            _fail("missing_existence_evidence", object_id=object_id, evidence_ref_id=evidence_id)
        if (
            evidence.source_artifact_id != PARTY_REGISTRY_ARTIFACT_ID
            or evidence.source_revision_id != artifact.current_revision_id
            or evidence.source_domain is not SourceDomain.OTHER
            or evidence.source_domain_key != "other"
        ):
            _fail(
                "unexpected_party_registry_mismatch",
                object_id=object_id,
                evidence_ref_id=evidence_id,
            )
        target_ids.append(evidence_id)
    if len(set(target_ids)) != len(target_ids):
        _fail("shared_target_evidence")

    payload = copy.deepcopy(parent.graph_payload)
    target_set = set(target_ids)
    for record in payload["evidence_refs"]:
        if record["evidence_ref_id"] in target_set:
            record["source_domain_key"] = artifact.source_domain_key
    try:
        transformed = UnionGraphV6Payload.model_validate(payload)
    except (TypeError, ValidationError, ValueError):
        _fail("transformed_payload_validation")
    changed = {
        record.evidence_ref_id
        for record in transformed.evidence_refs
        if record.evidence_ref_id in target_set and record.source_domain_key == "party_registry"
    }
    if changed != target_set:
        _fail("target_evidence_not_repaired")
    child_id = compute_revision_id(
        world_id=ELDYRWILD_WORLD_ID,
        parent_revision_id=parent.revision.revision_id,
        operation_ids=[OPERATION_ID],
        graph_schema=parent.revision.graph_schema,
        graph_payload_sha256=canonical_sha256(payload),
    )
    return PartyRegistryProvenanceMaterialization(
        parent_revision_id=parent.revision.revision_id,
        graph_schema=parent.revision.graph_schema,
        graph_payload=payload,
        corrected_evidence_ref_ids=tuple(sorted(target_ids)),
        expected_child_revision_id=child_id,
    )


def publish_party_registry_provenance_repair(
    world_graph: WorldGraphRepository,
    *,
    sources: SourceRepository,
    created_at: datetime,
    expected_parent_revision_id: str = EXPECTED_PARENT_REVISION_ID,
) -> PartyRegistryProvenanceRepairResult:
    """CAS-publish once; an exact completed retry is explicitly a no-op."""
    head = world_graph.get_head(ELDYRWILD_WORLD_ID)
    if head is None:
        _fail("missing_world_head")
    parent = world_graph.get_revision(ELDYRWILD_WORLD_ID, expected_parent_revision_id)
    if parent is None:
        _fail("expected_parent_missing", revision_id=expected_parent_revision_id)
    materialized = materialize_party_registry_provenance_repair(parent, sources=sources)
    if head.head_revision_id == materialized.expected_child_revision_id:
        return PartyRegistryProvenanceRepairResult(
            parent_revision_id=expected_parent_revision_id,
            child_revision_id=materialized.expected_child_revision_id,
            corrected_evidence_ref_ids=materialized.corrected_evidence_ref_ids,
            already_applied=True,
        )
    if head.head_revision_id != expected_parent_revision_id:
        raise StaleParentRevisionError(
            world_id=ELDYRWILD_WORLD_ID,
            expected_parent_revision_id=expected_parent_revision_id,
            actual_head_revision_id=head.head_revision_id,
        )
    revision = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=ELDYRWILD_WORLD_ID,
            parent_revision_id=expected_parent_revision_id,
            expected_parent_revision_id=expected_parent_revision_id,
            operation_ids=[OPERATION_ID],
            graph_schema=materialized.graph_schema,
            graph_payload=materialized.graph_payload,
            created_at=created_at,
        )
    )
    if revision.revision_id != materialized.expected_child_revision_id:
        _fail("published_child_identity_mismatch")
    return PartyRegistryProvenanceRepairResult(
        parent_revision_id=expected_parent_revision_id,
        child_revision_id=revision.revision_id,
        corrected_evidence_ref_ids=materialized.corrected_evidence_ref_ids,
        already_applied=False,
    )
