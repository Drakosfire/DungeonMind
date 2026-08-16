"""Strict Buddy dual-sense decomposition package and D&D materialization plan.

This is a DungeonMind-owned redeclaration of
``dmb_relationship_dual_sense_decomposition_v1``. Production code must not
import Buddy models or read a sibling repository. Parsing success is not
attestation.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from dungeonmind.contracts.base import DungeonMindModel

from .vocabulary import DndVocabularyRef

SOURCE_PACKAGE_SCHEMA = "dmb_relationship_dual_sense_decomposition_v1"
SOURCE_PACKAGE_PROJECTION_SCHEMA = (
    "dmb_relationship_dual_sense_decomposition_v1_package_projection"
)
PLAN_SCHEMA = "dmdnd_relationship_aspect_materialization_plan_v1"
AssignedEndpoint = Literal["source", "target"]


def _reject_blank(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")


class BuddyAspectRefV1(DungeonMindModel):
    source_node_id: str
    aspect_key: str
    projected_dm_kind: str

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _reject_blank(self.source_node_id, "aspect_ref.source_node_id")
        _reject_blank(self.aspect_key, "aspect_ref.aspect_key")
        _reject_blank(self.projected_dm_kind, "aspect_ref.projected_dm_kind")
        return self


class BuddyDecompositionRowV1(DungeonMindModel):
    source_node_id: str
    stored_buddy_kind: str
    aspect_key: str
    projected_dm_kind: str
    deferred_edge_ids: list[str]
    retained_edge_ids: list[str]
    predecessor_stop_authority_ref: str
    predecessor_repair_manifest_sha256: str
    kind_only_insufficient: bool
    stop_note: str

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _reject_blank(self.source_node_id, "source_node_id")
        _reject_blank(self.stored_buddy_kind, "stored_buddy_kind")
        _reject_blank(self.aspect_key, "aspect_key")
        _reject_blank(self.projected_dm_kind, "projected_dm_kind")
        if not self.deferred_edge_ids:
            raise ValueError("decomposition row requires deferred_edge_ids")
        return self


class BuddyEndpointAssignmentV1(DungeonMindModel):
    edge_id: str
    buddy_predicate: str
    source_node_id: str
    target_node_id: str
    assigned_endpoint: AssignedEndpoint
    aspect_ref: BuddyAspectRefV1
    predecessor_stop_authority_ref: str
    predecessor_repair_manifest_sha256: str
    rationale: str

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _reject_blank(self.edge_id, "edge_id")
        _reject_blank(self.buddy_predicate, "buddy_predicate")
        _reject_blank(self.source_node_id, "source_node_id")
        _reject_blank(self.target_node_id, "target_node_id")
        return self


class BuddyEndpointAdmissionV1(DungeonMindModel):
    edge_id: str
    admitted: bool
    dm_predicate: str | None = None
    source_dm_kind: str | None = None
    target_dm_kind: str | None = None
    note: str = ""


class BuddyPackageProjectionV1(DungeonMindModel):
    schema_: str = Field(alias="schema")
    passed: bool
    assigned_admissions: list[BuddyEndpointAdmissionV1]
    retained_admissions: list[BuddyEndpointAdmissionV1]
    retained_regressions: list[str]
    uncovered_current_residual_edge_ids: list[str]
    extra_package_edge_assignments: list[str]
    dungeonmind_target_id: str
    dungeonmind_dependency_ref: str
    world_object_revision_label: str

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.schema_ != SOURCE_PACKAGE_PROJECTION_SCHEMA:
            raise ValueError("package_projection schema mismatch")
        return self


class BuddyDualSenseDecompositionPackageV1(DungeonMindModel):
    """Strict local shape of ``dmb_relationship_dual_sense_decomposition_v1``."""

    schema_: str = Field(alias="schema")
    package_id: str
    world_id: str
    canonical_revision_id: str
    canonical_graph_payload_sha256: str
    store_semantic_sha256: str
    dungeonmind_target_id: str
    dungeonmind_dependency_ref: str
    world_object_revision_label: str
    predecessor_repair_id: str
    predecessor_repair_manifest_sha256: str
    decomposition_rows: list[BuddyDecompositionRowV1]
    endpoint_assignments: list[BuddyEndpointAssignmentV1]
    package_projection: BuddyPackageProjectionV1
    canonical_payload_sha256: str = ""

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.schema_ != SOURCE_PACKAGE_SCHEMA:
            raise ValueError("package schema mismatch")
        _reject_blank(self.package_id, "package_id")
        _reject_blank(self.world_id, "world_id")
        _reject_blank(self.canonical_revision_id, "canonical_revision_id")
        _reject_blank(self.canonical_graph_payload_sha256, "canonical_graph_payload_sha256")
        _reject_blank(self.dungeonmind_dependency_ref, "dungeonmind_dependency_ref")
        _reject_blank(self.world_object_revision_label, "world_object_revision_label")
        return self


class DndRelationshipAspectDirectiveV1(DungeonMindModel):
    source_object_id: str
    aspect_key: str
    projected_kind: str


class DndRelationshipAspectEndpointDirectiveV1(DungeonMindModel):
    source_edge_id: str
    assigned_endpoint: AssignedEndpoint
    source_object_id: str
    target_object_id: str
    aspect_key: str
    projected_kind: str
    dm_predicate: str
    source_dm_kind: str
    target_dm_kind: str

    @field_validator("source_edge_id", "source_object_id", "target_object_id")
    @classmethod
    def _no_synthetic_object_id(cls, value: str) -> str:
        _reject_blank(value, "object or edge id")
        if value.startswith("node:aspect:") or "synthetic" in value:
            raise ValueError("materialization plan must not invent object identities")
        return value


class DndRelationshipAspectMaterializationPlanV1(DungeonMindModel):
    schema_version: Literal[
        "dmdnd_relationship_aspect_materialization_plan_v1"
    ] = PLAN_SCHEMA
    source_package_schema: str
    source_package_sha256: str
    source_package_canonical_payload_sha256: str
    source_world_id: str
    source_revision_id: str
    source_graph_payload_sha256: str
    source_dungeonmind_dependency_ref: str
    world_object_vocabulary: DndVocabularyRef
    aspect_directives: list[DndRelationshipAspectDirectiveV1]
    endpoint_directives: list[DndRelationshipAspectEndpointDirectiveV1]
    plan_sha256: str = ""
