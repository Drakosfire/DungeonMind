"""Transport-neutral reader for pinned ``dm_union_graph_v1`` JSON snapshots.

Parses one exact graph payload into indexed views, resolves mentions without
fuzzy matching, and lists one-hop relationships. Malformed stored state fails
closed via ``PersistenceIntegrityError``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Self

from pydantic import Field, ValidationError, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.evidence import EVIDENCE_REF_SCHEMA, EvidenceRole, SourceDomain
from ..contracts.identity import IdentityOutcome
from ..contracts.retrieval import ResolvedReferent
from ..domain.errors import PersistenceIntegrityError

SUPPORTED_GRAPH_SCHEMA = "dm_union_graph_v1"


class GraphNodeRecord(DungeonMindModel):
    object_id: str
    kind: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    summary: str | None = None


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


class GraphObjectView(DungeonMindModel):
    object_id: str
    kind: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    summary: str | None = None


class GraphRelationshipView(DungeonMindModel):
    relationship_id: str
    subject_object_id: str
    predicate: str
    object_object_id: str
    evidence_ref_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ParsedGraphSnapshot:
    world_id: str
    graph_schema: str
    objects: dict[str, GraphObjectView]
    relationships: dict[str, GraphRelationshipView]
    evidence: dict[str, GraphEvidenceRecord]
    label_index: dict[str, list[str]] = field(default_factory=dict)
    alias_index: dict[str, list[str]] = field(default_factory=dict)


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


class UnionGraphV1SnapshotReader:
    """Concrete reader for ``dm_union_graph_v1`` only."""

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != SUPPORTED_GRAPH_SCHEMA:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {SUPPORTED_GRAPH_SCHEMA!r}",
                details={"graph_schema": graph_schema},
            )
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

        try:
            nodes = [
                GraphNodeRecord.model_validate(node)
                for node in graph_payload.get("nodes", [])
            ]
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
            )

        evidence: dict[str, GraphEvidenceRecord] = {}
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

        for obj in objects.values():
            for evidence_ref_id in obj.evidence_ref_ids:
                if evidence_ref_id not in evidence:
                    raise PersistenceIntegrityError(
                        f"dangling node evidence_ref_id {evidence_ref_id!r}",
                        details={"object_id": obj.object_id},
                    )

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
        return snapshot.objects.get(object_id)

    def list_relationships(
        self,
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

    def resolve_mentions(
        self,
        snapshot: ParsedGraphSnapshot,
        *,
        message: str,
        selected_object_ids: list[str],
        candidate_object_ids: list[str] | None = None,
    ) -> list[ResolvedReferent]:
        """Resolve mentions in precedence order.

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

        for alias, object_ids in sorted(snapshot.alias_index.items()):
            if alias and contains_exact_phrase(normalized_message, alias):
                if len(object_ids) == 1:
                    _emit(alias, IdentityOutcome.RESOLVED_EXISTING, object_ids[0])
                else:
                    _emit(alias, IdentityOutcome.AMBIGUOUS, None)

        for object_id in candidate_object_ids or []:
            if object_id in snapshot.objects:
                obj = snapshot.objects[object_id]
                _emit(obj.label, IdentityOutcome.RESOLVED_EXISTING, object_id)

        return referents


def collect_one_hop_object_ids(
    snapshot: ParsedGraphSnapshot,
    seed_object_ids: list[str],
) -> list[str]:
    """Resolved seeds plus objects at the far end of one-hop relationships."""
    seeds = sorted({oid for oid in seed_object_ids if oid in snapshot.objects})
    expanded = set(seeds)
    for rel in UnionGraphV1SnapshotReader().list_relationships(snapshot, seeds):
        expanded.add(rel.subject_object_id)
        expanded.add(rel.object_object_id)
    return sorted(expanded)
