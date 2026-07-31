"""Project pinned graph snapshots through validated provenance scope.

Exact graph labels, aliases, selected IDs, and one-hop traversal must not
bypass visibility, campaign, or provenance checks applied to evidence.

B.1a uses a coarse-object policy: an object or relationship is exposed only
when every attached evidence reference is fully validated and in scope. Mixed
provenance therefore hides the entire object rather than leaking GM-backed
aliases, summaries, or other descriptive fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.evidence import (
    EvidenceRef,
    EvidenceRole,
    SourceArtifact,
    SourceDomain,
    SourceStatus,
)
from ..contracts.projection import Admissibility
from ..contracts.vocabulary import Visibility
from .graph_snapshot import (
    GraphEvidenceRecord,
    GraphObjectView,
    GraphRelationshipView,
    ParsedGraphSnapshot,
)
from .repositories import SourceRepository


@dataclass(frozen=True)
class ProvenanceRejection:
    """Broken provenance chain that must not surface graph facts."""

    gap_code: str
    missing_id: str


@dataclass(frozen=True)
class ValidatedProvenance:
    """Fully validated evidence chain admitted for a scoped read."""

    record: GraphEvidenceRecord
    evidence: EvidenceRef
    artifact: SourceArtifact


@dataclass(frozen=True)
class ScopedGraphProjection:
    """Scoped snapshot plus broken-chain rejections collected during projection."""

    snapshot: ParsedGraphSnapshot
    rejections: list[ProvenanceRejection] = field(default_factory=list)


def source_artifact_in_scope(
    artifact: SourceArtifact,
    *,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> bool:
    """Return whether a source artifact may contribute graph facts for a turn."""
    if artifact.world_id != world_id:
        return False
    if artifact.status is not SourceStatus.ACTIVE:
        return False
    if (
        admissibility is Admissibility.PLAYER
        and artifact.visibility is not Visibility.PLAYER
    ):
        return False
    if campaign_id is None:
        # World-scoped reads exclude campaign-owned sources.
        if artifact.campaign_id is not None:
            return False
    elif artifact.campaign_id not in (None, campaign_id):
        return False
    return True


def resolve_evidence_provenance(
    evidence_ref_id: str,
    *,
    snapshot: ParsedGraphSnapshot,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> ValidatedProvenance | ProvenanceRejection | None:
    """Validate the complete evidence → artifact → revision provenance chain.

    Returns:
      * ``ValidatedProvenance`` when the chain is fully admitted for this read;
      * ``ProvenanceRejection`` when the chain is broken (caller may record a gap);
      * ``None`` when the artifact exists but is out of visibility/campaign scope
        (silent filter — not a ledger gap).
    """
    record = snapshot.evidence.get(evidence_ref_id)
    if record is None:
        return ProvenanceRejection("missing_support_evidence", evidence_ref_id)
    try:
        source_domain = SourceDomain(record.source_domain)
        evidence_role = EvidenceRole(record.evidence_role)
    except ValueError:
        return ProvenanceRejection("evidence_contract_invalid", evidence_ref_id)

    artifact = sources.get_artifact(record.source_artifact_id)
    if artifact is None:
        return ProvenanceRejection(
            "evidence_source_artifact_missing",
            record.source_artifact_id,
        )
    if artifact.status is not SourceStatus.ACTIVE:
        return ProvenanceRejection(
            "evidence_source_inactive",
            record.source_artifact_id,
        )
    if artifact.source_domain is not source_domain:
        return ProvenanceRejection("evidence_source_domain_mismatch", evidence_ref_id)
    if not source_artifact_in_scope(
        artifact,
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
    ):
        return None

    if record.source_revision_id:
        revision = sources.get_revision(record.source_revision_id)
        if revision is None:
            return ProvenanceRejection(
                "evidence_source_revision_missing",
                record.source_revision_id,
            )
        if revision.source_artifact_id != record.source_artifact_id:
            return ProvenanceRejection(
                "evidence_source_revision_artifact_mismatch",
                record.source_revision_id,
            )

    return ValidatedProvenance(
        record=record,
        evidence=EvidenceRef(
            evidence_ref_id=record.evidence_ref_id,
            source_artifact_id=record.source_artifact_id,
            source_revision_id=record.source_revision_id,
            source_domain=source_domain,
            evidence_role=evidence_role,
            can_open_source=record.can_open_source,
            can_highlight_span=record.can_highlight_span,
            locator=record.locator,
            uri=record.uri,
        ),
        artifact=artifact,
    )


def _classify_evidence_ids(
    evidence_ref_ids: list[str],
    *,
    snapshot: ParsedGraphSnapshot,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[bool, list[ProvenanceRejection]]:
    """Return whether every evidence ID is in-scope+valid, plus any rejections.

    Out-of-scope evidence (``None``) fails the coarse-object check silently.
    Broken chains fail the check and contribute ``ProvenanceRejection`` values.
    """
    rejections: list[ProvenanceRejection] = []
    all_valid_in_scope = True
    for evidence_ref_id in evidence_ref_ids:
        resolved = resolve_evidence_provenance(
            evidence_ref_id,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        if isinstance(resolved, ValidatedProvenance):
            continue
        all_valid_in_scope = False
        if isinstance(resolved, ProvenanceRejection):
            rejections.append(resolved)
    return all_valid_in_scope, rejections


def project_scoped_snapshot(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> ScopedGraphProjection:
    """Return a coarse-scoped snapshot and broken-provenance rejections.

    Coarse-object policy (B.1a): retain an object/relationship only when every
    attached evidence reference is fully validated and in scope. Mixed
    player/GM provenance therefore hides the entire object — including labels,
    aliases, and summaries — rather than leaking GM-backed descriptive fields.
    Out-of-scope evidence is filtered silently; malformed stored provenance is
    recorded as rejections for coverage.
    """
    rejections: list[ProvenanceRejection] = []
    objects: dict[str, GraphObjectView] = {}
    for object_id, obj in snapshot.objects.items():
        all_valid, object_rejections = _classify_evidence_ids(
            obj.evidence_ref_ids,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        rejections.extend(object_rejections)
        if not all_valid or not obj.evidence_ref_ids:
            continue
        objects[object_id] = obj

    relationships: dict[str, GraphRelationshipView] = {}
    for rel_id, rel in snapshot.relationships.items():
        if rel.subject_object_id not in objects or rel.object_object_id not in objects:
            continue
        all_valid, rel_rejections = _classify_evidence_ids(
            rel.evidence_ref_ids,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        rejections.extend(rel_rejections)
        if not all_valid or not rel.evidence_ref_ids:
            continue
        relationships[rel_id] = rel

    retained_evidence_ids = {
        evidence_ref_id
        for obj in objects.values()
        for evidence_ref_id in obj.evidence_ref_ids
    } | {
        evidence_ref_id
        for rel in relationships.values()
        for evidence_ref_id in rel.evidence_ref_ids
    }
    evidence = {
        evidence_ref_id: record
        for evidence_ref_id, record in snapshot.evidence.items()
        if evidence_ref_id in retained_evidence_ids
    }

    label_index: dict[str, list[str]] = {}
    alias_index: dict[str, list[str]] = {}
    for obj in objects.values():
        label_index.setdefault(obj.label.casefold().strip(), []).append(obj.object_id)
        for alias in obj.aliases:
            alias_index.setdefault(alias.casefold().strip(), []).append(obj.object_id)
    for key, ids in label_index.items():
        label_index[key] = sorted(set(ids))
    for key, ids in alias_index.items():
        alias_index[key] = sorted(set(ids))

    # Deduplicate rejections while preserving first-seen order.
    deduped: list[ProvenanceRejection] = []
    seen: set[tuple[str, str]] = set()
    for rejection in rejections:
        key = (rejection.gap_code, rejection.missing_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rejection)

    return ScopedGraphProjection(
        snapshot=ParsedGraphSnapshot(
            world_id=snapshot.world_id,
            graph_schema=snapshot.graph_schema,
            objects=objects,
            relationships=relationships,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
        ),
        rejections=deduped,
    )
