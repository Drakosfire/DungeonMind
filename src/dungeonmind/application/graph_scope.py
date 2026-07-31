"""Project pinned graph snapshots through validated provenance scope.

Exact graph labels, aliases, selected IDs, and one-hop traversal must not
bypass visibility, campaign, or provenance checks applied to evidence.

B.1a uses a coarse-object policy: an object or relationship is exposed only
when every attached evidence reference is fully validated and in scope. Mixed
provenance therefore hides the entire object rather than leaking GM-backed
aliases, summaries, or other descriptive fields.

Admissibility filtering is separated from provenance diagnostics:
out-of-scope artifacts are excluded silently; detailed rejection identities are
emitted only for artifacts already proven visible to the caller. Missing
artifacts (scope unestablishable) never expose their identifiers in public
coverage — they surface only as generic ``stored_provenance_invalid`` when a
request actually targets the affected object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

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

# Public gap code for corruption whose scope cannot be established, or when
# detailed identity must not appear in MindTurnResponse.coverage.
STORED_PROVENANCE_INVALID = "stored_provenance_invalid"


class EvidenceScopeVerdict(StrEnum):
    """Sentinel returned when artifact visibility cannot be established."""

    SCOPE_UNKNOWN = "scope_unknown"


@dataclass(frozen=True)
class ProvenanceRejection:
    """Broken provenance chain on an artifact already visible to the caller.

    ``missing_id`` may identify a source/revision/evidence record because the
    caller is authorized to know that artifact exists. Never construct this for
    out-of-scope or scope-unknown chains.
    """

    gap_code: str
    missing_id: str


@dataclass(frozen=True)
class ValidatedProvenance:
    """Fully validated evidence chain admitted for a scoped read."""

    record: GraphEvidenceRecord
    evidence: EvidenceRef
    artifact: SourceArtifact


@dataclass(frozen=True)
class ObjectScopeExclusion:
    """Why a graph object/relationship was hidden by coarse scoping.

    Detailed ``rejections`` are only populated for in-scope broken provenance.
    ``scope_unknown`` means at least one chain could not establish visibility
    (missing artifact/record) — public responses must not echo those IDs.
    """

    rejections: list[ProvenanceRejection] = field(default_factory=list)
    out_of_scope: bool = False
    scope_unknown: bool = False


@dataclass(frozen=True)
class ScopedGraphProjection:
    """Scoped snapshot plus per-object exclusion diagnostics."""

    snapshot: ParsedGraphSnapshot
    object_exclusions: dict[str, ObjectScopeExclusion] = field(default_factory=dict)
    relationship_exclusions: dict[str, ObjectScopeExclusion] = field(
        default_factory=dict
    )

    @property
    def rejections(self) -> list[ProvenanceRejection]:
        """Flat in-scope rejections (tests / internal). Not for public coverage."""
        items: list[ProvenanceRejection] = []
        seen: set[tuple[str, str]] = set()
        for exclusion in (
            *self.object_exclusions.values(),
            *self.relationship_exclusions.values(),
        ):
            for rejection in exclusion.rejections:
                key = (rejection.gap_code, rejection.missing_id)
                if key in seen:
                    continue
                seen.add(key)
                items.append(rejection)
        return items


def source_artifact_in_scope(
    artifact: SourceArtifact,
    *,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> bool:
    """Return whether a source artifact is visible for this turn's scope.

    Checks world, campaign, and visibility only. Lifecycle (ACTIVE/retracted)
    is a provenance concern handled after scope is established — inspecting
    status before visibility would leak hidden source identities into public
    coverage diagnostics.
    """
    if artifact.world_id != world_id:
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
) -> ValidatedProvenance | ProvenanceRejection | EvidenceScopeVerdict | None:
    """Validate the complete evidence → artifact → revision provenance chain.

    Returns:
      * ``ValidatedProvenance`` when the chain is fully admitted for this read;
      * ``ProvenanceRejection`` when the artifact is in scope but the chain is
        broken (detailed gap — safe for authorized callers);
      * ``None`` when the artifact exists but is out of visibility/campaign/world
        scope (silent filter — no lifecycle/domain inspection for diagnostics);
      * ``EvidenceScopeVerdict.SCOPE_UNKNOWN`` when scope cannot be established
        (missing artifact/record) — never expose those identifiers publicly.
    """
    record = snapshot.evidence.get(evidence_ref_id)
    if record is None:
        # Cannot establish artifact visibility without a stored evidence row.
        return EvidenceScopeVerdict.SCOPE_UNKNOWN

    try:
        source_domain = SourceDomain(record.source_domain)
        evidence_role = EvidenceRole(record.evidence_role)
    except ValueError:
        # Contract enums failed on a graph row; treat as integrity without IDs
        # until the owning object is targeted (public code is generic).
        return EvidenceScopeVerdict.SCOPE_UNKNOWN

    artifact = sources.get_artifact(record.source_artifact_id)
    if artifact is None:
        # Missing artifact: visibility unknown — silent exclusion, no ID leak.
        return EvidenceScopeVerdict.SCOPE_UNKNOWN

    # Admissibility / campaign / world FIRST — before lifecycle or domain.
    if not source_artifact_in_scope(
        artifact,
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
    ):
        return None

    # Artifact is proven visible — detailed provenance diagnostics are allowed.
    if artifact.status is not SourceStatus.ACTIVE:
        return ProvenanceRejection(
            "evidence_source_inactive",
            record.source_artifact_id,
        )
    if artifact.source_domain is not source_domain:
        return ProvenanceRejection("evidence_source_domain_mismatch", evidence_ref_id)

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


def public_coverage_gaps_for_exclusion(
    exclusion: ObjectScopeExclusion,
) -> tuple[list[str], list[str]]:
    """Map an exclusion to public ``gap_codes`` / ``missing`` entries.

    Out-of-scope-only exclusions yield nothing (silent). Scope-unknown
    corruption yields a generic gap without identifiers. In-scope broken
    chains may expose their detailed codes and IDs.
    """
    if exclusion.scope_unknown:
        return [STORED_PROVENANCE_INVALID], []
    if exclusion.rejections:
        codes = [r.gap_code for r in exclusion.rejections]
        missing = [r.missing_id for r in exclusion.rejections]
        return codes, missing
    # Pure out-of-scope: silent.
    return [], []


def _classify_evidence_ids(
    evidence_ref_ids: list[str],
    *,
    snapshot: ParsedGraphSnapshot,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[bool, ObjectScopeExclusion]:
    """Return whether every evidence ID is in-scope+valid, plus exclusion info."""
    rejections: list[ProvenanceRejection] = []
    out_of_scope = False
    scope_unknown = False
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
        if resolved is None:
            out_of_scope = True
        elif resolved is EvidenceScopeVerdict.SCOPE_UNKNOWN:
            scope_unknown = True
        elif isinstance(resolved, ProvenanceRejection):
            rejections.append(resolved)
    # Deduplicate rejections while preserving order.
    deduped: list[ProvenanceRejection] = []
    seen: set[tuple[str, str]] = set()
    for rejection in rejections:
        key = (rejection.gap_code, rejection.missing_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rejection)
    return all_valid_in_scope, ObjectScopeExclusion(
        rejections=deduped,
        out_of_scope=out_of_scope,
        scope_unknown=scope_unknown,
    )


def project_scoped_snapshot(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> ScopedGraphProjection:
    """Return a coarse-scoped snapshot and per-object exclusion diagnostics.

    Coarse-object policy (B.1a): retain an object/relationship only when every
    attached evidence reference is fully validated and in scope. Mixed
    player/GM provenance therefore hides the entire object — including labels,
    aliases, and summaries — rather than leaking GM-backed descriptive fields.

    Graph-global exclusions are retained per object/relationship for callers
    that need targeted diagnostics. They must not be copied wholesale into
    public ``Coverage`` on every turn.
    """
    object_exclusions: dict[str, ObjectScopeExclusion] = {}
    objects: dict[str, GraphObjectView] = {}
    for object_id, obj in snapshot.objects.items():
        all_valid, exclusion = _classify_evidence_ids(
            obj.evidence_ref_ids,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        if not all_valid or not obj.evidence_ref_ids:
            if not obj.evidence_ref_ids:
                object_exclusions[object_id] = ObjectScopeExclusion(scope_unknown=True)
            else:
                object_exclusions[object_id] = exclusion
            continue
        objects[object_id] = obj

    relationship_exclusions: dict[str, ObjectScopeExclusion] = {}
    relationships: dict[str, GraphRelationshipView] = {}
    for rel_id, rel in snapshot.relationships.items():
        if rel.subject_object_id not in objects or rel.object_object_id not in objects:
            relationship_exclusions[rel_id] = ObjectScopeExclusion(out_of_scope=True)
            continue
        all_valid, exclusion = _classify_evidence_ids(
            rel.evidence_ref_ids,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        if not all_valid or not rel.evidence_ref_ids:
            if not rel.evidence_ref_ids:
                relationship_exclusions[rel_id] = ObjectScopeExclusion(
                    scope_unknown=True
                )
            else:
                relationship_exclusions[rel_id] = exclusion
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
        object_exclusions=object_exclusions,
        relationship_exclusions=relationship_exclusions,
    )
