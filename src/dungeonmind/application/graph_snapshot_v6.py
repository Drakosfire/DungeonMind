"""Reader for ``dm_union_graph_v6`` — assertion-scoped relationship endpoint aspects.

V6 is additive on the v5 ledger (v4 assertion grain + ``dm_evidence_ref_v2``).
One object identity keeps a single primary ``kind`` and may carry zero or more
assertion-scoped secondary kind aspects. A relationship may name one exact
admitted aspect assertion for either endpoint. Historical v1-v5 readers and
payloads are not mutated.

The mandatory top-level discriminator ``relationship_endpoint_aspect_schema``
prevents a v5 payload from being silently relabeled as v6.
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.retrieval import ResolvedReferent
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.errors import PersistenceIntegrityError
from .graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    AdmittedAliasAssertion,
    AdmittedAspectAssertion,
    AdmittedPropertyAssertion,
    AdmittedSummaryAssertion,
    GraphEvidenceRecordV2,
    GraphObjectView,
    GraphRelationshipView,
    ParsedGraphSnapshot,
    build_label_and_alias_indexes,
    get_object_from_snapshot,
    list_relationships_from_snapshot,
    resolve_mentions_from_snapshot,
)
from .graph_snapshot_v4 import (
    AliasAssertionV4Record,
    PropertyAssertionV4Record,
    SummaryAssertionV4Record,
    _claim_assertion,
    _reject_blank,
)
from .graph_snapshot_v5 import _index_evidence_v2
from .semantic_profiles import (
    SemanticProfileRegistry,
    resolve_and_verify_profile,
    validate_qualified_term,
)


class ObjectAspectAssertionV6Record(DungeonMindModel):
    """One assertion-scoped secondary kind of an existing object identity."""

    aspect_key: str
    kind: str
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _validate_aspect(self) -> Self:
        _reject_blank(self.aspect_key, "aspect_key")
        _reject_blank(self.kind, "aspect kind")
        return self


class GraphObjectV6Record(DungeonMindModel):
    """A v6 object: v4/v5 fields plus optional assertion-scoped aspects."""

    object_id: str
    kind: str
    label: str
    assertion_metadata: KnowledgeAssertionMetadataV1
    aliases: list[AliasAssertionV4Record] = Field(default_factory=list)
    summary: SummaryAssertionV4Record | None = None
    properties: list[PropertyAssertionV4Record] = Field(default_factory=list)
    aspects: list[ObjectAspectAssertionV6Record] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_object(self) -> Self:
        _reject_blank(self.object_id, "object_id")
        _reject_blank(self.kind, "kind")
        _reject_blank(self.label, "label")
        return self


class GraphRelationshipV6Record(DungeonMindModel):
    """A v6 relationship that may select one exact aspect assertion per endpoint."""

    relationship_id: str
    source_object_id: str
    target_object_id: str
    predicate: str
    assertion_metadata: KnowledgeAssertionMetadataV1
    source_aspect_assertion_id: str | None = None
    target_aspect_assertion_id: str | None = None

    @field_validator("source_aspect_assertion_id", "target_aspect_assertion_id")
    @classmethod
    def _reject_blank_aspect_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("aspect assertion id must be non-blank when present")
        return value

    @model_validator(mode="after")
    def _validate_relationship(self) -> Self:
        _reject_blank(self.relationship_id, "relationship_id")
        _reject_blank(self.source_object_id, "source_object_id")
        _reject_blank(self.target_object_id, "target_object_id")
        _reject_blank(self.predicate, "predicate")
        return self


class UnionGraphV6Payload(DungeonMindModel):
    """Strict top-level ``dm_union_graph_v6`` payload shape."""

    world_id: str
    semantic_profile: SemanticProfileRef
    relationship_endpoint_aspect_schema: Literal[
        "dm_relationship_endpoint_aspect_v1"
    ] = RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA
    objects: list[GraphObjectV6Record] = Field(default_factory=list)
    relationships: list[GraphRelationshipV6Record] = Field(default_factory=list)
    evidence_refs: list[GraphEvidenceRecordV2] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_payload(self) -> Self:
        _reject_blank(self.world_id, "world_id")
        if (
            self.relationship_endpoint_aspect_schema
            != RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA
        ):
            raise ValueError(
                "relationship_endpoint_aspect_schema must be "
                f"{RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA!r}"
            )
        return self


def _retained_evidence_v6(
    existence: KnowledgeAssertionMetadataV1,
    alias_views: list[AdmittedAliasAssertion],
    summary_view: AdmittedSummaryAssertion | None,
    property_views: list[AdmittedPropertyAssertion],
    aspect_views: list[AdmittedAspectAssertion],
) -> list[str]:
    retained = list(existence.evidence_ref_ids)
    for alias_view in alias_views:
        retained.extend(alias_view.evidence_ref_ids)
    if summary_view is not None:
        retained.extend(summary_view.evidence_ref_ids)
    for property_view in property_views:
        retained.extend(property_view.evidence_ref_ids)
    for aspect_view in aspect_views:
        retained.extend(aspect_view.evidence_ref_ids)
    return list(dict.fromkeys(retained))


class UnionGraphV6SnapshotReader:
    """Concrete reader for ``dm_union_graph_v6`` only."""

    def __init__(self, profile_registry: SemanticProfileRegistry) -> None:
        self._profile_registry = profile_registry

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V6:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V6!r}",
                details={"graph_schema": graph_schema},
            )
        if not isinstance(graph_payload, dict):
            raise PersistenceIntegrityError(
                "graph payload must be an object",
                details={"payload_type": type(graph_payload).__name__},
            )
        if "semantic_profile" not in graph_payload:
            raise PersistenceIntegrityError(
                "dm_union_graph_v6 requires semantic_profile",
                details={"graph_schema": graph_schema},
            )
        if "relationship_endpoint_aspect_schema" not in graph_payload:
            raise PersistenceIntegrityError(
                "dm_union_graph_v6 requires relationship_endpoint_aspect_schema",
                details={"graph_schema": graph_schema},
            )
        try:
            payload = UnionGraphV6Payload.model_validate(graph_payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "malformed dm_union_graph_v6 object, relationship, assertion, "
                "aspect, or evidence record",
                details={"error": str(exc)},
            ) from exc

        descriptor = resolve_and_verify_profile(
            payload.semantic_profile, self._profile_registry
        )
        evidence = _index_evidence_v2(payload.evidence_refs)
        claimed_assertion_ids: set[str] = set()
        aspect_owners: dict[str, str] = {}

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

            aspect_views: list[AdmittedAspectAssertion] = []
            for aspect in record.aspects:
                validate_qualified_term(aspect.kind, descriptor, field_name="kind")
                metadata = _claim_assertion(
                    aspect.assertion_metadata,
                    claimed=claimed_assertion_ids,
                    kind="aspect",
                )
                aspect_owners[metadata.assertion_id] = record.object_id
                aspect_views.append(
                    AdmittedAspectAssertion(
                        assertion_id=metadata.assertion_id,
                        aspect_key=aspect.aspect_key,
                        kind=aspect.kind,
                        evidence_ref_ids=list(metadata.evidence_ref_ids),
                        assertion_metadata=metadata,
                    )
                )

            objects[record.object_id] = GraphObjectView(
                object_id=record.object_id,
                kind=record.kind,
                label=record.label,
                aliases=list(dict.fromkeys(item.alias for item in alias_views)),
                evidence_ref_ids=_retained_evidence_v6(
                    existence, alias_views, summary_view, property_views, aspect_views
                ),
                summary=summary_view.summary if summary_view is not None else None,
                object_field_schema="v6",
                core_evidence_ref_ids=list(existence.evidence_ref_ids),
                admitted_alias_assertions=alias_views,
                admitted_summary_assertion=summary_view,
                existence_assertion_metadata=existence,
                admitted_property_assertions=property_views,
                admitted_aspect_assertions=aspect_views,
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
            _require_owned_aspect(
                rel.source_aspect_assertion_id,
                endpoint_object_id=rel.source_object_id,
                aspect_owners=aspect_owners,
                relationship_id=rel.relationship_id,
                endpoint="source",
            )
            _require_owned_aspect(
                rel.target_aspect_assertion_id,
                endpoint_object_id=rel.target_object_id,
                aspect_owners=aspect_owners,
                relationship_id=rel.relationship_id,
                endpoint="target",
            )
            relationships[rel.relationship_id] = GraphRelationshipView(
                relationship_id=rel.relationship_id,
                subject_object_id=rel.source_object_id,
                predicate=rel.predicate,
                object_object_id=rel.target_object_id,
                evidence_ref_ids=list(metadata.evidence_ref_ids),
                assertion_metadata=metadata,
                source_aspect_assertion_id=rel.source_aspect_assertion_id,
                target_aspect_assertion_id=rel.target_aspect_assertion_id,
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


def _require_owned_aspect(
    aspect_assertion_id: str | None,
    *,
    endpoint_object_id: str,
    aspect_owners: dict[str, str],
    relationship_id: str,
    endpoint: str,
) -> None:
    if aspect_assertion_id is None:
        return
    owner = aspect_owners.get(aspect_assertion_id)
    if owner is None:
        raise PersistenceIntegrityError(
            "relationship endpoint aspect assertion does not exist",
            details={"relationship_id": relationship_id, "endpoint": endpoint},
        )
    if owner != endpoint_object_id:
        raise PersistenceIntegrityError(
            "relationship endpoint aspect assertion does not belong to the endpoint object",
            details={"relationship_id": relationship_id, "endpoint": endpoint},
        )
