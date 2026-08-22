"""Transport-neutral direct World Graph retrieval primitives (cutover lane R.2).

This module is the DungeonMind-native graph-semantic retrieval seam. Every
operation composes the landed v2 projection authority exactly once:

``WorldGraphProjectionRequestV2`` + operation inputs
→ ``WorldGraphProjectionService.project`` (one exact scoped revision)
→ deterministic graph-only primitives over the admitted projection
→ immutable per-operation results carrying the exact ``ProjectionSnapshotV2``

Five capabilities are owned here so product surfaces can retire their legacy
kernel reads:

* exact object lookup by stable object ID (explicit miss, no search fallback);
* deterministic graph-only search / referent resolution over admitted IDs,
  labels, aliases, kinds, summaries, property term/value text, relationship
  predicates, and related-object labels — no vector store, semantic index,
  LLM, or file-search fallback anywhere in this module;
* bounded depth-1/depth-2 neighborhood expansion over 1-8 exact seeds;
* evidence retrieval by native object / relationship / assertion identity
  with per-chain provenance revalidation;
* admitted source-anchor derivation plus opaque, context-bound revalidation.

Retrieval may narrow or rank the admitted projection; it never broadens scope
and never recovers rows the projection excluded. No operation opens source
body content, reconstructs a foreign graph store, or mutates durable state.
Anchor identity is bound to the complete v2 read context: the same admitted
provenance under the same exact context yields the same opaque anchor ID, and
changing any bound input (revision, campaign/scope mode, focus, admissibility,
evidence/source identity, locator identity) makes the old anchor unresolvable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

from ..contracts.evidence import EvidenceRef, EvidenceRefV2, SourceArtifactRecord
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.projection_v2 import ProjectionSnapshotV2, WorldGraphProjectionRequestV2
from ..contracts.retrieval import ResolvedReferent
from ..domain.canonical import canonical_json, canonical_sha256
from .graph_scope import (
    STORED_PROVENANCE_INVALID,
    EvidenceScopeVerdict,
    ProvenanceRejection,
    ValidatedProvenance,
    objects_blocked_by_ambiguous_aliases,
    objects_blocked_by_omitted_aliases,
    public_coverage_gaps_for_exclusion,
    resolve_evidence_provenance,
)
from .graph_snapshot import (
    GraphEvidenceLedgerRecord,
    GraphObjectView,
    GraphRelationshipView,
    contains_exact_phrase,
    resolve_mentions_from_snapshot,
)
from .repositories import SourceRepository
from .world_graph_projection import (
    WorldGraphProjectionResult,
    WorldGraphProjectionService,
)

SOURCE_ANCHOR_SCHEMA = "dm_source_anchor_v1"
SOURCE_ANCHOR_ID_PREFIX = "dm-source-anchor:v1:"

MAX_SEED_OBJECT_IDS = 8
MAX_NEIGHBORHOOD_DEPTH = 2

_OBJECTS_LIMIT = 12
_RELATIONSHIPS_LIMIT = 24
_ASSERTIONS_LIMIT = 32
_ANCHORS_LIMIT = 32

# Deterministic lexical ranking weights. Exact identity dominates phrasal
# matches, which dominate per-token matches; an explicit exact seed dominates
# everything. Ordering is fully deterministic: (-score, object_id).
_SCORE_EXACT_SEED = 1_000_000
_SCORE_EXACT_OBJECT_ID = 1_000
_SCORE_EXACT_LABEL = 900
_SCORE_EXACT_ALIAS = 850
_SCORE_LABEL_PHRASE = 700
_SCORE_ALIAS_PHRASE = 650
_SCORE_KIND_PHRASE = 500
_SCORE_SUMMARY_PHRASE = 300
_SCORE_PROPERTY_PHRASE = 250
_SCORE_OBJECT_BLOB_PHRASE = 200
_SCORE_RELATIONSHIP_PHRASE = 160
_SCORE_TOKEN_OBJECT_ID = 120
_SCORE_TOKEN_LABEL = 100
_SCORE_TOKEN_ALIAS = 90
_SCORE_TOKEN_KIND = 80
_SCORE_TOKEN_PROPERTY = 60
_SCORE_TOKEN_SUMMARY = 50
_SCORE_TOKEN_RELATIONSHIP = 45

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Noise words never scored as lexical tokens.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall", "can",
        "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
        "i", "me", "my", "we", "our", "you", "your", "they", "their", "it",
        "its", "this", "that", "these", "those", "am", "about", "into",
        "through", "during", "before", "after", "above", "below", "between",
        "under", "again",
    }
)


@dataclass(frozen=True)
class RetrievalBounds:
    """Explicit per-operation result caps. Truncation is always reported."""

    max_objects: int = 8
    max_relationships: int = 16
    max_assertions: int = 24
    max_anchors: int = 24

    def __post_init__(self) -> None:
        for name, value, limit in (
            ("max_objects", self.max_objects, _OBJECTS_LIMIT),
            ("max_relationships", self.max_relationships, _RELATIONSHIPS_LIMIT),
            ("max_assertions", self.max_assertions, _ASSERTIONS_LIMIT),
            ("max_anchors", self.max_anchors, _ANCHORS_LIMIT),
        ):
            if not 1 <= value <= limit:
                raise ValueError(f"{name} must be within 1..{limit}")


@dataclass(frozen=True)
class RetrievalCoverage:
    """Explicit missing/truncation/provenance coverage for one operation.

    ``missing_seed_object_ids`` echoes only caller-supplied seed IDs.
    ``gap_codes`` / ``missing_ids`` carry public-safe provenance diagnostics:
    in-scope broken chains may name their codes and record IDs, while
    out-of-scope and scope-unknown exclusions never echo identifiers.
    """

    requested_seed_object_ids: tuple[str, ...] = ()
    missing_seed_object_ids: tuple[str, ...] = ()
    truncated_fields: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    missing_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmittedAssertionValue:
    """One admitted assertion row in native DungeonMind semantics.

    Property assertions populate ``property_term`` / ``property_value`` so a
    product adapter can rebuild its claim ledger (assertion ID, subject object,
    property term/value, assertion metadata, evidence refs) without consulting
    any foreign kernel. Other assertion kinds carry identity plus evidence.
    """

    assertion_id: str
    subject_object_id: str
    assertion_kind: Literal[
        "existence", "alias", "summary", "property", "aspect", "relationship"
    ]
    evidence_ref_ids: tuple[str, ...]
    assertion_metadata: KnowledgeAssertionMetadataV1 | None
    property_term: str | None = None
    property_value: Any = None


@dataclass(frozen=True)
class SourceAnchorMetadata:
    """Admitted source-anchor identity plus the records a product opener needs.

    Carries already-admitted evidence/source identity only. No source body
    content is ever read or returned by this service, and callers can never
    supply a path, URI, locator, or source revision through this type.
    """

    anchor_id: str
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None
    locator_identity: str
    source_span_ref_id: str | None
    can_open_source: bool
    can_highlight_span: bool
    supporting_object_ids: tuple[str, ...]
    supporting_assertion_ids: tuple[str, ...]
    evidence: EvidenceRef | EvidenceRefV2
    artifact: SourceArtifactRecord


@dataclass(frozen=True)
class EvidenceTarget:
    """Native DungeonMind identity of an evidence retrieval target."""

    kind: Literal["object", "relationship", "assertion"]
    target_id: str

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("evidence target_id must be non-blank")


@dataclass(frozen=True)
class ObjectLookupResult:
    snapshot: ProjectionSnapshotV2
    found: bool
    object: GraphObjectView | None
    relationships: tuple[GraphRelationshipView, ...] = ()
    property_assertions: tuple[AdmittedAssertionValue, ...] = ()
    anchors: tuple[SourceAnchorMetadata, ...] = ()
    coverage: RetrievalCoverage = field(default_factory=RetrievalCoverage)


@dataclass(frozen=True)
class GraphSearchResult:
    """Deterministic graph-only search result over one exact projection."""

    snapshot: ProjectionSnapshotV2
    referents: tuple[ResolvedReferent, ...]
    matched_object_ids: tuple[str, ...]
    match_reasons: dict[str, tuple[str, ...]]
    objects: tuple[GraphObjectView, ...]
    relationships: tuple[GraphRelationshipView, ...]
    property_assertions: tuple[AdmittedAssertionValue, ...]
    anchors: tuple[SourceAnchorMetadata, ...]
    coverage: RetrievalCoverage


@dataclass(frozen=True)
class NeighborhoodResult:
    """Bounded BFS expansion result. ``object_depths[seed] == 0``."""

    snapshot: ProjectionSnapshotV2
    seed_object_ids: tuple[str, ...]
    object_depths: dict[str, int]
    objects: tuple[GraphObjectView, ...]
    relationships: tuple[GraphRelationshipView, ...]
    property_assertions: tuple[AdmittedAssertionValue, ...]
    anchors: tuple[SourceAnchorMetadata, ...]
    coverage: RetrievalCoverage


@dataclass(frozen=True)
class EvidenceRetrievalResult:
    snapshot: ProjectionSnapshotV2
    found: bool
    target: EvidenceTarget
    object: GraphObjectView | None = None
    relationship: GraphRelationshipView | None = None
    assertion: AdmittedAssertionValue | None = None
    evidence: tuple[EvidenceRef | EvidenceRefV2, ...] = ()
    anchors: tuple[SourceAnchorMetadata, ...] = ()
    coverage: RetrievalCoverage = field(default_factory=RetrievalCoverage)


@dataclass(frozen=True)
class SourceAnchorResolution:
    """Opaque anchor revalidation against one exact reprojected context."""

    snapshot: ProjectionSnapshotV2
    found: bool
    anchor_id: str
    anchor: SourceAnchorMetadata | None = None


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_PATTERN.findall(text.casefold())
        if len(token) > 1 and token not in _STOPWORDS
    ]


def _token_matches(token: str, text_cf: str) -> bool:
    """Boundary-aware token match with naive singular/plural tolerance."""
    if not text_cf:
        return False
    if contains_exact_phrase(text_cf, token):
        return True
    if token.endswith("s") and len(token) > 3:
        return contains_exact_phrase(text_cf, token[:-1])
    if not token.endswith("s"):
        return contains_exact_phrase(text_cf, f"{token}s")
    return False


def _value_search_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    return canonical_json(value)


def _property_search_text(obj: GraphObjectView) -> str:
    parts: list[str] = []
    for prop in obj.admitted_property_assertions:
        parts.append(prop.property_term)
        parts.append(_value_search_text(prop.value))
    return " ".join(part for part in parts if part).casefold()


def _score_object(
    obj: GraphObjectView,
    *,
    query_cf: str,
    tokens: list[str],
) -> tuple[int, list[str]]:
    if not query_cf and not tokens:
        return 0, []
    if query_cf and obj.object_id.casefold() == query_cf:
        return _SCORE_EXACT_OBJECT_ID, ["exact_object_id"]
    if query_cf and obj.label.casefold() == query_cf:
        return _SCORE_EXACT_LABEL, ["exact_label"]
    for alias in obj.aliases:
        if query_cf and alias.casefold() == query_cf:
            return _SCORE_EXACT_ALIAS, ["exact_alias"]

    score = 0
    reasons: list[str] = []
    label_cf = obj.label.casefold()
    kind_cf = obj.kind.casefold()
    summary_cf = (obj.summary or "").casefold()
    property_cf = _property_search_text(obj)
    blob_cf = " ".join(
        part
        for part in (
            label_cf,
            " ".join(alias.casefold() for alias in obj.aliases),
            kind_cf,
            summary_cf,
            property_cf,
        )
        if part
    )
    if query_cf:
        if contains_exact_phrase(label_cf, query_cf):
            score = max(score, _SCORE_LABEL_PHRASE)
            reasons.append("label_phrase")
        if any(contains_exact_phrase(alias.casefold(), query_cf) for alias in obj.aliases):
            score = max(score, _SCORE_ALIAS_PHRASE)
            reasons.append("alias_phrase")
        if contains_exact_phrase(kind_cf, query_cf):
            score = max(score, _SCORE_KIND_PHRASE)
            reasons.append("kind_phrase")
        if summary_cf and contains_exact_phrase(summary_cf, query_cf):
            score = max(score, _SCORE_SUMMARY_PHRASE)
            reasons.append("summary_phrase")
        if property_cf and contains_exact_phrase(property_cf, query_cf):
            score = max(score, _SCORE_PROPERTY_PHRASE)
            reasons.append("property_phrase")
        if blob_cf and contains_exact_phrase(blob_cf, query_cf):
            score = max(score, _SCORE_OBJECT_BLOB_PHRASE)
            reasons.append("object_blob_phrase")
    for token in tokens:
        if _token_matches(token, obj.object_id.casefold()):
            score += _SCORE_TOKEN_OBJECT_ID
            reasons.append(f"token:{token}:object_id")
        if _token_matches(token, label_cf):
            score += _SCORE_TOKEN_LABEL
            reasons.append(f"token:{token}:label")
        if any(_token_matches(token, alias.casefold()) for alias in obj.aliases):
            score += _SCORE_TOKEN_ALIAS
            reasons.append(f"token:{token}:alias")
        if _token_matches(token, kind_cf):
            score += _SCORE_TOKEN_KIND
            reasons.append(f"token:{token}:kind")
        if property_cf and _token_matches(token, property_cf):
            score += _SCORE_TOKEN_PROPERTY
            reasons.append(f"token:{token}:property")
        if summary_cf and _token_matches(token, summary_cf):
            score += _SCORE_TOKEN_SUMMARY
            reasons.append(f"token:{token}:summary")
    return score, sorted(set(reasons))


def _extend_scores_with_relationships(
    objects: dict[str, GraphObjectView],
    relationships: dict[str, GraphRelationshipView],
    query_cf: str,
    tokens: list[str],
    scores: dict[str, int],
    match_reasons: dict[str, list[str]],
) -> None:
    """Boost object scores from relationship predicate and related-object text.

    A query may only match through the *other* endpoint's label, so both
    endpoints of every admitted relationship are considered independently.
    """
    if not query_cf and not tokens:
        return
    label_by_id = {object_id: obj.label for object_id, obj in objects.items()}
    for rel in relationships.values():
        source_label = label_by_id.get(rel.subject_object_id, "")
        target_label = label_by_id.get(rel.object_object_id, "")
        for endpoint_id, related_label in (
            (rel.subject_object_id, target_label),
            (rel.object_object_id, source_label),
        ):
            if endpoint_id not in objects:
                continue
            blob_cf = " ".join(
                part for part in (rel.predicate, related_label) if part
            ).casefold()
            if not blob_cf:
                continue
            score = 0
            reasons: list[str] = []
            if query_cf and contains_exact_phrase(blob_cf, query_cf):
                score = max(score, _SCORE_RELATIONSHIP_PHRASE)
                reasons.append("relationship_or_related_object_phrase")
            for token in tokens:
                if _token_matches(token, blob_cf):
                    score += _SCORE_TOKEN_RELATIONSHIP
                    reasons.append(f"token:{token}:relationship_or_related_object")
            if score:
                scores[endpoint_id] = max(scores.get(endpoint_id, 0), score)
                match_reasons.setdefault(endpoint_id, []).extend(reasons)


def _locator_identity(record: GraphEvidenceLedgerRecord) -> str:
    """Admitted locator identity: explicit span ref first, then durable locators."""
    span = getattr(record, "source_span_ref_id", None)
    if isinstance(span, str) and span.strip():
        return span.strip()
    for name in ("locator", "uri", "source_locator", "line_ref"):
        value = getattr(record, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def derive_source_anchor_id(
    *,
    snapshot: ProjectionSnapshotV2,
    evidence_ref_id: str,
    source_artifact_id: str,
    source_revision_id: str | None,
    locator_identity: str,
) -> str:
    """Deterministically derive an opaque context-bound source anchor ID.

    The digest binds the anchor schema/version, world, campaign/scope mode,
    focus, admissibility, exact selected graph revision, evidence ref, source
    artifact, source revision (when present), and the admitted locator
    identity. Changing any bound input yields a different anchor.
    """
    payload = {
        "anchor_schema": SOURCE_ANCHOR_SCHEMA,
        "world_id": snapshot.world_id,
        "campaign_id": snapshot.campaign_id,
        "scope_mode": str(snapshot.scope_mode),
        "focus": snapshot.focus.model_dump(mode="json"),
        "admissibility": str(snapshot.admissibility),
        "revision_id": snapshot.revision_id,
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": source_artifact_id,
        "source_revision_id": source_revision_id,
        "locator_identity": locator_identity,
    }
    return f"{SOURCE_ANCHOR_ID_PREFIX}{canonical_sha256(payload)}"


def _normalize_seeds(seed_object_ids: Iterable[str], *, required: bool) -> list[str]:
    seeds = list(dict.fromkeys(seed_object_ids))
    for seed in seeds:
        if not isinstance(seed, str) or not seed.strip():
            raise ValueError("seed object IDs must be non-blank strings")
    if required and not seeds:
        raise ValueError("at least one seed object ID is required")
    if len(seeds) > MAX_SEED_OBJECT_IDS:
        raise ValueError(f"at most {MAX_SEED_OBJECT_IDS} seed object IDs are accepted")
    return seeds


def _assertion_rows_for_object(obj: GraphObjectView) -> list[AdmittedAssertionValue]:
    rows: list[AdmittedAssertionValue] = []
    for prop in obj.admitted_property_assertions:
        rows.append(
            AdmittedAssertionValue(
                assertion_id=prop.assertion_id,
                subject_object_id=obj.object_id,
                assertion_kind="property",
                evidence_ref_ids=tuple(prop.evidence_ref_ids),
                assertion_metadata=prop.assertion_metadata,
                property_term=prop.property_term,
                property_value=prop.value,
            )
        )
    return rows


def _index_admitted_assertions(
    result: WorldGraphProjectionResult,
) -> dict[str, AdmittedAssertionValue]:
    """Index every admitted assertion by ID across the scoped projection."""
    index: dict[str, AdmittedAssertionValue] = {}
    for object_id, obj in result.graph.objects.items():
        existence = obj.existence_assertion_metadata
        if existence is not None:
            index[existence.assertion_id] = AdmittedAssertionValue(
                assertion_id=existence.assertion_id,
                subject_object_id=object_id,
                assertion_kind="existence",
                evidence_ref_ids=tuple(existence.evidence_ref_ids),
                assertion_metadata=existence,
            )
        for alias in obj.admitted_alias_assertions:
            index[alias.assertion_id] = AdmittedAssertionValue(
                assertion_id=alias.assertion_id,
                subject_object_id=object_id,
                assertion_kind="alias",
                evidence_ref_ids=tuple(alias.evidence_ref_ids),
                assertion_metadata=alias.assertion_metadata,
            )
        summary = obj.admitted_summary_assertion
        if summary is not None:
            index[summary.assertion_id] = AdmittedAssertionValue(
                assertion_id=summary.assertion_id,
                subject_object_id=object_id,
                assertion_kind="summary",
                evidence_ref_ids=tuple(summary.evidence_ref_ids),
                assertion_metadata=summary.assertion_metadata,
            )
        for row in _assertion_rows_for_object(obj):
            index[row.assertion_id] = row
        for aspect in obj.admitted_aspect_assertions:
            index[aspect.assertion_id] = AdmittedAssertionValue(
                assertion_id=aspect.assertion_id,
                subject_object_id=object_id,
                assertion_kind="aspect",
                evidence_ref_ids=tuple(aspect.evidence_ref_ids),
                assertion_metadata=aspect.assertion_metadata,
            )
    for rel in result.graph.relationships.values():
        metadata = rel.assertion_metadata
        if metadata is not None:
            index[metadata.assertion_id] = AdmittedAssertionValue(
                assertion_id=metadata.assertion_id,
                subject_object_id=rel.subject_object_id,
                assertion_kind="relationship",
                evidence_ref_ids=tuple(rel.evidence_ref_ids),
                assertion_metadata=metadata,
            )
    return index


@dataclass(frozen=True)
class _ResolvedEvidenceChains:
    validated: dict[str, ValidatedProvenance]
    gap_codes: tuple[str, ...]
    missing_ids: tuple[str, ...]


@dataclass
class _AnchorAccum:
    validated: ValidatedProvenance
    locator_identity: str
    supporting_object_ids: set[str] = field(default_factory=set)
    supporting_assertion_ids: set[str] = field(default_factory=set)


_ItemT = TypeVar("_ItemT")

_DEFAULT_BOUNDS = RetrievalBounds()


class WorldGraphRetrievalService:
    """DungeonMind-native retrieval primitives over the v2 projection seam.

    Constructed around the landed ``WorldGraphProjectionService``; every
    operation resolves exactly one exact scoped projection through it. The
    source repository is the same identity store the projection service
    validates against and is used here only to revalidate evidence chains
    before they are returned or bound into an anchor.
    """

    def __init__(
        self,
        *,
        projection: WorldGraphProjectionService,
        sources: SourceRepository,
    ) -> None:
        self._projection = projection
        self._sources = sources

    def get_object(
        self,
        request: WorldGraphProjectionRequestV2,
        *,
        object_id: str,
        bounds: RetrievalBounds = _DEFAULT_BOUNDS,
    ) -> ObjectLookupResult:
        """Exact stable-ID object lookup. A miss is explicit; never a search."""
        if not object_id.strip():
            raise ValueError("object_id must be non-blank")
        result = self._projection.project(request)
        obj = result.graph.objects.get(object_id)
        if obj is None:
            gap_codes: tuple[str, ...] = ()
            missing_ids: tuple[str, ...] = ()
            exclusion = result.scoped_graph.object_exclusions.get(object_id)
            if exclusion is not None:
                codes, missing = public_coverage_gaps_for_exclusion(exclusion)
                gap_codes = tuple(codes)
                missing_ids = tuple(missing)
            return ObjectLookupResult(
                snapshot=result.snapshot,
                found=False,
                object=None,
                coverage=RetrievalCoverage(
                    gap_codes=gap_codes,
                    missing_ids=missing_ids,
                ),
            )
        relationships, relationship_truncated = self._cap(
            self._relationships_touching(result, {object_id}),
            bounds.max_relationships,
        )
        assertions, assertion_truncated = self._cap(
            _assertion_rows_for_object(obj),
            bounds.max_assertions,
        )
        anchors, anchor_truncated, anchor_gaps = self._anchors_for(
            result,
            object_ids={object_id},
            relationship_ids={rel.relationship_id for rel in relationships},
            assertion_ids={row.assertion_id for row in assertions},
            max_anchors=bounds.max_anchors,
        )
        return ObjectLookupResult(
            snapshot=result.snapshot,
            found=True,
            object=obj,
            relationships=relationships,
            property_assertions=assertions,
            anchors=anchors,
            coverage=RetrievalCoverage(
                truncated_fields=self._truncated_fields(
                    relationships=relationship_truncated,
                    assertions=assertion_truncated,
                    anchors=anchor_truncated,
                ),
                gap_codes=anchor_gaps[0],
                missing_ids=anchor_gaps[1],
            ),
        )

    def search(
        self,
        request: WorldGraphProjectionRequestV2,
        *,
        query_text: str = "",
        seed_object_ids: Iterable[str] = (),
        bounds: RetrievalBounds = _DEFAULT_BOUNDS,
    ) -> GraphSearchResult:
        """Deterministic graph-only search / referent resolution.

        Exact object IDs, exact admitted labels/aliases, and lexical
        phrase/token matches over admitted kind/summary/property/relationship
        text rank candidates; explicit seeds are admitted before ranking. A
        query that phrase-matches an omitted or ambiguous alias never recovers
        the blocked object as a candidate. An empty query selects seeds only.
        """
        seeds = _normalize_seeds(seed_object_ids, required=False)
        result = self._projection.project(request)
        graph = result.graph

        referents = tuple(
            resolve_mentions_from_snapshot(
                graph,
                message=query_text,
                selected_object_ids=seeds,
            )
        )

        query_cf = query_text.strip().casefold()
        tokens = _tokenize(query_text)
        scores: dict[str, int] = {}
        reasons: dict[str, list[str]] = {}
        for object_id, obj in graph.objects.items():
            score, object_reasons = _score_object(obj, query_cf=query_cf, tokens=tokens)
            if score:
                scores[object_id] = score
                reasons.setdefault(object_id, []).extend(object_reasons)
        _extend_scores_with_relationships(
            graph.objects, graph.relationships, query_cf, tokens, scores, reasons
        )

        present_seeds = [seed for seed in seeds if seed in graph.objects]
        missing_seeds = tuple(sorted({seed for seed in seeds if seed not in graph.objects}))
        for seed in present_seeds:
            scores[seed] = max(scores.get(seed, 0), _SCORE_EXACT_SEED)
            reasons.setdefault(seed, []).append("exact_seed")

        blocked = objects_blocked_by_omitted_aliases(
            query_text, result.scoped_graph.omitted_alias_index
        ) | objects_blocked_by_ambiguous_aliases(query_text, graph.alias_index)
        for object_id in blocked:
            if object_id not in present_seeds:
                scores.pop(object_id, None)

        ranked_ids = sorted(scores, key=lambda oid: (-scores[oid], oid))
        selected_ids, objects_truncated = self._cap(ranked_ids, bounds.max_objects)
        selected_set = set(selected_ids)

        relationships, relationship_truncated = self._cap(
            self._relationships_touching(result, selected_set),
            bounds.max_relationships,
        )
        assertion_rows = [
            row
            for object_id in selected_ids
            for row in _assertion_rows_for_object(graph.objects[object_id])
        ]
        assertions, assertion_truncated = self._cap(
            sorted(assertion_rows, key=lambda row: row.assertion_id),
            bounds.max_assertions,
        )
        anchors, anchor_truncated, anchor_gaps = self._anchors_for(
            result,
            object_ids=selected_set,
            relationship_ids={rel.relationship_id for rel in relationships},
            assertion_ids={row.assertion_id for row in assertions},
            max_anchors=bounds.max_anchors,
        )
        return GraphSearchResult(
            snapshot=result.snapshot,
            referents=referents,
            matched_object_ids=tuple(selected_ids),
            match_reasons={
                object_id: tuple(sorted(set(reasons[object_id])))
                for object_id in selected_ids
                if object_id in reasons
            },
            objects=tuple(graph.objects[object_id] for object_id in selected_ids),
            relationships=relationships,
            property_assertions=assertions,
            anchors=anchors,
            coverage=RetrievalCoverage(
                requested_seed_object_ids=tuple(seeds),
                missing_seed_object_ids=missing_seeds,
                truncated_fields=self._truncated_fields(
                    objects=objects_truncated,
                    relationships=relationship_truncated,
                    assertions=assertion_truncated,
                    anchors=anchor_truncated,
                ),
                gap_codes=anchor_gaps[0],
                missing_ids=anchor_gaps[1],
            ),
        )

    def get_neighborhood(
        self,
        request: WorldGraphProjectionRequestV2,
        *,
        seed_object_ids: Iterable[str],
        depth: Literal[1, 2] = 1,
        bounds: RetrievalBounds = _DEFAULT_BOUNDS,
    ) -> NeighborhoodResult:
        """Deterministic bounded BFS over the admitted projection.

        1-8 exact seeds, depth 1 or 2. Missing seeds are reported, never
        replaced by a search result; traversal never crosses objects or
        relationships the projection excluded because they are absent from
        the admitted snapshot.
        """
        if depth not in (1, 2):
            raise ValueError("neighborhood depth must be 1 or 2")
        seeds = _normalize_seeds(seed_object_ids, required=True)
        result = self._projection.project(request)
        graph = result.graph

        present_seeds = [seed for seed in seeds if seed in graph.objects]
        missing_seeds = tuple(sorted({seed for seed in seeds if seed not in graph.objects}))

        adjacency: dict[str, list[GraphRelationshipView]] = {}
        for rel in graph.relationships.values():
            adjacency.setdefault(rel.subject_object_id, []).append(rel)
            adjacency.setdefault(rel.object_object_id, []).append(rel)

        depths: dict[str, int] = {seed: 0 for seed in present_seeds}
        visited_edge_ids: set[str] = set()
        frontier = list(present_seeds)
        for level in range(1, depth + 1):
            next_frontier: list[str] = []
            for object_id in sorted(frontier):
                for rel in sorted(
                    adjacency.get(object_id, []), key=lambda item: item.relationship_id
                ):
                    visited_edge_ids.add(rel.relationship_id)
                    other_id = (
                        rel.object_object_id
                        if rel.subject_object_id == object_id
                        else rel.subject_object_id
                    )
                    if other_id not in depths:
                        depths[other_id] = level
                        next_frontier.append(other_id)
            frontier = next_frontier

        others_ordered = sorted(
            (oid for oid in depths if oid not in set(present_seeds)),
            key=lambda oid: (depths[oid], oid),
        )
        selected_ids = present_seeds + others_ordered
        selected_ids, objects_truncated = self._cap(selected_ids, bounds.max_objects)
        selected_set = set(selected_ids)

        candidate_relationships = sorted(
            (
                rel
                for rel in graph.relationships.values()
                if rel.relationship_id in visited_edge_ids
                and rel.subject_object_id in selected_set
                and rel.object_object_id in selected_set
            ),
            key=lambda item: item.relationship_id,
        )
        relationships, relationship_truncated = self._cap(
            candidate_relationships, bounds.max_relationships
        )
        assertion_rows = [
            row
            for object_id in selected_ids
            for row in _assertion_rows_for_object(graph.objects[object_id])
        ]
        assertions, assertion_truncated = self._cap(
            sorted(assertion_rows, key=lambda row: row.assertion_id),
            bounds.max_assertions,
        )
        anchors, anchor_truncated, anchor_gaps = self._anchors_for(
            result,
            object_ids=selected_set,
            relationship_ids={rel.relationship_id for rel in relationships},
            assertion_ids={row.assertion_id for row in assertions},
            max_anchors=bounds.max_anchors,
        )
        return NeighborhoodResult(
            snapshot=result.snapshot,
            seed_object_ids=tuple(present_seeds),
            object_depths={oid: depths[oid] for oid in selected_ids},
            objects=tuple(graph.objects[object_id] for object_id in selected_ids),
            relationships=relationships,
            property_assertions=assertions,
            anchors=anchors,
            coverage=RetrievalCoverage(
                requested_seed_object_ids=tuple(seeds),
                missing_seed_object_ids=missing_seeds,
                truncated_fields=self._truncated_fields(
                    objects=objects_truncated,
                    relationships=relationship_truncated,
                    assertions=assertion_truncated,
                    anchors=anchor_truncated,
                ),
                gap_codes=anchor_gaps[0],
                missing_ids=anchor_gaps[1],
            ),
        )

    def get_evidence(
        self,
        request: WorldGraphProjectionRequestV2,
        *,
        target: EvidenceTarget,
        max_anchors: int = _ANCHORS_LIMIT,
    ) -> EvidenceRetrievalResult:
        """Evidence for one native object / relationship / assertion target.

        Only evidence referenced by the admitted scoped view is returned, and
        every chain is revalidated before it is admitted. Broken in-scope
        provenance produces explicit safe coverage; out-of-scope or
        scope-unknown provenance never echoes identifiers.
        """
        if not 1 <= max_anchors <= _ANCHORS_LIMIT:
            raise ValueError(f"max_anchors must be within 1..{_ANCHORS_LIMIT}")
        result = self._projection.project(request)
        graph = result.graph

        obj: GraphObjectView | None = None
        rel: GraphRelationshipView | None = None
        assertion: AdmittedAssertionValue | None = None
        evidence_ref_ids: tuple[str, ...]
        if target.kind == "object":
            obj = graph.objects.get(target.target_id)
            if obj is None:
                return self._evidence_miss(result, target)
            evidence_ref_ids = tuple(obj.evidence_ref_ids)
        elif target.kind == "relationship":
            rel = graph.relationships.get(target.target_id)
            if rel is None:
                return self._evidence_miss(result, target)
            evidence_ref_ids = tuple(rel.evidence_ref_ids)
        else:
            assertion = _index_admitted_assertions(result).get(target.target_id)
            if assertion is None:
                return self._evidence_miss(result, target)
            evidence_ref_ids = assertion.evidence_ref_ids

        chains = self._resolve_evidence_chains(result, evidence_ref_ids)
        supporters: dict[str, tuple[set[str], set[str]]] = {}
        for evidence_ref_id in evidence_ref_ids:
            if target.kind == "assertion":
                supporters[evidence_ref_id] = (set(), {target.target_id})
            else:
                supporters[evidence_ref_id] = ({target.target_id}, set())
        anchors, anchor_truncated = self._anchors_from_chains(
            result,
            chains,
            supporters=supporters,
            max_anchors=max_anchors,
        )
        return EvidenceRetrievalResult(
            snapshot=result.snapshot,
            found=True,
            target=target,
            object=obj,
            relationship=rel,
            assertion=assertion,
            evidence=tuple(
                chains.validated[evidence_ref_id].evidence
                for evidence_ref_id in sorted(chains.validated)
            ),
            anchors=anchors,
            coverage=RetrievalCoverage(
                truncated_fields=self._truncated_fields(anchors=anchor_truncated),
                gap_codes=chains.gap_codes,
                missing_ids=chains.missing_ids,
            ),
        )

    def resolve_source_anchor(
        self,
        request: WorldGraphProjectionRequestV2,
        *,
        anchor_id: str,
    ) -> SourceAnchorResolution:
        """Opaque anchor revalidation against the exact reprojected context.

        Reprojects the authorized v2 context exactly once, rederives every
        admitted anchor against the exact selected revision, and returns the
        matching admitted anchor metadata or an explicit miss. No cache entry
        is authority; an anchor minted under any other revision, scope mode,
        campaign, focus, admissibility, evidence/source identity, or locator
        identity does not resolve here.
        """
        if not anchor_id.strip():
            raise ValueError("anchor_id must be non-blank")
        result = self._projection.project(request)
        assertion_index = _index_admitted_assertions(result)
        anchors, _truncated, _gaps = self._anchors_for(
            result,
            object_ids=set(result.graph.objects),
            relationship_ids=set(result.graph.relationships),
            assertion_ids=set(assertion_index),
            max_anchors=None,
        )
        for anchor in anchors:
            if anchor.anchor_id == anchor_id:
                return SourceAnchorResolution(
                    snapshot=result.snapshot,
                    found=True,
                    anchor_id=anchor_id,
                    anchor=anchor,
                )
        return SourceAnchorResolution(
            snapshot=result.snapshot,
            found=False,
            anchor_id=anchor_id,
            anchor=None,
        )

    def _evidence_miss(
        self,
        result: WorldGraphProjectionResult,
        target: EvidenceTarget,
    ) -> EvidenceRetrievalResult:
        """Explicit miss with exclusion-aware, leak-safe coverage."""
        exclusion = None
        if target.kind == "object":
            exclusion = result.scoped_graph.object_exclusions.get(target.target_id)
        elif target.kind == "relationship":
            exclusion = result.scoped_graph.relationship_exclusions.get(target.target_id)
        else:
            exclusion = result.scoped_graph.assertion_exclusions.get(target.target_id)
        gap_codes: tuple[str, ...] = ()
        missing_ids: tuple[str, ...] = ()
        if exclusion is not None:
            codes, missing = public_coverage_gaps_for_exclusion(exclusion)
            gap_codes = tuple(codes)
            missing_ids = tuple(missing)
        return EvidenceRetrievalResult(
            snapshot=result.snapshot,
            found=False,
            target=target,
            coverage=RetrievalCoverage(gap_codes=gap_codes, missing_ids=missing_ids),
        )

    def _resolve_evidence_chains(
        self,
        result: WorldGraphProjectionResult,
        evidence_ref_ids: Iterable[str],
    ) -> _ResolvedEvidenceChains:
        """Revalidate every evidence chain against the exact resolved context."""
        snapshot = result.snapshot
        validated: dict[str, ValidatedProvenance] = {}
        gap_codes: set[str] = set()
        missing_ids: set[str] = set()
        unnamed_gap = False
        for evidence_ref_id in sorted(set(evidence_ref_ids)):
            resolved = resolve_evidence_provenance(
                evidence_ref_id,
                snapshot=result.graph,
                sources=self._sources,
                world_id=snapshot.world_id,
                campaign_id=snapshot.campaign_id,
                admissibility=snapshot.admissibility,
                scope_mode=snapshot.scope_mode,
            )
            if isinstance(resolved, ValidatedProvenance):
                validated[evidence_ref_id] = resolved
            elif isinstance(resolved, ProvenanceRejection):
                gap_codes.add(resolved.gap_code)
                missing_ids.add(resolved.missing_id)
            elif resolved is None or resolved is EvidenceScopeVerdict.SCOPE_UNKNOWN:
                # Out-of-scope / scope-unknown on revalidation: never echo the ID.
                unnamed_gap = True
        if unnamed_gap:
            gap_codes.add(STORED_PROVENANCE_INVALID)
        return _ResolvedEvidenceChains(
            validated=validated,
            gap_codes=tuple(sorted(gap_codes)),
            missing_ids=tuple(sorted(missing_ids)),
        )

    def _anchors_for(
        self,
        result: WorldGraphProjectionResult,
        *,
        object_ids: set[str],
        relationship_ids: set[str],
        assertion_ids: set[str],
        max_anchors: int | None,
    ) -> tuple[tuple[SourceAnchorMetadata, ...], bool, tuple[tuple[str, ...], tuple[str, ...]]]:
        """Derive context-bound anchors for the evidence of selected targets."""
        supporters: dict[str, tuple[set[str], set[str]]] = {}
        for object_id in object_ids:
            obj = result.graph.objects.get(object_id)
            if obj is None:
                continue
            for evidence_ref_id in obj.evidence_ref_ids:
                supporters.setdefault(evidence_ref_id, (set(), set()))[0].add(object_id)
        for relationship_id in relationship_ids:
            rel = result.graph.relationships.get(relationship_id)
            if rel is None:
                continue
            for evidence_ref_id in rel.evidence_ref_ids:
                supporters.setdefault(evidence_ref_id, (set(), set()))[0].add(relationship_id)
        if assertion_ids:
            assertion_index = _index_admitted_assertions(result)
            for assertion_id in assertion_ids:
                row = assertion_index.get(assertion_id)
                if row is None:
                    continue
                for evidence_ref_id in row.evidence_ref_ids:
                    supporters.setdefault(evidence_ref_id, (set(), set()))[1].add(assertion_id)

        chains = self._resolve_evidence_chains(result, supporters.keys())
        anchors, truncated = self._anchors_from_chains(
            result,
            chains,
            supporters=supporters,
            max_anchors=max_anchors,
        )
        return anchors, truncated, (chains.gap_codes, chains.missing_ids)

    def _anchors_from_chains(
        self,
        result: WorldGraphProjectionResult,
        chains: _ResolvedEvidenceChains,
        *,
        supporters: dict[str, tuple[set[str], set[str]]],
        max_anchors: int | None,
    ) -> tuple[tuple[SourceAnchorMetadata, ...], bool]:
        snapshot = result.snapshot
        merged: dict[str, _AnchorAccum] = {}
        for evidence_ref_id in sorted(chains.validated):
            validated = chains.validated[evidence_ref_id]
            record = validated.record
            locator_identity = _locator_identity(record)
            anchor_id = derive_source_anchor_id(
                snapshot=snapshot,
                evidence_ref_id=evidence_ref_id,
                source_artifact_id=record.source_artifact_id,
                source_revision_id=record.source_revision_id,
                locator_identity=locator_identity,
            )
            entry = merged.get(anchor_id)
            if entry is None:
                entry = _AnchorAccum(
                    validated=validated, locator_identity=locator_identity
                )
                merged[anchor_id] = entry
            object_supporters, assertion_supporters = supporters.get(
                evidence_ref_id, (set(), set())
            )
            entry.supporting_object_ids.update(object_supporters)
            entry.supporting_assertion_ids.update(assertion_supporters)
        anchors: list[SourceAnchorMetadata] = []
        for anchor_id in sorted(merged):
            entry = merged[anchor_id]
            record = entry.validated.record
            span = getattr(record, "source_span_ref_id", None)
            anchors.append(
                SourceAnchorMetadata(
                    anchor_id=anchor_id,
                    evidence_ref_id=entry.validated.evidence.evidence_ref_id,
                    source_artifact_id=record.source_artifact_id,
                    source_revision_id=record.source_revision_id,
                    locator_identity=entry.locator_identity,
                    source_span_ref_id=(
                        span.strip() if isinstance(span, str) and span.strip() else None
                    ),
                    can_open_source=record.can_open_source,
                    can_highlight_span=record.can_highlight_span,
                    supporting_object_ids=tuple(sorted(entry.supporting_object_ids)),
                    supporting_assertion_ids=tuple(
                        sorted(entry.supporting_assertion_ids)
                    ),
                    evidence=entry.validated.evidence,
                    artifact=entry.validated.artifact,
                )
            )
        if max_anchors is not None and len(anchors) > max_anchors:
            return tuple(anchors[:max_anchors]), True
        return tuple(anchors), False

    @staticmethod
    def _relationships_touching(
        result: WorldGraphProjectionResult,
        object_ids: set[str],
    ) -> list[GraphRelationshipView]:
        return sorted(
            (
                rel
                for rel in result.graph.relationships.values()
                if rel.subject_object_id in object_ids
                or rel.object_object_id in object_ids
            ),
            key=lambda item: item.relationship_id,
        )

    @staticmethod
    def _cap(items: list[_ItemT], limit: int) -> tuple[tuple[_ItemT, ...], bool]:
        if len(items) > limit:
            return tuple(items[:limit]), True
        return tuple(items), False

    @staticmethod
    def _truncated_fields(**flags: bool) -> tuple[str, ...]:
        return tuple(sorted(name for name, flag in flags.items() if flag))


__all__ = [
    "MAX_NEIGHBORHOOD_DEPTH",
    "MAX_SEED_OBJECT_IDS",
    "SOURCE_ANCHOR_ID_PREFIX",
    "SOURCE_ANCHOR_SCHEMA",
    "AdmittedAssertionValue",
    "EvidenceRetrievalResult",
    "EvidenceTarget",
    "GraphSearchResult",
    "NeighborhoodResult",
    "ObjectLookupResult",
    "RetrievalBounds",
    "RetrievalCoverage",
    "SourceAnchorMetadata",
    "SourceAnchorResolution",
    "WorldGraphRetrievalService",
    "derive_source_anchor_id",
]
