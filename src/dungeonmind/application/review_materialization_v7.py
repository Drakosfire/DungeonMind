"""Reviewed v7 ingestion keeps independently sufficient core proofs separate."""

from __future__ import annotations

import copy
from typing import Any

from ..contracts.contribution import (
    AcceptanceState,
    GraphContributionAssertionV2,
    GraphContributionAssertionV4,
)
from ..contracts.contribution_review import ContributionIdentityVerdictKind
from ..contracts.contribution_review_v3 import ContributionReviewStateV3
from ..contracts.contribution_review_v4 import ContributionReviewStateV4
from ..contracts.contribution_review_v5 import ContributionReviewStateV5
from ..contracts.graph import StoredGraphRevision
from ..domain.canonical import canonical_sha256
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from .graph_snapshot_v6 import UnionGraphV6Payload
from .graph_snapshot_v7 import (
    EXISTENCE_SUPPORT_SCHEMA,
    GRAPH_SCHEMA_V7,
    GraphObjectV7Record,
    ObjectExistenceAssertionV7Record,
    UnionGraphV7Payload,
)
from .review_materialization import FinalizedReviewGraphMaterialization
from .review_materialization_v4 import _property, _validate_reviewed_property_delta
from .review_materialization_v6 import (
    NON_MUTATING_IDENTITY_OUTCOMES,
    _assertion_evidence,
    _fail,
    _metadata,
    _parse_value,
    _reject_mechanics_binding,
    _reload_parent,
    _session_refs,
    _V6Materialization,
)
from .source_description_correction import SourceDescriptionCorrectionProof
from .source_provenance_snapshot import SourceProvenanceSnapshot


class _V7Materialization(_V6Materialization):
    def apply_node(self, assertion: GraphContributionAssertionV2) -> None:
        target = assertion.subject_object_id
        if target is None:
            _fail("orphan_accepted_assertion")
        existing = self.objects.get(target)
        verdict = self._verdict_for_target(target) if target is not None else None
        if existing is None:
            if verdict is not ContributionIdentityVerdictKind.CREATE_NEW:
                _fail("v7_new_node_requires_explicit_identity")
            super().apply_node(assertion)
            created = self.objects[target]
            self.objects[target] = GraphObjectV7Record.model_validate(
                created.model_dump(mode="json")
            )
            return
        if verdict is not ContributionIdentityVerdictKind.CONFIRM_EXISTING:
            _fail("v7_existing_node_requires_confirmed_identity")
        value = _parse_value(assertion)
        label = assertion.label or value.get("label")
        if (
            value.get("dm_kind") != existing.kind
            or not isinstance(label, str)
            or not label.strip()
            or existing.assertion_metadata.canon_state != "canonical"
        ):
            _fail("v7_existence_core_mismatch")
        ids, evidence = _assertion_evidence(
            assertion,
            kind="node",
            reviewed_contribution_id=self.reviewed.contribution_id,
            reviewed_source_artifact_id=self.reviewed.source_artifact_id,
            reviewed_source_revision_id=self.reviewed.source_revision_id,
            graph_object_id=existing.object_id,
            world_id=self.record.world_id,
            sources=self.source_snapshot,
        )
        proof = ObjectExistenceAssertionV7Record(
            label=label,
            kind=existing.kind,
            assertion_metadata=_metadata(
                assertion,
                assertion_id=assertion.assertion_id,
                evidence_ref_ids=ids,
                session_refs=_session_refs(assertion, value),
            ),
        )
        self._register_evidence(evidence)
        # Reuse the reviewed alias merge, then retain the original core proof.
        super().apply_node(assertion)
        merged = self.objects[existing.object_id]
        original = GraphObjectV7Record.model_validate(existing.model_dump(mode="json"))
        self.objects[existing.object_id] = merged.model_copy(
            update={
                "assertion_metadata": original.assertion_metadata,
                "independent_existence_assertions": [
                    *original.independent_existence_assertions,
                    proof,
                ],
            }
        )

    def apply_alias(self, assertion: GraphContributionAssertionV2) -> None:
        target = assertion.subject_object_id
        existing = self.objects.get(target) if target is not None else None
        super().apply_alias(assertion)
        if existing is not None:
            self.objects[existing.object_id] = self.objects[existing.object_id].model_copy(
                update={"assertion_metadata": existing.assertion_metadata}
            )

    def result_payload(self, parent_payload: UnionGraphV6Payload) -> dict[str, Any]:
        # Historical serializer is statically V6 and would erase V7 proof fields.
        return UnionGraphV7Payload(
            world_id=parent_payload.world_id,
            semantic_profile=parent_payload.semantic_profile,
            relationship_endpoint_aspect_schema=parent_payload.relationship_endpoint_aspect_schema,
            object_existence_support_schema=EXISTENCE_SUPPORT_SCHEMA,
            objects=[
                GraphObjectV7Record.model_validate(self.objects[oid].model_dump(mode="json"))
                for oid in [*self.object_order, *sorted(self.new_object_ids)]
                if oid in self.objects
            ],
            relationships=[
                self.relationships[rid]
                for rid in [*self.relationship_order, *sorted(self.new_relationship_ids)]
            ],
            evidence_refs=[
                self.evidence[eid] for eid in [*self.evidence_order, *sorted(self.new_evidence_ids)]
            ],
        ).model_dump(mode="json")


def materialize_finalized_review_v7(
    state: ContributionReviewStateV3 | ContributionReviewStateV4 | ContributionReviewStateV5,
    *,
    parent: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    source_snapshot: SourceProvenanceSnapshot,
    source_description_correction_proof: SourceDescriptionCorrectionProof | None = None,
) -> FinalizedReviewGraphMaterialization:
    if isinstance(state, ContributionReviewStateV5):
        state = ContributionReviewStateV5.model_validate(state.model_dump(mode="json"))
    elif isinstance(state, ContributionReviewStateV4):
        state = ContributionReviewStateV4.model_validate(state.model_dump(mode="json"))
    elif isinstance(state, ContributionReviewStateV3):
        state = ContributionReviewStateV3.model_validate(state.model_dump(mode="json"))
    else:
        _fail("v7_requires_typed_review")
    parent = _reload_parent(parent)
    record = state.record
    plan = record.plan_ref
    if (
        parent.revision.graph_schema not in {GRAPH_SCHEMA_V6, GRAPH_SCHEMA_V7}
        or parent.revision.world_id != record.world_id
        or parent.revision.revision_id != plan.expected_parent_revision_id
        or parent.revision.graph_schema != plan.base_graph_schema
        or parent.revision.graph_payload_sha256 != plan.base_graph_payload_sha256
    ):
        _fail("parent_binding_mismatch")
    snapshot = graph_reader.parse(
        graph_schema=parent.revision.graph_schema,
        graph_payload=parent.graph_payload,
    )
    if snapshot.semantic_profile_ref != plan.semantic_profile:
        _fail("profile_mismatch")
    raw = copy.deepcopy(parent.graph_payload)
    raw["object_existence_support_schema"] = EXISTENCE_SUPPORT_SCHEMA
    typed = UnionGraphV7Payload.model_validate(raw)
    legacy = copy.deepcopy(raw)
    legacy.pop("object_existence_support_schema")
    for obj in legacy["objects"]:
        obj.pop("independent_existence_assertions", None)
    legacy_parent = UnionGraphV6Payload.model_validate(legacy)
    workspace = _V7Materialization(
        state=state,
        parent_payload=legacy_parent,
        parent_snapshot=snapshot,
        source_snapshot=source_snapshot,
    )
    workspace.objects = {obj.object_id: obj for obj in typed.objects}
    accepted = [
        a
        for a in state.reviewed_contribution.assertions
        if a.acceptance_state is AcceptanceState.ACCEPTED
        and a.identity_resolution_outcome not in NON_MUTATING_IDENTITY_OUTCOMES
    ]
    for assertion in accepted:
        _reject_mechanics_binding(assertion)
    for assertion in accepted:
        if assertion.assertion_kind == "node":
            workspace.apply_node(assertion)
    for assertion in accepted:
        kind = assertion.assertion_kind
        if kind == "node":
            continue
        if (
            kind == "property"
            and isinstance(state, (ContributionReviewStateV4, ContributionReviewStateV5))
            and isinstance(assertion, GraphContributionAssertionV4)
        ):
            if assertion.subject_object_id not in workspace.objects:
                _fail("orphan_accepted_property")
            row, evidence = _property(state, assertion, source_snapshot)
            workspace._register_evidence(evidence)
            obj = workspace.objects[assertion.subject_object_id]
            workspace.objects[obj.object_id] = obj.model_copy(
                update={"properties": [*obj.properties, row]}
            )
            workspace.updated_object_ids.add(obj.object_id)
        elif kind == "edge":
            workspace.apply_edge(assertion)
        elif kind == "alias":
            workspace.apply_alias(assertion)
        elif kind in {"attribute", "evidence_ref"}:
            workspace.apply_evidence_only(assertion)
        else:
            _fail("unsupported_assertion_kind")
    if source_description_correction_proof is not None and not (
        source_description_correction_proof.matches(state, parent)
    ):
        _fail("source_description_correction_proof_mismatch")
    workspace.apply_corrections(source_description_correction_proof)
    payload = workspace.result_payload(legacy_parent)
    output = graph_reader.parse(graph_schema=GRAPH_SCHEMA_V7, graph_payload=payload)
    if output.world_id != record.world_id or output.semantic_profile_ref != plan.semantic_profile:
        _fail("output_graph_validation")
    if isinstance(state, (ContributionReviewStateV4, ContributionReviewStateV5)):
        _validate_reviewed_property_delta(
            state,
            parent=parent,
            graph_payload=payload,
            source_snapshot=source_snapshot,
        )
    return FinalizedReviewGraphMaterialization(
        world_id=record.world_id,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=plan.expected_parent_revision_id,
        parent_graph_payload_sha256=plan.base_graph_payload_sha256,
        graph_schema=GRAPH_SCHEMA_V7,
        graph_payload=payload,
        graph_payload_sha256=canonical_sha256(payload),
    )
