"""Reader for ``dm_union_graph_v5`` — v4 assertion grain with v2 evidence ledger.

V5 reuses v4 object/relationship/assertion record classes unchanged. The only
ledger difference is that ``evidence_refs`` must be ``dm_evidence_ref_v2`` rows;
v1 evidence in a v5 payload fails closed, and v4 continues to reject v2 evidence.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field, ValidationError, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.retrieval import ResolvedReferent
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.errors import PersistenceIntegrityError
from .graph_snapshot import (
    GRAPH_SCHEMA_V5,
    AdmittedAliasAssertion,
    AdmittedPropertyAssertion,
    AdmittedSummaryAssertion,
    GraphEvidenceLedgerRecord,
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
    GraphObjectV4Record,
    GraphRelationshipV4Record,
    _claim_assertion,
    _reject_blank,
    _retained_evidence,
)
from .semantic_profiles import (
    SemanticProfileRegistry,
    resolve_and_verify_profile,
    validate_qualified_term,
)


class UnionGraphV5Payload(DungeonMindModel):
    """Strict top-level ``dm_union_graph_v5`` payload shape."""

    world_id: str
    semantic_profile: SemanticProfileRef
    objects: list[GraphObjectV4Record] = Field(default_factory=list)
    relationships: list[GraphRelationshipV4Record] = Field(default_factory=list)
    evidence_refs: list[GraphEvidenceRecordV2] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_payload(self) -> Self:
        _reject_blank(self.world_id, "world_id")
        return self


def _index_evidence_v2(
    rows: list[GraphEvidenceRecordV2],
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


class UnionGraphV5SnapshotReader:
    """Concrete reader for ``dm_union_graph_v5`` only."""

    def __init__(self, profile_registry: SemanticProfileRegistry) -> None:
        self._profile_registry = profile_registry

    def parse(
        self,
        *,
        graph_schema: str,
        graph_payload: dict[str, Any],
    ) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V5:
            raise PersistenceIntegrityError(
                f"unsupported graph schema {graph_schema!r}; "
                f"expected {GRAPH_SCHEMA_V5!r}",
                details={"graph_schema": graph_schema},
            )
        if not isinstance(graph_payload, dict):
            raise PersistenceIntegrityError(
                "graph payload must be an object",
                details={"payload_type": type(graph_payload).__name__},
            )
        if "semantic_profile" not in graph_payload:
            raise PersistenceIntegrityError(
                "dm_union_graph_v5 requires semantic_profile",
                details={"graph_schema": graph_schema},
            )
        try:
            payload = UnionGraphV5Payload.model_validate(graph_payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "malformed dm_union_graph_v5 object, relationship, assertion, "
                "or evidence record",
                details={"error": str(exc)},
            ) from exc

        descriptor = resolve_and_verify_profile(
            payload.semantic_profile, self._profile_registry
        )
        evidence = _index_evidence_v2(payload.evidence_refs)
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
