"""Project pinned graph snapshots through validated provenance scope.

Exact graph labels, aliases, selected IDs, and one-hop traversal must not
bypass visibility, campaign, or provenance checks applied to evidence.

``dm_union_graph_v1`` uses a coarse-object policy: an object or relationship is
exposed only when every attached evidence reference is fully validated and in
scope. Mixed provenance therefore hides the entire object rather than leaking
GM-backed aliases, summaries, or other descriptive fields.

``dm_union_graph_v2`` keeps core identity coarse, then admits each alias and the
summary independently from their own evidence. Omitted fields never enter
indexes, context, projections, or public diagnostics.

``dm_union_graph_v4`` moves the grain again: every assertion (object existence,
alias, summary, property, relationship) carries its own campaign scope and
visibility alongside its evidence, and each is admitted independently. A hidden
existence assertion removes the object and everything hanging off it; a hidden
alias/summary/property leaves the object standing without that field; a hidden
relationship is not traversable. Campaign filtering never leaks another
campaign's assertions, and hidden assertions are excluded silently (no
identifiers in public diagnostics).

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
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.projection import Admissibility
from ..contracts.vocabulary import Visibility
from .graph_snapshot import (
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    AdmittedAliasAssertion,
    AdmittedPropertyAssertion,
    AdmittedSummaryAssertion,
    GraphEvidenceRecord,
    GraphObjectView,
    GraphRelationshipView,
    ParsedGraphSnapshot,
    build_label_and_alias_indexes,
    contains_exact_phrase,
)
from .repositories import SourceRepository

# Public gap code for corruption whose scope cannot be established, or when
# detailed identity must not appear in MindTurnResponse.coverage.
STORED_PROVENANCE_INVALID = "stored_provenance_invalid"


def _norm_alias(text: str) -> str:
    return text.casefold().strip()


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
    """Scoped snapshot plus per-object / per-assertion exclusion diagnostics."""

    snapshot: ParsedGraphSnapshot
    object_exclusions: dict[str, ObjectScopeExclusion] = field(default_factory=dict)
    relationship_exclusions: dict[str, ObjectScopeExclusion] = field(
        default_factory=dict
    )
    assertion_exclusions: dict[str, ObjectScopeExclusion] = field(default_factory=dict)
    # Normalized omitted alias text → object IDs that lost that alias. Internal
    # only: used to stop semantic candidate seeding from revealing a hidden
    # alias→object association. Never copied into public coverage/diagnostics.
    omitted_alias_index: dict[str, list[str]] = field(default_factory=dict)

    @property
    def rejections(self) -> list[ProvenanceRejection]:
        """Flat in-scope rejections (tests / internal). Not for public coverage."""
        items: list[ProvenanceRejection] = []
        seen: set[tuple[str, str]] = set()
        for exclusion in (
            *self.object_exclusions.values(),
            *self.relationship_exclusions.values(),
            *self.assertion_exclusions.values(),
        ):
            for rejection in exclusion.rejections:
                key = (rejection.gap_code, rejection.missing_id)
                if key in seen:
                    continue
                seen.add(key)
                items.append(rejection)
        return items


def objects_blocked_by_omitted_aliases(
    message: str,
    omitted_alias_index: dict[str, list[str]],
) -> set[str]:
    """Object IDs that must not be seeded from semantic candidates for this message.

    When the caller message contains an exact phrase matching an omitted alias,
    candidate retrieval must not recover that object — otherwise a dense hit on
    a player-visible document would reveal the hidden alias→object association.
    """
    if not omitted_alias_index:
        return set()
    normalized = _norm_alias(message)
    blocked: set[str] = set()
    for alias, object_ids in omitted_alias_index.items():
        if alias and contains_exact_phrase(normalized, alias):
            blocked.update(object_ids)
    return blocked


def objects_blocked_by_ambiguous_aliases(
    message: str,
    alias_index: dict[str, list[str]],
) -> set[str]:
    """Object IDs blocked when the message matches an admitted multi-object alias.

    Exact alias ambiguity must stay AMBIGUOUS: semantic candidates must not seed
    either object into projections, evidence, or agent context.
    """
    if not alias_index:
        return set()
    normalized = _norm_alias(message)
    blocked: set[str] = set()
    for alias, object_ids in alias_index.items():
        if alias and contains_exact_phrase(normalized, alias) and len(object_ids) > 1:
            blocked.update(object_ids)
    return blocked


def filter_candidate_object_ids(
    candidate_object_ids: list[str],
    *,
    message: str,
    omitted_alias_index: dict[str, list[str]],
    alias_index: dict[str, list[str]] | None = None,
) -> list[str]:
    """Drop candidate IDs blocked by omitted-alias or admitted-alias ambiguity."""
    blocked = objects_blocked_by_omitted_aliases(message, omitted_alias_index)
    if alias_index is not None:
        blocked |= objects_blocked_by_ambiguous_aliases(message, alias_index)
    if not blocked:
        return list(candidate_object_ids)
    return [object_id for object_id in candidate_object_ids if object_id not in blocked]


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


def _project_v1_objects(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[dict[str, GraphObjectView], dict[str, ObjectScopeExclusion]]:
    """Coarse-object policy for ``dm_union_graph_v1``."""
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
    return objects, object_exclusions


def _project_v2_objects(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[
    dict[str, GraphObjectView],
    dict[str, ObjectScopeExclusion],
    dict[str, ObjectScopeExclusion],
    dict[str, list[str]],
]:
    """Core-coarse + independent alias/summary admission for v2."""
    object_exclusions: dict[str, ObjectScopeExclusion] = {}
    assertion_exclusions: dict[str, ObjectScopeExclusion] = {}
    omitted_alias_index: dict[str, list[str]] = {}
    objects: dict[str, GraphObjectView] = {}

    def _record_omitted_alias(alias: str, owner_object_id: str) -> None:
        key = _norm_alias(alias)
        if not key:
            return
        owners = omitted_alias_index.setdefault(key, [])
        if owner_object_id not in owners:
            owners.append(owner_object_id)

    for object_id, obj in snapshot.objects.items():
        core_ids = list(obj.core_evidence_ref_ids)
        all_valid, exclusion = _classify_evidence_ids(
            core_ids,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        if not all_valid or not core_ids:
            if not core_ids:
                object_exclusions[object_id] = ObjectScopeExclusion(scope_unknown=True)
            else:
                object_exclusions[object_id] = exclusion
            continue

        admitted_aliases: list[AdmittedAliasAssertion] = []
        for assertion in obj.admitted_alias_assertions:
            alias_ok, alias_exclusion = _classify_evidence_ids(
                assertion.evidence_ref_ids,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            if alias_ok and assertion.evidence_ref_ids:
                admitted_aliases.append(assertion)
            else:
                _record_omitted_alias(assertion.alias, object_id)
                if not assertion.evidence_ref_ids:
                    assertion_exclusions[assertion.assertion_id] = ObjectScopeExclusion(
                        scope_unknown=True
                    )
                else:
                    assertion_exclusions[assertion.assertion_id] = alias_exclusion

        admitted_summary: AdmittedSummaryAssertion | None = None
        if obj.admitted_summary_assertion is not None:
            summary = obj.admitted_summary_assertion
            summary_ok, summary_exclusion = _classify_evidence_ids(
                summary.evidence_ref_ids,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            if summary_ok and summary.evidence_ref_ids:
                admitted_summary = summary
            elif not summary.evidence_ref_ids:
                assertion_exclusions[summary.assertion_id] = ObjectScopeExclusion(
                    scope_unknown=True
                )
            else:
                assertion_exclusions[summary.assertion_id] = summary_exclusion

        retained_evidence = list(core_ids)
        for assertion in admitted_aliases:
            retained_evidence.extend(assertion.evidence_ref_ids)
        if admitted_summary is not None:
            retained_evidence.extend(admitted_summary.evidence_ref_ids)

        objects[object_id] = GraphObjectView(
            object_id=obj.object_id,
            kind=obj.kind,
            label=obj.label,
            aliases=[item.alias for item in admitted_aliases],
            evidence_ref_ids=list(dict.fromkeys(retained_evidence)),
            summary=admitted_summary.summary if admitted_summary is not None else None,
            object_field_schema="v2",
            core_evidence_ref_ids=list(core_ids),
            admitted_alias_assertions=admitted_aliases,
            admitted_summary_assertion=admitted_summary,
        )

    return objects, object_exclusions, assertion_exclusions, omitted_alias_index


def assertion_metadata_in_scope(
    metadata: KnowledgeAssertionMetadataV1 | None,
    *,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> bool:
    """Whether one v4 assertion's own scope admits it for this read.

    Two independent gates, both fail-closed:

    * **Campaign.** ``campaign_scope is None`` is world-universal knowledge and
      always passes. Otherwise it must equal the caller's ``campaign_id``; a
      world-scoped read (``campaign_id is None``) never sees campaign-scoped
      assertions, and no read ever sees another campaign's assertions.
    * **Visibility.** A player-admissible read requires
      ``Visibility.PLAYER``; GM reads see both.

    ``None`` metadata means the assertion predates v4 (v1-v3 views), where
    scope lives on the evidence chain alone — those reads are unaffected.
    """
    if metadata is None:
        return True
    if metadata.campaign_scope is not None and metadata.campaign_scope != campaign_id:
        return False
    return not (
        admissibility is Admissibility.PLAYER
        and metadata.visibility is not Visibility.PLAYER
    )


def _admit_v4_assertion(
    metadata: KnowledgeAssertionMetadataV1,
    *,
    snapshot: ParsedGraphSnapshot,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[bool, ObjectScopeExclusion]:
    """Assertion-scope gate first, then the existing evidence provenance chain.

    Assertion-scope failures are silent (``out_of_scope``) so campaign and
    audience filtering never emit identifiers a caller is not entitled to.
    """
    if not assertion_metadata_in_scope(
        metadata, campaign_id=campaign_id, admissibility=admissibility
    ):
        return False, ObjectScopeExclusion(out_of_scope=True)
    if not metadata.evidence_ref_ids:
        return False, ObjectScopeExclusion(scope_unknown=True)
    return _classify_evidence_ids(
        metadata.evidence_ref_ids,
        snapshot=snapshot,
        sources=sources,
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
    )


def _project_v4_objects(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> tuple[
    dict[str, GraphObjectView],
    dict[str, ObjectScopeExclusion],
    dict[str, ObjectScopeExclusion],
    dict[str, list[str]],
]:
    """Independent admission of every ``dm_union_graph_v4`` assertion."""
    object_exclusions: dict[str, ObjectScopeExclusion] = {}
    assertion_exclusions: dict[str, ObjectScopeExclusion] = {}
    omitted_alias_index: dict[str, list[str]] = {}
    objects: dict[str, GraphObjectView] = {}

    for object_id, obj in snapshot.objects.items():
        existence = obj.existence_assertion_metadata
        if existence is None:
            # A v4 snapshot without an existence assertion cannot be scoped.
            object_exclusions[object_id] = ObjectScopeExclusion(scope_unknown=True)
            continue
        existence_ok, existence_exclusion = _admit_v4_assertion(
            existence,
            snapshot=snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
        if not existence_ok:
            object_exclusions[object_id] = existence_exclusion
            continue

        admitted_aliases: list[AdmittedAliasAssertion] = []
        omitted_alias_values: list[str] = []
        for alias in obj.admitted_alias_assertions:
            assert alias.assertion_metadata is not None
            alias_ok, alias_exclusion = _admit_v4_assertion(
                alias.assertion_metadata,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            if alias_ok:
                admitted_aliases.append(alias)
                continue
            omitted_alias_values.append(alias.alias)
            assertion_exclusions[alias.assertion_id] = alias_exclusion

        admitted_summary: AdmittedSummaryAssertion | None = None
        if obj.admitted_summary_assertion is not None:
            summary = obj.admitted_summary_assertion
            assert summary.assertion_metadata is not None
            summary_ok, summary_exclusion = _admit_v4_assertion(
                summary.assertion_metadata,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            if summary_ok:
                admitted_summary = summary
            else:
                assertion_exclusions[summary.assertion_id] = summary_exclusion

        admitted_properties: list[AdmittedPropertyAssertion] = []
        for prop in obj.admitted_property_assertions:
            assert prop.assertion_metadata is not None
            property_ok, property_exclusion = _admit_v4_assertion(
                prop.assertion_metadata,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                campaign_id=campaign_id,
                admissibility=admissibility,
            )
            if property_ok:
                admitted_properties.append(prop)
            else:
                assertion_exclusions[prop.assertion_id] = property_exclusion

        # Another assertion may still admit the same alias text; only record a
        # value as omitted when nothing admitted recovers it.
        admitted_alias_values = {_norm_alias(item.alias) for item in admitted_aliases}
        for value in omitted_alias_values:
            key = _norm_alias(value)
            if not key or key in admitted_alias_values:
                continue
            owners = omitted_alias_index.setdefault(key, [])
            if object_id not in owners:
                owners.append(object_id)

        retained_evidence = list(existence.evidence_ref_ids)
        for alias in admitted_aliases:
            retained_evidence.extend(alias.evidence_ref_ids)
        if admitted_summary is not None:
            retained_evidence.extend(admitted_summary.evidence_ref_ids)
        for prop in admitted_properties:
            retained_evidence.extend(prop.evidence_ref_ids)

        objects[object_id] = GraphObjectView(
            object_id=obj.object_id,
            kind=obj.kind,
            label=obj.label,
            aliases=list(dict.fromkeys(item.alias for item in admitted_aliases)),
            evidence_ref_ids=list(dict.fromkeys(retained_evidence)),
            summary=admitted_summary.summary if admitted_summary is not None else None,
            object_field_schema="v4",
            core_evidence_ref_ids=list(existence.evidence_ref_ids),
            admitted_alias_assertions=admitted_aliases,
            admitted_summary_assertion=admitted_summary,
            existence_assertion_metadata=existence,
            admitted_property_assertions=admitted_properties,
        )

    return objects, object_exclusions, assertion_exclusions, omitted_alias_index


def project_scoped_snapshot(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceRepository,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
) -> ScopedGraphProjection:
    """Return a scoped snapshot and exclusion diagnostics.

    V1 keeps the B.1a coarse-object policy. V2/V3 retain the object shell when
    core evidence is admitted, then filter each alias and summary independently.
    V4 filters every assertion by its own campaign scope and visibility before
    the same evidence-provenance checks.

    Graph-global exclusions are retained per object/relationship/assertion for
    callers that need targeted diagnostics. They must not be copied wholesale
    into public ``Coverage`` on every turn.
    """
    assertion_exclusions: dict[str, ObjectScopeExclusion] = {}
    omitted_alias_index: dict[str, list[str]] = {}
    if snapshot.graph_schema == GRAPH_SCHEMA_V4:
        (
            objects,
            object_exclusions,
            assertion_exclusions,
            omitted_alias_index,
        ) = _project_v4_objects(
            snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
    elif snapshot.graph_schema in (GRAPH_SCHEMA_V2, GRAPH_SCHEMA_V3):
        (
            objects,
            object_exclusions,
            assertion_exclusions,
            omitted_alias_index,
        ) = _project_v2_objects(
            snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )
    else:
        objects, object_exclusions = _project_v1_objects(
            snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
        )

    relationship_exclusions: dict[str, ObjectScopeExclusion] = {}
    relationships: dict[str, GraphRelationshipView] = {}
    for rel_id, rel in snapshot.relationships.items():
        if rel.subject_object_id not in objects or rel.object_object_id not in objects:
            relationship_exclusions[rel_id] = ObjectScopeExclusion(out_of_scope=True)
            continue
        # V4 only: the relationship's own campaign/visibility scope. ``None``
        # metadata (v1-v3) leaves this a no-op.
        if not assertion_metadata_in_scope(
            rel.assertion_metadata,
            campaign_id=campaign_id,
            admissibility=admissibility,
        ):
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

    label_index, alias_index = build_label_and_alias_indexes(objects)

    return ScopedGraphProjection(
        snapshot=ParsedGraphSnapshot(
            world_id=snapshot.world_id,
            graph_schema=snapshot.graph_schema,
            objects=objects,
            relationships=relationships,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
            semantic_profile_ref=snapshot.semantic_profile_ref,
            semantic_profile_descriptor=snapshot.semantic_profile_descriptor,
        ),
        object_exclusions=object_exclusions,
        relationship_exclusions=relationship_exclusions,
        assertion_exclusions=assertion_exclusions,
        omitted_alias_index=omitted_alias_index,
    )
