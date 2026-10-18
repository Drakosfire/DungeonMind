"""Explicit V4 reviewed properties; historical attribute semantics are unchanged."""

from __future__ import annotations

from typing import Any

from ..contracts.contribution import (
    AcceptanceState,
    GraphContributionAssertionV4,
    GraphContributionV4,
    ReviewedPropertyLiteralV1,
    parse_reviewed_property_literal,
)
from ..contracts.contribution_review_v4 import ContributionReviewStateV4
from ..contracts.evidence import EvidenceRefV2
from ..contracts.graph import StoredGraphRevision
from ..contracts.identity import IdentityOutcome
from ..domain.canonical import canonical_sha256
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from .graph_snapshot_v4 import PropertyAssertionV4Record
from .review_materialization import FinalizedReviewGraphMaterialization
from .review_materialization_v6 import (
    NON_MUTATING_IDENTITY_OUTCOMES,
    _assertion_evidence,
    _fail,
    _metadata,
    _parse_parent,
    _reject_mechanics_binding,
    _reload_parent,
    _V6Materialization,
    review_source_refs_v6,
)
from .source_description_correction import SourceDescriptionCorrectionProof
from .source_provenance_snapshot import SourceProvenanceSnapshot


def reload_review_v4(state: ContributionReviewStateV4) -> ContributionReviewStateV4:
    try:
        GraphContributionV4.model_validate(state.candidate_contribution)
        GraphContributionV4.model_validate(state.reviewed_contribution)
        return ContributionReviewStateV4.model_validate(state.model_dump(mode="json"))
    except Exception:
        _fail("state_reload_validation")


def review_source_refs_v4(
    state: ContributionReviewStateV4,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return review_source_refs_v6(reload_review_v4(state))


def _facet_ids(payload: dict[str, Any]) -> tuple[set[str], set[str]]:
    ids = []
    property_ids = set()
    object_ids = [o["object_id"] for o in payload["objects"]]
    if len(object_ids) != len(set(object_ids)):
        _fail("duplicate_property_subject")
    for obj in payload["objects"]:
        ids.append(obj["assertion_metadata"]["assertion_id"])
        facets = [*obj.get("aliases", []), *obj.get("properties", []), *obj.get("aspects", [])]
        if obj.get("summary") is not None:
            facets.append(obj["summary"])
        for facet in facets:
            ids.append(facet["assertion_metadata"]["assertion_id"])
        property_ids.update(
            p["assertion_metadata"]["assertion_id"] for p in obj.get("properties", [])
        )
    ids.extend(r["assertion_metadata"]["assertion_id"] for r in payload["relationships"])
    if len(ids) != len(set(ids)):
        _fail("cross_facet_assertion_collision")
    return set(ids), property_ids


def _accepted(state: ContributionReviewStateV4) -> list[GraphContributionAssertionV4]:
    return [
        a
        for a in state.reviewed_contribution.assertions
        if a.acceptance_state is AcceptanceState.ACCEPTED
        and a.identity_resolution_outcome not in NON_MUTATING_IDENTITY_OUTCOMES
    ]


def _preflight(state: ContributionReviewStateV4, parent: StoredGraphRevision) -> None:
    parent_ids, properties = _facet_ids(parent.graph_payload)
    new_properties = {
        a.assertion_id
        for a in state.reviewed_contribution.assertions
        if a.assertion_kind == "property"
    }
    for correction in state.reviewed_contribution.assertion_corrections:
        if (
            correction.target_assertion_id in properties | new_properties
            or correction.replacement_assertion_id in properties | new_properties
        ):
            _fail("property_correction_unsupported")
    if parent_ids.intersection(a.assertion_id for a in state.reviewed_contribution.assertions):
        _fail("cross_facet_assertion_collision")
    generated = []
    for assertion in _accepted(state):
        generated.append(assertion.assertion_id)
        if assertion.assertion_kind == "node":
            import json

            value = json.loads(assertion.value or "{}")
            aliases = value.get("aliases")
            if not isinstance(aliases, list) or not aliases:
                aliases = [assertion.label or assertion.subject_object_id]
            for alias in dict.fromkeys(str(a).casefold() for a in aliases):
                original = next(str(a) for a in aliases if str(a).casefold() == alias)
                if original.strip():
                    generated.append(f"{assertion.assertion_id}:alias:{original}")
    if len(generated) != len(set(generated)) or parent_ids.intersection(generated):
        _fail("cross_facet_assertion_collision")


def _property(
    state: ContributionReviewStateV4,
    assertion: GraphContributionAssertionV4,
    source_snapshot: SourceProvenanceSnapshot | None,
) -> tuple[PropertyAssertionV4Record, dict[str, EvidenceRefV2]]:
    literal = parse_reviewed_property_literal(assertion.value)
    if source_snapshot is None:
        _fail("property_provenance_unavailable")
    ids, evidence = _assertion_evidence(
        assertion,
        kind="property",
        reviewed_contribution_id=state.reviewed_contribution.contribution_id,
        reviewed_source_artifact_id=state.reviewed_contribution.source_artifact_id,
        reviewed_source_revision_id=state.reviewed_contribution.source_revision_id,
        graph_object_id=assertion.subject_object_id,
        world_id=state.record.world_id,
        sources=source_snapshot,
    )
    row = PropertyAssertionV4Record(
        property_term=literal.property_term,
        value=literal.value,
        assertion_metadata=_metadata(
            assertion, assertion_id=assertion.assertion_id, evidence_ref_ids=ids, session_refs=[]
        ),
    )
    return row, evidence


def capture_property_literals_v4(payload: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    """Capture raw literal types BEFORE command serialization, without old-family enforcement.

    Only strict JSON is serialized into the snapshot. Invalid raw values retain an
    explicit failure marker; custom objects never get a chance to coerce themselves.
    The publication UoW checks this snapshot only after resolving a durable V4 review.
    """
    captured: dict[str, dict[str, Any] | None] = {}
    if type(payload) is not dict or type(payload.get("objects")) is not list:
        return captured
    try:
        for obj in payload["objects"]:
            if type(obj) is not dict or type(obj.get("properties", [])) is not list:
                return {}
            for row in obj.get("properties", []):
                if type(row) is not dict or type(row.get("assertion_metadata")) is not dict:
                    return {}
                assertion_id = row["assertion_metadata"]["assertion_id"]
                if type(assertion_id) is not str:
                    continue
                if assertion_id in captured:
                    captured[assertion_id] = None
                    continue
                try:
                    literal = ReviewedPropertyLiteralV1.model_validate(
                        {
                            "schema_version": "dm_reviewed_property_literal_v1",
                            "property_term": row["property_term"],
                            "value": row["value"],
                        }
                    )
                    captured[assertion_id] = literal.model_dump(mode="json")
                except (TypeError, ValueError, KeyError):
                    captured[assertion_id] = None
    except (TypeError, ValueError, KeyError, AttributeError):
        return {}
    return captured


def validate_reviewed_property_delta_v4(
    state: ContributionReviewStateV4,
    *,
    parent: StoredGraphRevision,
    graph_payload: dict[str, Any],
    source_snapshot: SourceProvenanceSnapshot | None,
    raw_literals: dict[str, dict[str, Any] | None] | None = None,
) -> None:
    """UoW re-proves exact property facts against its locked durable review/source."""
    state = reload_review_v4(state)
    _preflight(state, parent)
    _facet_ids(graph_payload)
    new_ids = {a.assertion_id for a in _accepted(state) if a.assertion_kind == "property"}
    if raw_literals is not None:
        for assertion in _accepted(state):
            if assertion.assertion_kind != "property":
                continue
            raw = raw_literals.get(assertion.assertion_id)
            if raw is None:
                _fail("property_literal_validation")
            expected_literal = parse_reviewed_property_literal(assertion.value).model_dump(
                mode="json"
            )
            if canonical_sha256(raw) != canonical_sha256(expected_literal):
                _fail("reviewed_property_delta_mismatch")
    for obj in graph_payload["objects"]:
        for row in obj.get("properties", []):
            if row["assertion_metadata"]["assertion_id"] not in new_ids:
                continue
            try:
                ReviewedPropertyLiteralV1.model_validate(
                    {
                        "schema_version": "dm_reviewed_property_literal_v1",
                        "property_term": row["property_term"],
                        "value": row["value"],
                    }
                )
            except (TypeError, ValueError):
                _fail("property_literal_validation")
    expected = {
        o["object_id"]: list(o.get("properties", [])) for o in parent.graph_payload["objects"]
    }
    allowed = set(expected)
    allowed.update(
        a.subject_object_id
        for a in _accepted(state)
        if a.assertion_kind == "node"
        and a.identity_resolution_outcome is IdentityOutcome.CREATED_NEW
    )
    for assertion in _accepted(state):
        if assertion.assertion_kind != "property":
            continue
        if assertion.subject_object_id not in allowed:
            _fail("orphan_accepted_property")
        row, _ = _property(state, assertion, source_snapshot)
        expected.setdefault(assertion.subject_object_id, []).append(row.model_dump(mode="json"))
    actual = {o["object_id"]: o.get("properties", []) for o in graph_payload["objects"]}
    for object_id in set(expected) | set(actual):
        if canonical_sha256(actual.get(object_id, [])) != canonical_sha256(
            expected.get(object_id, [])
        ):
            _fail("reviewed_property_delta_mismatch")


def materialize_finalized_review_v4(
    state: ContributionReviewStateV4,
    *,
    parent: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    source_snapshot: SourceProvenanceSnapshot | None = None,
    source_description_correction_proof: SourceDescriptionCorrectionProof | None = None,
) -> FinalizedReviewGraphMaterialization:
    state = reload_review_v4(state)
    parent = _reload_parent(parent)
    typed_parent, snapshot = _parse_parent(parent, state=state, graph_reader=graph_reader)
    _preflight(state, parent)
    workspace = _V6Materialization(
        state=state,
        parent_payload=typed_parent,
        parent_snapshot=snapshot,
        source_snapshot=source_snapshot,
    )
    accepted = _accepted(state)
    for assertion in accepted:
        _reject_mechanics_binding(assertion)
    # Identity nodes are established first regardless of candidate array order.
    for assertion in accepted:
        if assertion.assertion_kind == "node":
            workspace.apply_node(assertion)
    for assertion in accepted:
        kind = assertion.assertion_kind
        if kind == "node":
            continue
        if kind == "property":
            subject = assertion.subject_object_id
            if subject not in workspace.objects:
                _fail("orphan_accepted_property", assertion_id=assertion.assertion_id)
            row, evidence = _property(state, assertion, source_snapshot)
            workspace._register_evidence(evidence)
            obj = workspace.objects[subject]
            workspace.objects[subject] = obj.model_copy(
                update={"properties": [*obj.properties, row]}
            )
            workspace.updated_object_ids.add(subject)
        elif kind == "edge":
            workspace.apply_edge(assertion)
        elif kind == "alias":
            workspace.apply_alias(assertion)
        elif kind in {"attribute", "evidence_ref"}:
            workspace.apply_evidence_only(assertion)
        else:
            _fail("unsupported_assertion_kind")
    if (
        source_description_correction_proof is not None
        and not source_description_correction_proof.matches(state, parent)
    ):
        _fail("source_description_correction_proof_mismatch")
    workspace.apply_corrections(source_description_correction_proof)
    payload = workspace.result_payload(typed_parent)
    live_ids, _ = _facet_ids(payload)
    if live_ids.intersection(workspace.corrected_assertion_ids):
        _fail("output_graph_validation")
    validate_reviewed_property_delta_v4(
        state, parent=parent, graph_payload=payload, source_snapshot=source_snapshot
    )
    try:
        parsed = graph_reader.parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload)
        if (
            parsed.world_id != state.record.world_id
            or parsed.semantic_profile_ref != state.record.plan_ref.semantic_profile
        ):
            _fail("output_graph_validation")
    except Exception:
        _fail("output_graph_validation")
    record = state.record
    return FinalizedReviewGraphMaterialization(
        world_id=record.world_id,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=record.plan_ref.expected_parent_revision_id,
        parent_graph_payload_sha256=record.plan_ref.base_graph_payload_sha256,
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=payload,
        graph_payload_sha256=canonical_sha256(payload),
    )
