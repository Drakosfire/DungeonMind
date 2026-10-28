"""Explicit independent existence proofs; v1-v6 semantics remain frozen."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from ..contracts.base import DungeonMindModel
from ..contracts.knowledge_assertion import KnowledgeAssertionMetadataV1
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.errors import PersistenceIntegrityError
from .graph_snapshot import (
    GRAPH_SCHEMA_V6,
    GraphEvidenceRecordV2,
    GraphObjectView,
    ParsedGraphSnapshot,
    VersionedUnionGraphSnapshotReader,
    build_label_and_alias_indexes,
)
from .graph_snapshot_v4 import _claim_assertion, _reject_blank
from .graph_snapshot_v6 import (
    GraphObjectV6Record,
    GraphRelationshipV6Record,
    UnionGraphV6Payload,
    UnionGraphV6SnapshotReader,
)
from .semantic_profiles import SemanticProfileRegistry

GRAPH_SCHEMA_V7 = "dm_union_graph_v7"
EXISTENCE_SUPPORT_SCHEMA = "dm_independent_object_existence_support_v1"


class AdmittedExistenceAssertion(DungeonMindModel):
    label: str
    kind: str
    assertion_metadata: KnowledgeAssertionMetadataV1


class GraphObjectV7View(GraphObjectView):
    """Distinct capability; historical v6 internal grain remains unchanged."""

    independent_existence_assertions: list[AdmittedExistenceAssertion] = Field(
        default_factory=list,
        exclude=True,
    )


class ObjectExistenceAssertionV7Record(DungeonMindModel):
    label: str
    kind: str
    assertion_metadata: KnowledgeAssertionMetadataV1

    @model_validator(mode="after")
    def _valid(self) -> Self:
        _reject_blank(self.label, "existence label")
        _reject_blank(self.kind, "existence kind")
        if self.assertion_metadata.canon_state != "canonical":
            raise ValueError("independent existence proof must be canonical")
        return self


class GraphObjectV7Record(GraphObjectV6Record):
    independent_existence_assertions: list[ObjectExistenceAssertionV7Record] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _same_primary_kind(self) -> Self:
        if any(proof.kind != self.kind for proof in self.independent_existence_assertions):
            raise ValueError("existence proof cannot change primary kind")
        return self


class UnionGraphV7Payload(DungeonMindModel):
    world_id: str = Field(min_length=1)
    semantic_profile: SemanticProfileRef
    relationship_endpoint_aspect_schema: Literal["dm_relationship_endpoint_aspect_v1"]
    relationships: list[GraphRelationshipV6Record] = Field(default_factory=list)
    evidence_refs: list[GraphEvidenceRecordV2] = Field(default_factory=list)
    object_existence_support_schema: Literal["dm_independent_object_existence_support_v1"]
    objects: list[GraphObjectV7Record] = Field(default_factory=list)


def _all_assertion_ids(payload: UnionGraphV6Payload) -> set[str]:
    result = set()
    for obj in payload.objects:
        result.add(obj.assertion_metadata.assertion_id)
        for row in [*obj.aliases, *obj.properties, *obj.aspects]:
            result.add(row.assertion_metadata.assertion_id)
        if obj.summary is not None:
            result.add(obj.summary.assertion_metadata.assertion_id)
    result.update(r.assertion_metadata.assertion_id for r in payload.relationships)
    return result


class UnionGraphV7SnapshotReader(UnionGraphV6SnapshotReader):
    """Validate legacy structure, then strict additional independent proofs."""

    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]) -> ParsedGraphSnapshot:
        if graph_schema != GRAPH_SCHEMA_V7:
            raise PersistenceIntegrityError("v7 reader requires dm_union_graph_v7")
        try:
            payload = UnionGraphV7Payload.model_validate(graph_payload)
        except (ValidationError, ValueError, TypeError) as exc:
            raise PersistenceIntegrityError("malformed dm_union_graph_v7") from exc
        legacy = copy.deepcopy(graph_payload)
        legacy.pop("object_existence_support_schema", None)
        for obj in legacy.get("objects", []):
            obj.pop("independent_existence_assertions", None)
        parsed = super().parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=legacy)
        claimed = _all_assertion_ids(UnionGraphV6Payload.model_validate(legacy))
        objects = {}
        for record in payload.objects:
            alternatives = []
            for proof in record.independent_existence_assertions:
                metadata = _claim_assertion(
                    proof.assertion_metadata, claimed=claimed, kind="independent_existence"
                )
                if any(eid not in parsed.evidence for eid in metadata.evidence_ref_ids):
                    raise PersistenceIntegrityError("dangling independent existence evidence")
                alternatives.append(
                    AdmittedExistenceAssertion(
                        label=proof.label, kind=proof.kind, assertion_metadata=metadata
                    )
                )
            view = parsed.objects[record.object_id]
            objects[record.object_id] = GraphObjectV7View.model_validate(
                {
                    **{name: getattr(view, name) for name in type(view).model_fields},
                    "independent_existence_assertions": alternatives,
                    "evidence_ref_ids": list(
                        dict.fromkeys(
                            [
                                *view.evidence_ref_ids,
                                *(
                                    eid
                                    for p in alternatives
                                    for eid in p.assertion_metadata.evidence_ref_ids
                                ),
                            ]
                        )
                    ),
                }
            )
        labels, aliases = build_label_and_alias_indexes(objects)
        return replace(
            parsed,
            graph_schema=GRAPH_SCHEMA_V7,
            objects=objects,
            label_index=labels,
            alias_index=aliases,
        )


class VersionedUnionGraphSnapshotReaderV7(VersionedUnionGraphSnapshotReader):
    """Explicit capability extension; historical dispatcher remains frozen."""

    def __init__(self, profile_registry: SemanticProfileRegistry) -> None:
        super().__init__(profile_registry)
        self._independent_reader = UnionGraphV7SnapshotReader(profile_registry)

    @property
    def parse_compatibility_id(self) -> str:
        return super().parse_compatibility_id + ":independent-existence-v7"

    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]) -> ParsedGraphSnapshot:
        if graph_schema == GRAPH_SCHEMA_V7:
            return self._independent_reader.parse(
                graph_schema=graph_schema,
                graph_payload=graph_payload,
            )
        return super().parse(graph_schema=graph_schema, graph_payload=graph_payload)
