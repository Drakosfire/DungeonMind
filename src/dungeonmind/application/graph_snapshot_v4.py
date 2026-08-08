"""Reader for ``dm_union_graph_v4`` — the assertion-scoped World Graph.

V4 keeps v3's pinned ``SemanticProfileRef`` and adds one
``KnowledgeAssertionMetadataV1`` record to every independently durable
assertion: object existence, each alias, the summary, each property, and each
relationship. Nothing about an assertion is positional — campaign scope,
audience visibility, epistemic standing, canon standing, evidence, session
references, and explicit temporal state are all carried on the assertion
itself, so :mod:`dungeonmind.application.graph_scope` can admit or omit each
one independently.

Deliberate non-decisions encoded here:

* Multiple property assertions may share a ``property_term``. The reader keeps
  every one of them in payload order; there is no implicit first-wins or
  latest-wins collapse, and the kernel does not resolve the disagreement.
* Multiple alias assertions may carry the same alias text (for example a
  GM-visible and a player-visible assertion of the same name). They stay
  distinct assertions; only the projected alias list is de-duplicated.
* ``session_refs`` never influences ``temporal_scope``. There is no code path
  from one to the other.

V1-v3 payload bytes and readers are untouched: v4 is a new schema with its own
top-level shape (``objects`` rather than ``nodes``) and its own strict payload
model, so a v1-v3 payload cannot be read as v4 and vice versa.
"""

from __future__ import annotations

import math
from typing import Any, Self

from pydantic import Field, ValidationError, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.retrieval import ResolvedReferent
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.errors import PersistenceIntegrityError
from .graph_snapshot import (
    GRAPH_SCHEMA_V4,
    AdmittedAliasAssertion,
    AdmittedPropertyAssertion,
    AdmittedSummaryAssertion,
    GraphEvidenceLedgerRecord,
    GraphEvidenceRecord,
    GraphObjectView,
    GraphRelationshipView,
    ParsedGraphSnapshot,
    build_label_and_alias_indexes,
    get_object_from_snapshot,
    list_relationships_from_snapshot,
    resolve_mentions_from_snapshot,
)
from .semantic_profiles import (
    SemanticProfileRegistry,
    resolve_and_verify_profile,
    validate_qualified_term,
)


def _reject_blank(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")


def _validate_json_value(value: Any, *, path: str) -> None:
    """Reject anything a canonical JSON payload cannot round-trip.

    Allowed: ``str``, ``int``, ``float`` (finite), ``bool``, ``None``, and
    lists/dicts (string keys) recursively composed of those.
    """
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be a finite JSON number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} object keys must be strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(
        f"{path} must be a JSON-compatible value "
        f"(got {type(value).__name__})"
    )


class AliasAssertionV4Record(DungeonMindModel):
    """One alias assertion in a ``dm_union_graph_v4`` payload."""

    value: str
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _validate_alias(self) -> Self:
        _reject_blank(self.value, "alias value")
        return self


class SummaryAssertionV4Record(DungeonMindModel):
    """The single summary assertion an object may carry."""

    value: str
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _validate_summary(self) -> Self:
        _reject_blank(self.value, "summary value")
        return self


class PropertyAssertionV4Record(DungeonMindModel):
    """One property assertion. ``value`` must be JSON-compatible."""

    property_term: str
    value: Any
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _validate_property(self) -> Self:
        _reject_blank(self.property_term, "property_term")
        _validate_json_value(self.value, path="property value")
        return self


class GraphObjectV4Record(DungeonMindModel):
    """A v4 object: an existence assertion plus its field assertions."""

    object_id: str
    kind: str
    label: str
    assertion_metadata: KnowledgeAssertionMetadataV1
    aliases: list[AliasAssertionV4Record] = Field(default_factory=list)
    summary: SummaryAssertionV4Record | None = None
    properties: list[PropertyAssertionV4Record] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_object(self) -> Self:
        _reject_blank(self.object_id, "object_id")
        _reject_blank(self.kind, "kind")
        _reject_blank(self.label, "label")
        return self


class GraphRelationshipV4Record(DungeonMindModel):
    """A v4 relationship — one assertion, endpoints named source/target."""

    relationship_id: str
    source_object_id: str
    target_object_id: str
    predicate: str
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _validate_relationship(self) -> Self:
        _reject_blank(self.relationship_id, "relationship_id")
        _reject_blank(self.source_object_id, "source_object_id")
        _reject_blank(self.target_object_id, "target_object_id")
        _reject_blank(self.predicate, "predicate")
        return self


class UnionGraphV4Payload(DungeonMindModel):
    """Strict top-level ``dm_union_graph_v4`` payload shape.

    ``extra="forbid"`` (inherited) means a v1-v3 payload — which carries
    ``nodes`` — can never be silently read as v4.
    """

    world_id: str
    semantic_profile: SemanticProfileRef
    objects: list[GraphObjectV4Record] = Field(default_factory=list)
    relationships: list[GraphRelationshipV4Record] = Field(default_factory=list)
    evidence_refs: list[GraphEvidenceRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_payload(self) -> Self:
        _reject_blank(self.world_id, "world_id")
        return self


def _index_evidence(
    rows: list[GraphEvidenceRecord],
) -> dict[str, GraphEvidenceLedgerRecord]:
    evidence: dict[str, GraphEvidenceLedgerRecord] = {}
    for row in rows:
        prior = evidence.get(row.evidence_ref_id)
        if prior is not None and prior.model_dump() != row.model_dump():
            raise PersistenceIntegrityError(
                f"duplicate evidence_ref_id {row.evidence_ref_id!r} with "
                "differing payloads",
                details={"evidence_ref_id": row.evidence_ref_id},
            )
        evidence[row.evidence_ref_id] = row
    return evidence


def _claim_assertion(
    metadata: KnowledgeAssertionMetadataV1,
    *,
    claimed: set[str],
    kind: str,
) -> KnowledgeAssertionMetadataV1:
    """Enforce graph-global ``assertion_id`` uniqueness.

    Uniqueness spans every assertion family (existence, alias, summary,
    property, relationship) so an id identifies exactly one durable claim.
    Nonempty ``evidence_ref_ids`` is enforced by
    :class:`KnowledgeAssertionMetadataV1` itself; resolvability of those ids
    against the payload ledger is checked separately during parse.
    """
    if metadata.assertion_id in claimed:
        raise PersistenceIntegrityError(
            f"duplicate assertion_id {metadata.assertion_id!r}",
            details={"assertion_id": metadata.assertion_id, "assertion_kind": kind},
        )
    claimed.add(metadata.assertion_id)
    return metadata


class UnionGraphV4SnapshotReader:
    """Concrete reader for ``dm_union_graph_v4`` only."""

    def __init__(self, profile_registry: SemanticProfileRegistry) -> None:
        self._profile_registry = profile_registry

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V4:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V4!r}",
                details={"graph_schema": graph_schema},
            )
        if not isinstance(graph_payload, dict):
            raise PersistenceIntegrityError(
                "graph payload must be an object",
                details={"payload_type": type(graph_payload).__name__},
            )
        if "semantic_profile" not in graph_payload:
            raise PersistenceIntegrityError(
                "dm_union_graph_v4 requires semantic_profile",
                details={"graph_schema": graph_schema},
            )
        try:
            payload = UnionGraphV4Payload.model_validate(graph_payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "malformed dm_union_graph_v4 object, relationship, assertion, "
                "or evidence record",
                details={"error": str(exc)},
            ) from exc

        descriptor = resolve_and_verify_profile(
            payload.semantic_profile, self._profile_registry
        )
        evidence = _index_evidence(payload.evidence_refs)
        claimed_assertion_ids: set[str] = set()

        objects: dict[str, GraphObjectView] = {}
        for record in payload.objects:
            if record.object_id in objects:
                raise PersistenceIntegrityError(
                    f"duplicate object_id {record.object_id!r}",
                    details={"object_id": record.object_id},
                )
            validate_qualified_term(record.kind, descriptor, field_name="kind")
            existence = _claim_assertion(
                record.assertion_metadata,
                claimed=claimed_assertion_ids,
                kind="object_existence",
            )

            alias_views: list[AdmittedAliasAssertion] = []
            for alias in record.aliases:
                metadata = _claim_assertion(
                    alias.assertion_metadata,
                    claimed=claimed_assertion_ids,
                    kind="alias",
                )
                alias_views.append(
                    AdmittedAliasAssertion(
                        assertion_id=metadata.assertion_id,
                        alias=alias.value,
                        evidence_ref_ids=list(metadata.evidence_ref_ids),
                        assertion_metadata=metadata,
                    )
                )

            summary_view: AdmittedSummaryAssertion | None = None
            if record.summary is not None:
                metadata = _claim_assertion(
                    record.summary.assertion_metadata,
                    claimed=claimed_assertion_ids,
                    kind="summary",
                )
                summary_view = AdmittedSummaryAssertion(
                    assertion_id=metadata.assertion_id,
                    summary=record.summary.value,
                    evidence_ref_ids=list(metadata.evidence_ref_ids),
                    assertion_metadata=metadata,
                )

            property_views: list[AdmittedPropertyAssertion] = []
            for prop in record.properties:
                validate_qualified_term(
                    prop.property_term, descriptor, field_name="property_term"
                )
                metadata = _claim_assertion(
                    prop.assertion_metadata,
                    claimed=claimed_assertion_ids,
                    kind="property",
                )
                property_views.append(
                    AdmittedPropertyAssertion(
                        assertion_id=metadata.assertion_id,
                        property_term=prop.property_term,
                        value=prop.value,
                        evidence_ref_ids=list(metadata.evidence_ref_ids),
                        assertion_metadata=metadata,
                    )
                )

            objects[record.object_id] = GraphObjectView(
                object_id=record.object_id,
                kind=record.kind,
                label=record.label,
                aliases=list(dict.fromkeys(item.alias for item in alias_views)),
                evidence_ref_ids=_retained_evidence(
                    existence, alias_views, summary_view, property_views
                ),
                summary=summary_view.summary if summary_view is not None else None,
                object_field_schema="v4",
                core_evidence_ref_ids=list(existence.evidence_ref_ids),
                admitted_alias_assertions=alias_views,
                admitted_summary_assertion=summary_view,
                existence_assertion_metadata=existence,
                admitted_property_assertions=property_views,
            )

        relationships: dict[str, GraphRelationshipView] = {}
        for rel in payload.relationships:
            if rel.relationship_id in relationships:
                raise PersistenceIntegrityError(
                    f"duplicate relationship_id {rel.relationship_id!r}",
                    details={"relationship_id": rel.relationship_id},
                )
            if rel.source_object_id not in objects:
                raise PersistenceIntegrityError(
                    f"dangling relationship subject {rel.source_object_id!r}",
                    details={"relationship_id": rel.relationship_id},
                )
            if rel.target_object_id not in objects:
                raise PersistenceIntegrityError(
                    f"dangling relationship object {rel.target_object_id!r}",
                    details={"relationship_id": rel.relationship_id},
                )
            validate_qualified_term(rel.predicate, descriptor, field_name="predicate")
            metadata = _claim_assertion(
                rel.assertion_metadata,
                claimed=claimed_assertion_ids,
                kind="relationship",
            )
            for evidence_ref_id in metadata.evidence_ref_ids:
                if evidence_ref_id not in evidence:
                    raise PersistenceIntegrityError(
                        f"dangling relationship evidence_ref_id {evidence_ref_id!r}",
                        details={"relationship_id": rel.relationship_id},
                    )
            relationships[rel.relationship_id] = GraphRelationshipView(
                relationship_id=rel.relationship_id,
                subject_object_id=rel.source_object_id,
                predicate=rel.predicate,
                object_object_id=rel.target_object_id,
                evidence_ref_ids=list(metadata.evidence_ref_ids),
                assertion_metadata=metadata,
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
            world_id=payload.world_id,
            graph_schema=graph_schema,
            objects=objects,
            relationships=relationships,
            evidence=evidence,
            label_index=label_index,
            alias_index=alias_index,
            semantic_profile_ref=payload.semantic_profile,
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


def _retained_evidence(
    existence: KnowledgeAssertionMetadataV1,
    alias_views: list[AdmittedAliasAssertion],
    summary_view: AdmittedSummaryAssertion | None,
    property_views: list[AdmittedPropertyAssertion],
) -> list[str]:
    """Evidence ids reachable from the object's currently admitted assertions."""
    retained = list(existence.evidence_ref_ids)
    for alias_view in alias_views:
        retained.extend(alias_view.evidence_ref_ids)
    if summary_view is not None:
        retained.extend(summary_view.evidence_ref_ids)
    for property_view in property_views:
        retained.extend(property_view.evidence_ref_ids)
    return list(dict.fromkeys(retained))
