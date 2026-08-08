"""Transport-neutral readers for pinned union-graph JSON snapshots.

Supports ``dm_union_graph_v1`` (coarse object fields), ``dm_union_graph_v2``
(assertion-scoped aliases and summary), ``dm_union_graph_v3`` (v2 node shape
plus a pinned ``SemanticProfileRef`` with namespace-admitted terms), and
``dm_union_graph_v4`` (v3 profile pinning plus shared
``KnowledgeAssertionMetadataV1`` on every durable assertion — see
``graph_snapshot_v4``). Malformed stored state fails closed via
``PersistenceIntegrityError``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Self

from pydantic import Field, ValidationError, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.evidence import (
    EVIDENCE_REF_SCHEMA,
    EvidenceRefV2,
    EvidenceRole,
    SourceDomain,
)
from ..contracts.identity import IdentityOutcome
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.retrieval import ResolvedReferent
from ..contracts.semantic_profile import (
    SemanticProfileDescriptor,
    SemanticProfileRef,
)
from ..domain.errors import PersistenceIntegrityError
from .semantic_profiles import (
    SemanticProfileRegistry,
    resolve_and_verify_profile,
    validate_qualified_term,
)

GRAPH_SCHEMA_V1 = "dm_union_graph_v1"
GRAPH_SCHEMA_V2 = "dm_union_graph_v2"
GRAPH_SCHEMA_V3 = "dm_union_graph_v3"
GRAPH_SCHEMA_V4 = "dm_union_graph_v4"
GRAPH_SCHEMA_V5 = "dm_union_graph_v5"
SUPPORTED_GRAPH_SCHEMA = GRAPH_SCHEMA_V1  # v1 constant retained for callers


class GraphNodeRecord(DungeonMindModel):
    """``dm_union_graph_v1`` node — aliases/summary share coarse evidence."""

    object_id: str
    kind: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    summary: str | None = None


class AliasAssertionRecord(DungeonMindModel):
    """Schema-local alias assertion for ``dm_union_graph_v2``."""

    assertion_id: str
    alias: str
    evidence_ref_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_alias_assertion(self) -> Self:
        if not self.alias.strip():
            raise ValueError("alias assertion requires a non-empty alias")
        if not self.assertion_id.strip():
            raise ValueError("alias assertion requires a non-empty assertion_id")
        if len(self.evidence_ref_ids) != len(set(self.evidence_ref_ids)):
            raise ValueError(
                f"alias assertion {self.assertion_id!r} has duplicate evidence_ref_ids"
            )
        return self


class SummaryAssertionRecord(DungeonMindModel):
    """Schema-local summary assertion for ``dm_union_graph_v2``."""

    assertion_id: str
    summary: str
    evidence_ref_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_summary_assertion(self) -> Self:
        if not self.summary.strip():
            raise ValueError("summary assertion requires a non-empty summary")
        if not self.assertion_id.strip():
            raise ValueError("summary assertion requires a non-empty assertion_id")
        if len(self.evidence_ref_ids) != len(set(self.evidence_ref_ids)):
            raise ValueError(
                f"summary assertion {self.assertion_id!r} has duplicate evidence_ref_ids"
            )
        return self


class GraphNodeV2Record(DungeonMindModel):
    """``dm_union_graph_v2`` node — no legacy ``aliases`` / ``summary`` keys."""

    object_id: str
    kind: str
    label: str
    evidence_ref_ids: list[str] = Field(min_length=1)
    alias_assertions: list[AliasAssertionRecord] = Field(default_factory=list)
    summary_assertion: SummaryAssertionRecord | None = None

    @model_validator(mode="after")
    def _validate_core_evidence(self) -> Self:
        if not self.label.strip():
            raise ValueError("v2 node requires a non-empty label")
        if len(self.evidence_ref_ids) != len(set(self.evidence_ref_ids)):
            raise ValueError(
                f"v2 node {self.object_id!r} has duplicate core evidence_ref_ids"
            )
        return self


class GraphRelationshipRecord(DungeonMindModel):
    relationship_id: str
    subject_object_id: str
    predicate: str
    object_object_id: str
    evidence_ref_ids: list[str] = Field(default_factory=list)


class GraphEvidenceRecord(DungeonMindModel):
    schema_version: str = EVIDENCE_REF_SCHEMA
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None = None
    source_domain: str
    evidence_role: str = "support"
    can_open_source: bool = True
    can_highlight_span: bool = False
    locator: str | None = None
    uri: str | None = None

    @model_validator(mode="after")
    def _approved_contract_values(self) -> Self:
        if self.schema_version != EVIDENCE_REF_SCHEMA:
            raise ValueError(
                f"unsupported evidence schema_version {self.schema_version!r}; "
                f"expected {EVIDENCE_REF_SCHEMA!r}"
            )
        try:
            SourceDomain(self.source_domain)
            EvidenceRole(self.evidence_role)
        except ValueError as exc:
            raise ValueError(
                "evidence_ref must use approved source_domain and evidence_role values"
            ) from exc
        return self


# V5 ledger rows are the public EvidenceRefV2 contract — no schema-local
# defaults that would invent provenance values omitted from durable JSON.
GraphEvidenceRecordV2 = EvidenceRefV2

GraphEvidenceLedgerRecord = GraphEvidenceRecord | GraphEvidenceRecordV2


class AdmittedAliasAssertion(DungeonMindModel):
    """Internal admitted alias assertion (excluded from public dumps).

    ``assertion_metadata`` is populated only for ``dm_union_graph_v4``; v1-v3
    admitted assertions leave it ``None`` so their dumps stay byte-identical.
    """

    assertion_id: str
    alias: str
    evidence_ref_ids: list[str] = Field(default_factory=list)
    assertion_metadata: KnowledgeAssertionMetadataV1 | None = Field(
        default=None, exclude=True
    )


class AdmittedSummaryAssertion(DungeonMindModel):
    """Internal admitted summary assertion (excluded from public dumps)."""

    assertion_id: str
    summary: str
    evidence_ref_ids: list[str] = Field(default_factory=list)
    assertion_metadata: KnowledgeAssertionMetadataV1 | None = Field(
        default=None, exclude=True
    )


class AdmittedPropertyAssertion(DungeonMindModel):
    """Internal admitted v4 property assertion (excluded from public dumps).

    Multiple assertions may share a ``property_term``; there is no implicit
    first/latest winner and the reader never collapses them.
    """

    assertion_id: str
    property_term: str
    value: Any
    evidence_ref_ids: list[str] = Field(default_factory=list)
    assertion_metadata: KnowledgeAssertionMetadataV1 | None = Field(
        default=None, exclude=True
    )


class GraphObjectView(DungeonMindModel):
    object_id: str
    kind: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    # Internal / excluded: never appear in model_dump used for agent context.
    object_field_schema: Literal["v1", "v2", "v4"] = Field(default="v1", exclude=True)
    core_evidence_ref_ids: list[str] = Field(default_factory=list, exclude=True)
    admitted_alias_assertions: list[AdmittedAliasAssertion] = Field(
        default_factory=list, exclude=True
    )
    admitted_summary_assertion: AdmittedSummaryAssertion | None = Field(
        default=None, exclude=True
    )
    # V4 only: the object's existence assertion plus its property assertions.
    existence_assertion_metadata: KnowledgeAssertionMetadataV1 | None = Field(
        default=None, exclude=True
    )
    admitted_property_assertions: list[AdmittedPropertyAssertion] = Field(
        default_factory=list, exclude=True
    )


class GraphRelationshipView(DungeonMindModel):
    relationship_id: str
    subject_object_id: str
    predicate: str
    object_object_id: str
    evidence_ref_ids: list[str] = Field(default_factory=list)
    # V4 only: the relationship's own assertion metadata.
    assertion_metadata: KnowledgeAssertionMetadataV1 | None = Field(
        default=None, exclude=True
    )


@dataclass(frozen=True)
class ParsedGraphSnapshot:
    world_id: str
    graph_schema: str
    objects: dict[str, GraphObjectView]
    relationships: dict[str, GraphRelationshipView]
    evidence: dict[str, GraphEvidenceLedgerRecord]
    label_index: dict[str, list[str]] = field(default_factory=dict)
    alias_index: dict[str, list[str]] = field(default_factory=dict)
    semantic_profile_ref: SemanticProfileRef | None = None
    semantic_profile_descriptor: SemanticProfileDescriptor | None = None


class GraphSnapshotReader(Protocol):
    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot: ...

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]: ...

    def get_object(
        self,
        snapshot: ParsedGraphSnapshot,
        object_id: str,
    ) -> GraphObjectView | None: ...

    def list_relationships(
        self,
        snapshot: ParsedGraphSnapshot,
        object_ids: list[str],
    ) -> list[GraphRelationshipView]: ...


def _norm(text: str) -> str:
    return text.casefold().strip()


# Opaque DungeonMind IDs commonly include hyphens (e.g. obj:npc-mere-astor).
# Hyphen is last in the class so it is literal.
_TOKEN_CONTINUATION = r"A-Za-z0-9_:-"


def contains_exact_phrase(haystack: str, needle: str) -> bool:
    """Boundary-aware exact phrase/token match (case-sensitive on supplied strings).

    Prevents ``Astor`` from matching inside ``Astoria``, ``obj:x`` from matching
    inside ``obj:xyz``, and ``obj:npc-mere-astor`` from matching inside
    ``obj:npc-mere-astor-impostor``.
    """
    if not needle:
        return False
    pattern = (
        rf"(?<![{_TOKEN_CONTINUATION}])"
        rf"{re.escape(needle)}"
        rf"(?![{_TOKEN_CONTINUATION}])"
    )
    return re.search(pattern, haystack) is not None


def build_label_and_alias_indexes(
    objects: dict[str, GraphObjectView],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Rebuild label/alias indexes from currently admitted object fields."""
    label_index: dict[str, list[str]] = {}
    alias_index: dict[str, list[str]] = {}
    for obj in objects.values():
        label_index.setdefault(_norm(obj.label), []).append(obj.object_id)
        for alias in obj.aliases:
            alias_index.setdefault(_norm(alias), []).append(obj.object_id)
    for key, ids in label_index.items():
        label_index[key] = sorted(set(ids))
    for key, ids in alias_index.items():
        alias_index[key] = sorted(set(ids))
    return label_index, alias_index


def get_object_from_snapshot(
    snapshot: ParsedGraphSnapshot,
    object_id: str,
) -> GraphObjectView | None:
    return snapshot.objects.get(object_id)


def list_relationships_from_snapshot(
    snapshot: ParsedGraphSnapshot,
    object_ids: list[str],
) -> list[GraphRelationshipView]:
    focus = set(object_ids)
    matched = [
        rel
        for rel in snapshot.relationships.values()
        if rel.subject_object_id in focus or rel.object_object_id in focus
    ]
    return sorted(matched, key=lambda rel: rel.relationship_id)


def resolve_mentions_from_snapshot(
    snapshot: ParsedGraphSnapshot,
    *,
    message: str,
    selected_object_ids: list[str],
    candidate_object_ids: list[str] | None = None,
) -> list[ResolvedReferent]:
    """Resolve mentions against the scoped snapshot indexes.

    Precedence:
    1. exact selected object IDs
    2. exact object IDs present in the message
    3. case-insensitive exact labels
    4. case-insensitive exact aliases
    5. fused semantic-document candidates mapped to graph object IDs
    """
    referents: list[ResolvedReferent] = []
    seen_mentions: set[str] = set()

    def _emit(mention: str, outcome: IdentityOutcome, object_id: str | None) -> None:
        key = f"{mention}|{outcome.value}|{object_id or ''}"
        if key in seen_mentions:
            return
        seen_mentions.add(key)
        referents.append(
            ResolvedReferent(
                mention_text=mention,
                outcome=outcome,
                object_id=object_id,
            )
        )

    normalized_message = _norm(message)

    for object_id in selected_object_ids:
        if object_id in snapshot.objects:
            _emit(object_id, IdentityOutcome.RESOLVED_EXISTING, object_id)
        else:
            _emit(object_id, IdentityOutcome.REJECTED, None)

    for object_id in sorted(snapshot.objects):
        if contains_exact_phrase(message, object_id):
            _emit(object_id, IdentityOutcome.RESOLVED_EXISTING, object_id)

    for label, object_ids in sorted(snapshot.label_index.items()):
        if label and contains_exact_phrase(normalized_message, label):
            if len(object_ids) == 1:
                obj = snapshot.objects[object_ids[0]]
                _emit(obj.label, IdentityOutcome.RESOLVED_EXISTING, object_ids[0])
            else:
                _emit(
                    snapshot.objects[object_ids[0]].label,
                    IdentityOutcome.AMBIGUOUS,
                    None,
                )

    ambiguous_object_ids: set[str] = set()
    for alias, object_ids in sorted(snapshot.alias_index.items()):
        if alias and contains_exact_phrase(normalized_message, alias):
            if len(object_ids) == 1:
                _emit(alias, IdentityOutcome.RESOLVED_EXISTING, object_ids[0])
            else:
                ambiguous_object_ids.update(object_ids)
                _emit(alias, IdentityOutcome.AMBIGUOUS, None)

    # Semantic candidates must not override an exact ambiguous alias match by
    # emitting resolved_existing under a visible primary label.
    for object_id in candidate_object_ids or []:
        if object_id in ambiguous_object_ids:
            continue
        if object_id in snapshot.objects:
            obj = snapshot.objects[object_id]
            _emit(obj.label, IdentityOutcome.RESOLVED_EXISTING, object_id)

    return referents


def _parse_common_evidence_and_relationships(
    *,
    graph_payload: dict[str, Any],
    objects: dict[str, GraphObjectView],
) -> tuple[dict[str, GraphEvidenceLedgerRecord], dict[str, GraphRelationshipView]]:
    try:
        relationships = [
            GraphRelationshipRecord.model_validate(rel)
            for rel in graph_payload.get("relationships", [])
        ]
        evidence_rows = [
            GraphEvidenceRecord.model_validate(row)
            for row in graph_payload.get("evidence_refs", [])
        ]
    except (ValidationError, TypeError, ValueError) as exc:
        raise PersistenceIntegrityError(
            "malformed graph relationship or evidence record",
            details={"error": str(exc)},
        ) from exc

    evidence: dict[str, GraphEvidenceLedgerRecord] = {}
    for row in evidence_rows:
        prior = evidence.get(row.evidence_ref_id)
        if prior is not None and prior.model_dump() != row.model_dump():
            raise PersistenceIntegrityError(
                f"duplicate evidence_ref_id {row.evidence_ref_id!r} with differing payloads",
                details={"evidence_ref_id": row.evidence_ref_id},
            )
        evidence[row.evidence_ref_id] = row

    relationships_by_id: dict[str, GraphRelationshipView] = {}
    for rel in relationships:
        if rel.relationship_id in relationships_by_id:
            raise PersistenceIntegrityError(
                f"duplicate relationship_id {rel.relationship_id!r}",
                details={"relationship_id": rel.relationship_id},
            )
        if rel.subject_object_id not in objects:
            raise PersistenceIntegrityError(
                f"dangling relationship subject {rel.subject_object_id!r}",
                details={"relationship_id": rel.relationship_id},
            )
        if rel.object_object_id not in objects:
            raise PersistenceIntegrityError(
                f"dangling relationship object {rel.object_object_id!r}",
                details={"relationship_id": rel.relationship_id},
            )
        for evidence_ref_id in rel.evidence_ref_ids:
            if evidence_ref_id not in evidence:
                raise PersistenceIntegrityError(
                    f"dangling relationship evidence_ref_id {evidence_ref_id!r}",
                    details={"relationship_id": rel.relationship_id},
                )
        relationships_by_id[rel.relationship_id] = GraphRelationshipView(
            relationship_id=rel.relationship_id,
            subject_object_id=rel.subject_object_id,
            predicate=rel.predicate,
            object_object_id=rel.object_object_id,
            evidence_ref_ids=list(rel.evidence_ref_ids),
        )
    return evidence, relationships_by_id


def _require_payload_world(graph_payload: dict[str, Any]) -> str:
    if not isinstance(graph_payload, dict):
        raise PersistenceIntegrityError(
            "graph payload must be an object",
            details={"payload_type": type(graph_payload).__name__},
        )
    world_id = graph_payload.get("world_id")
    if not isinstance(world_id, str) or not world_id:
        raise PersistenceIntegrityError(
            "graph payload requires a non-empty world_id",
        )
    return world_id


def _reject_semantic_profile_field(
    graph_payload: dict[str, Any], *, graph_schema: str
) -> None:
    if "semantic_profile" in graph_payload:
        raise PersistenceIntegrityError(
            f"{graph_schema} does not accept semantic_profile",
            details={"graph_schema": graph_schema},
        )


def _parse_v2_shaped_objects(
    graph_payload: dict[str, Any],
) -> dict[str, GraphObjectView]:
    """Shared node parse for ``dm_union_graph_v2`` / ``dm_union_graph_v3``."""
    try:
        nodes = [
            GraphNodeV2Record.model_validate(node)
            for node in graph_payload.get("nodes", [])
        ]
    except (ValidationError, TypeError, ValueError) as exc:
        raise PersistenceIntegrityError(
            "malformed graph node, relationship, or evidence record",
            details={"error": str(exc)},
        ) from exc

    objects: dict[str, GraphObjectView] = {}
    assertion_ids: set[str] = set()
    for node in nodes:
        if node.object_id in objects:
            raise PersistenceIntegrityError(
                f"duplicate object_id {node.object_id!r}",
                details={"object_id": node.object_id},
            )
        seen_aliases: set[str] = set()
        alias_views: list[AdmittedAliasAssertion] = []
        for assertion in node.alias_assertions:
            if assertion.assertion_id in assertion_ids:
                raise PersistenceIntegrityError(
                    f"duplicate assertion_id {assertion.assertion_id!r}",
                    details={"assertion_id": assertion.assertion_id},
                )
            assertion_ids.add(assertion.assertion_id)
            normalized_alias = _norm(assertion.alias)
            if normalized_alias in seen_aliases:
                raise PersistenceIntegrityError(
                    f"duplicate normalized alias {assertion.alias!r} on "
                    f"object {node.object_id!r}",
                    details={"object_id": node.object_id, "alias": assertion.alias},
                )
            seen_aliases.add(normalized_alias)
            alias_views.append(
                AdmittedAliasAssertion(
                    assertion_id=assertion.assertion_id,
                    alias=assertion.alias,
                    evidence_ref_ids=list(assertion.evidence_ref_ids),
                )
            )

        summary_view: AdmittedSummaryAssertion | None = None
        if node.summary_assertion is not None:
            assertion = node.summary_assertion
            if assertion.assertion_id in assertion_ids:
                raise PersistenceIntegrityError(
                    f"duplicate assertion_id {assertion.assertion_id!r}",
                    details={"assertion_id": assertion.assertion_id},
                )
            assertion_ids.add(assertion.assertion_id)
            summary_view = AdmittedSummaryAssertion(
                assertion_id=assertion.assertion_id,
                summary=assertion.summary,
                evidence_ref_ids=list(assertion.evidence_ref_ids),
            )

        retained_evidence = list(node.evidence_ref_ids)
        for alias_view in alias_views:
            retained_evidence.extend(alias_view.evidence_ref_ids)
        if summary_view is not None:
            retained_evidence.extend(summary_view.evidence_ref_ids)

        objects[node.object_id] = GraphObjectView(
            object_id=node.object_id,
            kind=node.kind,
            label=node.label,
            aliases=[item.alias for item in alias_views],
            evidence_ref_ids=list(dict.fromkeys(retained_evidence)),
            summary=summary_view.summary if summary_view is not None else None,
            object_field_schema="v2",
            core_evidence_ref_ids=list(node.evidence_ref_ids),
            admitted_alias_assertions=alias_views,
            admitted_summary_assertion=summary_view,
        )
    return objects


class UnionGraphV1SnapshotReader:
    """Concrete reader for ``dm_union_graph_v1`` only."""

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V1:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V1!r}",
                details={"graph_schema": graph_schema},
            )
        world_id = _require_payload_world(graph_payload)
        _reject_semantic_profile_field(graph_payload, graph_schema=graph_schema)

        try:
            nodes = [
                GraphNodeRecord.model_validate(node)
                for node in graph_payload.get("nodes", [])
            ]
        except (ValidationError, TypeError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "malformed graph node, relationship, or evidence record",
                details={"error": str(exc)},
            ) from exc

        objects: dict[str, GraphObjectView] = {}
        for node in nodes:
            if node.object_id in objects:
                raise PersistenceIntegrityError(
                    f"duplicate object_id {node.object_id!r}",
                    details={"object_id": node.object_id},
                )
            objects[node.object_id] = GraphObjectView(
                object_id=node.object_id,
                kind=node.kind,
                label=node.label,
                aliases=list(node.aliases),
                evidence_ref_ids=list(node.evidence_ref_ids),
                summary=node.summary,
                object_field_schema="v1",
                core_evidence_ref_ids=list(node.evidence_ref_ids),
            )

        evidence, relationships_by_id = _parse_common_evidence_and_relationships(
            graph_payload=graph_payload,
            objects=objects,
        )
        for obj in objects.values():
            for evidence_ref_id in obj.evidence_ref_ids:
                if evidence_ref_id not in evidence:
                    raise PersistenceIntegrityError(
                        f"dangling node evidence_ref_id {evidence_ref_id!r}",
                        details={"object_id": obj.object_id},
                    )

        label_index, alias_index = build_label_and_alias_indexes(objects)
        return ParsedGraphSnapshot(
            world_id=world_id,
            graph_schema=graph_schema,
            objects=objects,
            relationships=relationships_by_id,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
        )

    def get_object(
        self,
        snapshot: ParsedGraphSnapshot,
        object_id: str,
    ) -> GraphObjectView | None:
        return get_object_from_snapshot(snapshot, object_id)

    def list_relationships(
        self,
        snapshot: ParsedGraphSnapshot,
        object_ids: list[str],
    ) -> list[GraphRelationshipView]:
        return list_relationships_from_snapshot(snapshot, object_ids)

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]:
        return resolve_mentions_from_snapshot(
            snapshot,
            message=message,
            selected_object_ids=selected_object_ids,
            candidate_object_ids=candidate_object_ids,
        )


class UnionGraphV2SnapshotReader:
    """Concrete reader for ``dm_union_graph_v2`` only."""

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V2:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V2!r}",
                details={"graph_schema": graph_schema},
            )
        world_id = _require_payload_world(graph_payload)
        _reject_semantic_profile_field(graph_payload, graph_schema=graph_schema)

        objects = _parse_v2_shaped_objects(graph_payload)
        evidence, relationships_by_id = _parse_common_evidence_and_relationships(
            graph_payload=graph_payload,
            objects=objects,
        )
        for obj in objects.values():
            for evidence_ref_id in obj.evidence_ref_ids:
                if evidence_ref_id not in evidence:
                    raise PersistenceIntegrityError(
                        f"dangling node evidence_ref_id {evidence_ref_id!r}",
                        details={"object_id": obj.object_id},
                    )

        label_index, alias_index = build_label_and_alias_indexes(objects)
        return ParsedGraphSnapshot(
            world_id=world_id,
            graph_schema=graph_schema,
            objects=objects,
            relationships=relationships_by_id,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
            semantic_profile_ref=None,
            semantic_profile_descriptor=None,
        )

    def get_object(
        self,
        snapshot: ParsedGraphSnapshot,
        object_id: str,
    ) -> GraphObjectView | None:
        return get_object_from_snapshot(snapshot, object_id)

    def list_relationships(
        self,
        snapshot: ParsedGraphSnapshot,
        object_ids: list[str],
    ) -> list[GraphRelationshipView]:
        return list_relationships_from_snapshot(snapshot, object_ids)

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]:
        return resolve_mentions_from_snapshot(
            snapshot,
            message=message,
            selected_object_ids=selected_object_ids,
            candidate_object_ids=candidate_object_ids,
        )


class UnionGraphV3SnapshotReader:
    """Concrete reader for ``dm_union_graph_v3`` (v2 nodes + semantic profile)."""

    def __init__(self, profile_registry: SemanticProfileRegistry) -> None:
        self._profile_registry = profile_registry

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V3:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V3!r}",
                details={"graph_schema": graph_schema},
            )
        world_id = _require_payload_world(graph_payload)

        raw_profile = graph_payload.get("semantic_profile")
        if raw_profile is None:
            raise PersistenceIntegrityError(
                "dm_union_graph_v3 requires semantic_profile",
                details={"graph_schema": graph_schema},
            )
        try:
            profile_ref = SemanticProfileRef.model_validate(raw_profile)
        except (ValidationError, TypeError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "malformed semantic_profile on graph payload",
                details={"error": str(exc)},
            ) from exc

        descriptor = resolve_and_verify_profile(profile_ref, self._profile_registry)

        objects = _parse_v2_shaped_objects(graph_payload)
        for obj in objects.values():
            validate_qualified_term(obj.kind, descriptor, field_name="kind")

        evidence, relationships_by_id = _parse_common_evidence_and_relationships(
            graph_payload=graph_payload,
            objects=objects,
        )
        for rel in relationships_by_id.values():
            validate_qualified_term(rel.predicate, descriptor, field_name="predicate")

        for obj in objects.values():
            for evidence_ref_id in obj.evidence_ref_ids:
                if evidence_ref_id not in evidence:
                    raise PersistenceIntegrityError(
                        f"dangling node evidence_ref_id {evidence_ref_id!r}",
                        details={"object_id": obj.object_id},
                    )

        label_index, alias_index = build_label_and_alias_indexes(objects)
        return ParsedGraphSnapshot(
            world_id=world_id,
            graph_schema=graph_schema,
            objects=objects,
            relationships=relationships_by_id,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
            semantic_profile_ref=profile_ref,
            semantic_profile_descriptor=descriptor,
        )

    def get_object(
        self,
        snapshot: ParsedGraphSnapshot,
        object_id: str,
    ) -> GraphObjectView | None:
        return get_object_from_snapshot(snapshot, object_id)

    def list_relationships(
        self,
        snapshot: ParsedGraphSnapshot,
        object_ids: list[str],
    ) -> list[GraphRelationshipView]:
        return list_relationships_from_snapshot(snapshot, object_ids)

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]:
        return resolve_mentions_from_snapshot(
            snapshot,
            message=message,
            selected_object_ids=selected_object_ids,
            candidate_object_ids=candidate_object_ids,
        )


class _EmptySemanticProfileRegistry:
    """Default registry: admits nothing (v3 fails closed)."""

    def get(
        self, profile_id: str, profile_revision: str
    ) -> SemanticProfileDescriptor | None:
        return None


class VersionedUnionGraphSnapshotReader:
    """Dispatch by exact ``graph_schema``; reject unsupported schemas."""

    def __init__(
        self,
        profile_registry: SemanticProfileRegistry | None = None,
    ) -> None:
        registry = profile_registry if profile_registry is not None else (
            _EmptySemanticProfileRegistry()
        )
        # Imported here (not at module scope) because the v4 reader depends on
        # the record/view types defined above.
        from .graph_snapshot_v4 import UnionGraphV4SnapshotReader
        from .graph_snapshot_v5 import UnionGraphV5SnapshotReader

        self._profile_registry = registry
        self._v1 = UnionGraphV1SnapshotReader()
        self._v2 = UnionGraphV2SnapshotReader()
        self._v3 = UnionGraphV3SnapshotReader(registry)
        self._v4 = UnionGraphV4SnapshotReader(registry)
        self._v5 = UnionGraphV5SnapshotReader(registry)

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema == GRAPH_SCHEMA_V1:
            return self._v1.parse(
                graph_schema=graph_schema, graph_payload=graph_payload
            )
        if graph_schema == GRAPH_SCHEMA_V2:
            return self._v2.parse(
                graph_schema=graph_schema, graph_payload=graph_payload
            )
        if graph_schema == GRAPH_SCHEMA_V3:
            return self._v3.parse(
                graph_schema=graph_schema, graph_payload=graph_payload
            )
        if graph_schema == GRAPH_SCHEMA_V4:
            return self._v4.parse(
                graph_schema=graph_schema, graph_payload=graph_payload
            )
        if graph_schema == GRAPH_SCHEMA_V5:
            return self._v5.parse(
                graph_schema=graph_schema, graph_payload=graph_payload
            )
        raise PersistenceIntegrityError(
            f"unsupported graph schema {graph_schema!r}",
            details={"graph_schema": graph_schema},
        )

    def get_object(
        self,
        snapshot: ParsedGraphSnapshot,
        object_id: str,
    ) -> GraphObjectView | None:
        return get_object_from_snapshot(snapshot, object_id)

    def list_relationships(
        self,
        snapshot: ParsedGraphSnapshot,
        object_ids: list[str],
    ) -> list[GraphRelationshipView]:
        return list_relationships_from_snapshot(snapshot, object_ids)

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]:
        return resolve_mentions_from_snapshot(
            snapshot,
            message=message,
            selected_object_ids=selected_object_ids,
            candidate_object_ids=candidate_object_ids,
        )


def collect_one_hop_object_ids(
    snapshot: ParsedGraphSnapshot,
    seed_object_ids: list[str],
) -> list[str]:
    """Resolved seeds plus objects at the far end of one-hop relationships."""
    seeds = sorted({oid for oid in seed_object_ids if oid in snapshot.objects})
    expanded = set(seeds)
    for rel in list_relationships_from_snapshot(snapshot, seeds):
        expanded.add(rel.subject_object_id)
        expanded.add(rel.object_object_id)
    return sorted(expanded)
