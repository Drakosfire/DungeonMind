"""Project pinned graph snapshots through world/campaign/admissibility scope.

Exact graph labels, aliases, selected IDs, and one-hop traversal must not
bypass the same visibility and campaign filters applied to semantic search.
Object and relationship visibility is derived from linked source artifacts.
"""

from __future__ import annotations

from ..contracts.evidence import SourceArtifact, SourceStatus
from ..contracts.projection import Admissibility
from ..contracts.vocabulary import Visibility
from .graph_snapshot import (
    GraphObjectView,
    GraphRelationshipView,
    ParsedGraphSnapshot,
)
from .repositories import SourceRepository


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


def evidence_ref_in_scope(
    *,
    evidence_ref_id: str,
    snapshot: ParsedGraphSnapshot,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> bool:
    record = snapshot.evidence.get(evidence_ref_id)
    if record is None:
        return False
    artifact = sources.get_artifact(record.source_artifact_id)
    if artifact is None:
        return False
    return source_artifact_in_scope(
        artifact,
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
    )


def project_scoped_snapshot(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> ParsedGraphSnapshot:
    """Return a snapshot containing only objects/relationships in scope.

    An object or relationship is retained when at least one attached evidence
    reference resolves to an in-scope source artifact. Relationships also
    require both endpoints to remain after object filtering.
    """

    def _readable_evidence(evidence_ref_ids: list[str]) -> bool:
        return any(
            evidence_ref_in_scope(
                evidence_ref_id=evidence_ref_id,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            for evidence_ref_id in evidence_ref_ids
        )

    objects: dict[str, GraphObjectView] = {
        object_id: obj
        for object_id, obj in snapshot.objects.items()
        if _readable_evidence(obj.evidence_ref_ids)
    }
    relationships: dict[str, GraphRelationshipView] = {
        rel_id: rel
        for rel_id, rel in snapshot.relationships.items()
        if rel.subject_object_id in objects
        and rel.object_object_id in objects
        and _readable_evidence(rel.evidence_ref_ids)
    }
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

    return ParsedGraphSnapshot(
        world_id=snapshot.world_id,
        graph_schema=snapshot.graph_schema,
        objects=objects,
        relationships=relationships,
        evidence=evidence,
        label_index=label_index,
        alias_index=alias_index,
    )
