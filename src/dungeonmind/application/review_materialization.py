"""Pure materialization of one finalized review into a v3 graph payload.

This module owns payload transformation only.  It does not construct a
revision, observe or advance a graph head, call a repository, append identity
decisions, or expose a transport surface.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, NoReturn

from ..contracts.contribution import (
    AcceptanceState,
    GraphContributionAssertion,
)
from ..contracts.contribution_review import (
    ContributionIdentityVerdictKind,
    ContributionReviewState,
)
from ..contracts.graph import StoredGraphRevision
from ..domain.canonical import canonical_json, canonical_sha256
from ..domain.errors import ContributionMaterializationError
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot

GRAPH_SCHEMA_V3 = "dm_union_graph_v3"
RELATIONSHIP_ID_SCHEMA = "dm_review_relationship_id_v1"


@dataclass(frozen=True, init=False)
class FinalizedReviewGraphMaterialization:
    """Ephemeral result with a private canonical payload and copy-on-read access."""

    world_id: str
    review_id: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    review_intent_sha256: str
    confirmation_id: str
    operation_id: str
    expected_parent_revision_id: str
    parent_graph_payload_sha256: str
    graph_schema: str
    graph_payload_sha256: str
    _graph_payload_json: str = field(repr=False)

    def __init__(
        self,
        world_id: str,
        review_id: str,
        reviewed_contribution_id: str,
        reviewed_contribution_sha256: str,
        review_intent_sha256: str,
        confirmation_id: str,
        operation_id: str,
        expected_parent_revision_id: str,
        parent_graph_payload_sha256: str,
        graph_schema: str,
        graph_payload: dict[str, Any],
        graph_payload_sha256: str,
    ) -> None:
        payload = copy.deepcopy(graph_payload)
        if graph_schema != GRAPH_SCHEMA_V3:
            raise ValueError("materialization result has an unsupported graph schema")
        if canonical_sha256(payload) != graph_payload_sha256:
            raise ValueError("materialization result payload digest does not match")
        object.__setattr__(self, "world_id", world_id)
        object.__setattr__(self, "review_id", review_id)
        object.__setattr__(self, "reviewed_contribution_id", reviewed_contribution_id)
        object.__setattr__(self, "reviewed_contribution_sha256", reviewed_contribution_sha256)
        object.__setattr__(self, "review_intent_sha256", review_intent_sha256)
        object.__setattr__(self, "confirmation_id", confirmation_id)
        object.__setattr__(self, "operation_id", operation_id)
        object.__setattr__(self, "expected_parent_revision_id", expected_parent_revision_id)
        object.__setattr__(
            self,
            "parent_graph_payload_sha256",
            parent_graph_payload_sha256,
        )
        object.__setattr__(self, "graph_schema", graph_schema)
        object.__setattr__(self, "graph_payload_sha256", graph_payload_sha256)
        object.__setattr__(self, "_graph_payload_json", canonical_json(payload))

    @property
    def graph_payload(self) -> dict[str, Any]:
        """Return a fresh JSON-compatible copy that cannot mutate this result."""
        return json.loads(self._graph_payload_json)


def _fail(reason: str, **details: Any) -> NoReturn:
    raise ContributionMaterializationError(reason, details=details) from None


def _reload_state(state: ContributionReviewState) -> ContributionReviewState:
    try:
        return ContributionReviewState.model_validate(state.model_dump(mode="json"))
    except Exception:
        _fail("state_reload_validation")


def _reload_parent(parent: StoredGraphRevision) -> StoredGraphRevision:
    try:
        reloaded = StoredGraphRevision.model_validate(parent.model_dump(mode="json"))
        actual_digest = canonical_sha256(reloaded.graph_payload)
    except Exception:
        _fail("parent_reload_validation")
    if actual_digest != reloaded.revision.graph_payload_sha256:
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=reloaded.revision.revision_id,
        )
    return reloaded


def _parse_parent(
    parent: StoredGraphRevision,
    *,
    state: ContributionReviewState,
    graph_reader: GraphSnapshotReader,
) -> ParsedGraphSnapshot:
    record = state.record
    plan_ref = record.plan_ref
    revision = parent.revision
    if revision.graph_schema != GRAPH_SCHEMA_V3:
        _fail("unsupported_graph_schema", graph_schema=revision.graph_schema)
    if (
        revision.world_id != record.world_id
        or revision.revision_id != plan_ref.expected_parent_revision_id
        or revision.graph_schema != plan_ref.base_graph_schema
        or revision.graph_payload_sha256 != plan_ref.base_graph_payload_sha256
    ):
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=revision.revision_id,
            expected_parent_revision_id=plan_ref.expected_parent_revision_id,
            graph_schema=revision.graph_schema,
        )
    try:
        reader_payload = copy.deepcopy(parent.graph_payload)
        snapshot = graph_reader.parse(
            graph_schema=revision.graph_schema,
            graph_payload=reader_payload,
        )
    except Exception:
        _fail("parent_reload_validation", graph_schema=revision.graph_schema)
    if (
        snapshot.world_id != record.world_id
        or snapshot.graph_schema != plan_ref.base_graph_schema
        or snapshot.semantic_profile_ref != plan_ref.semantic_profile
    ):
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=revision.revision_id,
            graph_schema=revision.graph_schema,
        )
    return snapshot


def _raw_records(
    payload: dict[str, Any],
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    records = payload.get(field_name, [])
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        _fail("parent_reload_validation", field_name=field_name)
    return records


def _raw_nodes_by_id(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    nodes = _raw_records(payload, field_name="nodes")
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        object_id = node.get("object_id")
        if not isinstance(object_id, str) or object_id in by_id:
            _fail("parent_reload_validation", field_name="nodes")
        by_id[object_id] = node
    return nodes, by_id


def _evidence_ids(assertion: GraphContributionAssertion) -> list[str]:
    return sorted({ref.evidence_ref_id for ref in assertion.evidence_refs})


def _alias_record(assertion: GraphContributionAssertion) -> dict[str, Any]:
    if assertion.value is None:
        _fail("orphan_accepted_assertion")
    return {
        "assertion_id": assertion.assertion_id,
        "alias": assertion.value,
        "evidence_ref_ids": _evidence_ids(assertion),
    }


def _summary_record(assertion: GraphContributionAssertion) -> dict[str, Any]:
    if assertion.value is None:
        _fail("orphan_accepted_assertion")
    return {
        "assertion_id": assertion.assertion_id,
        "summary": assertion.value,
        "evidence_ref_ids": _evidence_ids(assertion),
    }


def _relationship_id(
    *,
    world_id: str,
    review_id: str,
    reviewed_contribution_id: str,
    expected_parent_revision_id: str,
    assertion: GraphContributionAssertion,
) -> str:
    if (
        assertion.subject_object_id is None
        or assertion.predicate is None
        or assertion.object_object_id is None
    ):
        _fail("orphan_accepted_assertion")
    material = {
        "schema": RELATIONSHIP_ID_SCHEMA,
        "world_id": world_id,
        "review_id": review_id,
        "reviewed_contribution_id": reviewed_contribution_id,
        "expected_parent_revision_id": expected_parent_revision_id,
        "source_assertion_id": assertion.assertion_id,
        "subject_object_id": assertion.subject_object_id,
        "predicate": assertion.predicate,
        "object_object_id": assertion.object_object_id,
    }
    return f"rel:{canonical_sha256(material)[:32]}"


def _expected_object_fields(node: dict[str, Any]) -> dict[str, Any]:
    summary = node.get("summary_assertion")
    return {
        "kind": node.get("kind"),
        "label": node.get("label"),
        "core_evidence_ref_ids": list(node.get("evidence_ref_ids", [])),
        "aliases": [
            item.get("alias", item.get("value"))
            for item in node.get("alias_assertions", [])
        ],
        "alias_assertion_ids": [
            item.get("assertion_id") for item in node.get("alias_assertions", [])
        ],
        "alias_assertions": copy.deepcopy(node.get("alias_assertions", [])),
        "summary": None if summary is None else summary.get("summary"),
        "summary_assertion_id": None if summary is None else summary.get("assertion_id"),
        "summary_assertion": copy.deepcopy(summary),
    }


def _output_object_matches(
    snapshot: ParsedGraphSnapshot,
    *,
    object_id: str,
    expected: dict[str, Any],
) -> bool:
    obj = snapshot.objects.get(object_id)
    if obj is None:
        return False
    actual_alias_assertions = [
        {
            "assertion_id": item.assertion_id,
            "alias": item.alias,
            "evidence_ref_ids": list(item.evidence_ref_ids),
        }
        for item in obj.admitted_alias_assertions
    ]
    actual_summary_assertion = (
        None
        if obj.admitted_summary_assertion is None
        else {
            "assertion_id": obj.admitted_summary_assertion.assertion_id,
            "summary": obj.admitted_summary_assertion.summary,
            "evidence_ref_ids": list(obj.admitted_summary_assertion.evidence_ref_ids),
        }
    )
    return (
        obj.kind == expected["kind"]
        and obj.label == expected["label"]
        and obj.core_evidence_ref_ids == expected["core_evidence_ref_ids"]
        and obj.aliases == expected["aliases"]
        and [item.assertion_id for item in obj.admitted_alias_assertions]
        == expected["alias_assertion_ids"]
        and obj.summary == expected["summary"]
        and (
            None
            if obj.admitted_summary_assertion is None
            else obj.admitted_summary_assertion.assertion_id
        )
        == expected["summary_assertion_id"]
        and actual_alias_assertions == expected["alias_assertions"]
        and actual_summary_assertion == expected["summary_assertion"]
    )


def materialize_finalized_review(
    state: ContributionReviewState,
    *,
    parent: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewGraphMaterialization:
    """Materialize one finalized review into one validated v3 graph payload."""
    verified_state = _reload_state(state)
    verified_parent = _reload_parent(parent)
    parent_snapshot = _parse_parent(
        verified_parent,
        state=verified_state,
        graph_reader=graph_reader,
    )
    record = verified_state.record
    plan_ref = record.plan_ref
    payload = copy.deepcopy(verified_parent.graph_payload)
    parent_nodes, parent_nodes_by_id = _raw_nodes_by_id(payload)
    parent_relationships = _raw_records(payload, field_name="relationships")
    parent_evidence = _raw_records(payload, field_name="evidence_refs")

    proposals_by_candidate = {
        proposal.candidate_id: proposal for proposal in record.identity_proposals
    }
    verdicts_by_candidate = {
        verdict.candidate_id: verdict for verdict in record.identity_verdicts
    }
    verdicts_by_assertion = {
        verdict.assertion_id: verdict.acceptance_state
        for verdict in record.assertion_verdicts
    }
    reviewed_assertions = {
        assertion.assertion_id: assertion
        for assertion in verified_state.reviewed_contribution.assertions
    }
    if set(reviewed_assertions) != set(verdicts_by_assertion):
        _fail("state_reload_validation")

    accepted_assertions = [
        assertion
        for assertion in verified_state.reviewed_contribution.assertions
        if assertion.acceptance_state is AcceptanceState.ACCEPTED
    ]
    accepted_by_target: dict[str, list[GraphContributionAssertion]] = defaultdict(list)
    accepted_relationships: list[GraphContributionAssertion] = []
    accepted_evidence: dict[str, dict[str, Any]] = {}
    for assertion in accepted_assertions:
        if verdicts_by_assertion.get(assertion.assertion_id) is not AcceptanceState.ACCEPTED:
            _fail("state_reload_validation")
        if not assertion.evidence_refs:
            _fail(
                "accepted_assertion_missing_graph_evidence",
                assertion_id=assertion.assertion_id,
            )
        for evidence_ref in assertion.evidence_refs:
            evidence_payload = evidence_ref.model_dump(mode="json")
            prior = accepted_evidence.get(evidence_ref.evidence_ref_id)
            if prior is not None and prior != evidence_payload:
                _fail(
                    "accepted_evidence_conflict",
                    evidence_ref_id=evidence_ref.evidence_ref_id,
                )
            accepted_evidence[evidence_ref.evidence_ref_id] = evidence_payload
        if assertion.assertion_kind == "relationship":
            accepted_relationships.append(assertion)
            continue
        target = assertion.subject_object_id
        if target is None or target not in {
            verdict.target_object_id for verdict in record.identity_verdicts
        }:
            _fail(
                "orphan_accepted_assertion",
                assertion_id=assertion.assertion_id,
            )
        accepted_by_target[target].append(assertion)

    parent_assertion_ids = {
        assertion.assertion_id
        for obj in parent_snapshot.objects.values()
        for assertion in (
            *obj.admitted_alias_assertions,
            *(
                [obj.admitted_summary_assertion]
                if obj.admitted_summary_assertion is not None
                else []
            ),
        )
    }
    accepted_graph_assertion_ids = {
        assertion.assertion_id
        for assertion in accepted_assertions
        if assertion.assertion_kind in {"alias", "summary"}
    }
    colliding_assertion_ids = sorted(parent_assertion_ids & accepted_graph_assertion_ids)
    if colliding_assertion_ids:
        _fail(
            "parent_assertion_id_collision",
            assertion_ids=colliding_assertion_ids,
        )
    colliding_evidence_ids = sorted(set(parent_snapshot.evidence) & set(accepted_evidence))
    if colliding_evidence_ids:
        _fail("parent_evidence_id_collision", evidence_ref_ids=colliding_evidence_ids)

    created_nodes: dict[str, dict[str, Any]] = {}
    materialized_nodes: dict[str, dict[str, Any]] = {}
    expected_output_objects: dict[str, dict[str, Any]] = {}
    expected_output_relationships: dict[str, dict[str, Any]] = {}
    created_object_ids: set[str] = set()
    updated_object_ids: set[str] = set()

    for candidate_id in sorted(proposals_by_candidate):
        proposal = proposals_by_candidate[candidate_id]
        verdict = verdicts_by_candidate[candidate_id]
        target = verdict.target_object_id
        if verdict.verdict is ContributionIdentityVerdictKind.REJECT_CANDIDATE:
            continue

        existing_view = parent_snapshot.objects.get(target)
        existing_node = parent_nodes_by_id.get(target)
        if verdict.verdict is ContributionIdentityVerdictKind.CREATE_NEW:
            if existing_view is not None or existing_node is not None or target in created_nodes:
                _fail("parent_binding_mismatch", object_id=target)
            effect_kind = proposal.candidate_kind
        else:
            if existing_view is None:
                _fail("parent_binding_mismatch", object_id=target)
            if existing_node is None:
                _fail("parent_binding_mismatch", object_id=target)
            if existing_view.kind != proposal.candidate_kind:
                _fail("parent_binding_mismatch", object_id=target)
            effect_kind = existing_view.kind

        target_assertions = accepted_by_target.get(target, [])
        label_assertions = [
            assertion
            for assertion in target_assertions
            if assertion.assertion_kind == "label"
        ]
        summary_assertions = [
            assertion
            for assertion in target_assertions
            if assertion.assertion_kind == "summary"
        ]
        alias_assertions = sorted(
            (
                assertion
                for assertion in target_assertions
                if assertion.assertion_kind == "alias"
            ),
            key=lambda assertion: assertion.assertion_id,
        )
        if verdict.verdict is ContributionIdentityVerdictKind.CREATE_NEW:
            if len(label_assertions) != 1:
                _fail("orphan_accepted_assertion", object_id=target)
        elif len(label_assertions) > 1:
            _fail("unsupported_field_shape", object_id=target)
        if len(summary_assertions) > 1:
            _fail("unsupported_field_shape", object_id=target)

        alias_values = [
            assertion.value for assertion in alias_assertions if assertion.value is not None
        ]
        normalized_aliases = [value.casefold().strip() for value in alias_values]
        if len(normalized_aliases) != len(set(normalized_aliases)):
            _fail("unsupported_field_shape", object_id=target)
        if existing_view is not None:
            existing_aliases = {
                value.casefold().strip() for value in existing_view.aliases
            }
            if existing_aliases & set(normalized_aliases):
                _fail("unsupported_field_shape", object_id=target)

        label_assertion = label_assertions[0] if label_assertions else None
        summary_assertion = summary_assertions[0] if summary_assertions else None
        if label_assertion is not None:
            label = label_assertion.label
            if label is None:
                _fail("orphan_accepted_assertion", object_id=target)
            core_evidence_ids = _evidence_ids(label_assertion)
        else:
            if existing_view is None:
                _fail("orphan_accepted_assertion", object_id=target)
            label = existing_view.label
            core_evidence_ids = list(existing_view.core_evidence_ref_ids)

        if verdict.verdict is ContributionIdentityVerdictKind.CREATE_NEW:
            node = {
                "object_id": target,
                "kind": effect_kind,
                "label": label,
                "evidence_ref_ids": core_evidence_ids,
                "alias_assertions": [_alias_record(assertion) for assertion in alias_assertions],
                "summary_assertion": (
                    _summary_record(summary_assertion)
                    if summary_assertion is not None
                    else None
                ),
            }
            created_nodes[target] = node
            materialized_nodes[target] = node
            created_object_ids.add(target)
        else:
            if existing_node is None:
                _fail("parent_binding_mismatch", object_id=target)
            node = copy.deepcopy(existing_node)
            if label_assertion is not None:
                node["label"] = label
                node["evidence_ref_ids"] = core_evidence_ids
            if alias_assertions:
                node["alias_assertions"] = [
                    *node.get("alias_assertions", []),
                    *[_alias_record(assertion) for assertion in alias_assertions],
                ]
            if summary_assertion is not None:
                node["summary_assertion"] = _summary_record(summary_assertion)
            materialized_nodes[target] = node
            updated_object_ids.add(target)
        expected_output_objects[target] = _expected_object_fields(node)

    for object_id in sorted(updated_object_ids):
        node_index = next(
            index for index, node in enumerate(parent_nodes) if node["object_id"] == object_id
        )
        parent_nodes[node_index] = copy.deepcopy(materialized_nodes[object_id])

    payload["nodes"] = [*parent_nodes, *[created_nodes[key] for key in sorted(created_nodes)]]
    parent_relationship_ids = {
        relationship["relationship_id"] for relationship in parent_relationships
    }
    existing_triples = {
        (
            relationship.subject_object_id,
            relationship.predicate,
            relationship.object_object_id,
        )
        for relationship in parent_snapshot.relationships.values()
    }
    resulting_object_ids = set(parent_snapshot.objects) | created_object_ids
    relationship_groups: dict[
        tuple[str, str, str], list[GraphContributionAssertion]
    ] = defaultdict(list)
    for assertion in accepted_relationships:
        if (
            assertion.subject_object_id is None
            or assertion.predicate is None
            or assertion.object_object_id is None
        ):
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        relationship_groups[
            (
                assertion.subject_object_id,
                assertion.predicate,
                assertion.object_object_id,
            )
        ].append(assertion)

    new_relationships: dict[str, dict[str, Any]] = {}
    for (subject, predicate, object_id), assertions in sorted(relationship_groups.items()):
        if len(assertions) != 1:
            _fail("duplicate_relationship_triple")
        if (subject, predicate, object_id) in existing_triples:
            _fail("preexisting_relationship_triple")
        if subject not in resulting_object_ids or object_id not in resulting_object_ids:
            _fail("orphan_accepted_assertion")
        relationship_id = _relationship_id(
            world_id=record.world_id,
            review_id=record.review_id,
            reviewed_contribution_id=record.reviewed_contribution_id,
            expected_parent_revision_id=plan_ref.expected_parent_revision_id,
            assertion=assertions[0],
        )
        if relationship_id in parent_relationship_ids or relationship_id in new_relationships:
            _fail("relationship_id_collision", relationship_id=relationship_id)
        new_relationships[relationship_id] = {
            "relationship_id": relationship_id,
            "subject_object_id": subject,
            "predicate": predicate,
            "object_object_id": object_id,
            "evidence_ref_ids": _evidence_ids(assertions[0]),
        }
        expected_output_relationships[relationship_id] = copy.deepcopy(
            new_relationships[relationship_id]
        )
    payload["relationships"] = [
        *parent_relationships,
        *[new_relationships[key] for key in sorted(new_relationships)],
    ]
    payload["evidence_refs"] = [
        *parent_evidence,
        *[accepted_evidence[key] for key in sorted(accepted_evidence)],
    ]

    try:
        reader_payload = copy.deepcopy(payload)
        output_snapshot = graph_reader.parse(
            graph_schema=GRAPH_SCHEMA_V3,
            graph_payload=reader_payload,
        )
    except Exception:
        _fail("output_graph_validation")
    if (
        output_snapshot.world_id != record.world_id
        or output_snapshot.graph_schema != GRAPH_SCHEMA_V3
        or output_snapshot.semantic_profile_ref != plan_ref.semantic_profile
    ):
        _fail("output_graph_validation")
    for object_id in (*sorted(created_object_ids), *sorted(updated_object_ids)):
        if not _output_object_matches(
            output_snapshot,
            object_id=object_id,
            expected=expected_output_objects[object_id],
        ):
            _fail("output_graph_validation")
    for relationship_id, expected in expected_output_relationships.items():
        actual = output_snapshot.relationships.get(relationship_id)
        if actual is None or (
            actual.relationship_id != expected["relationship_id"]
            or actual.subject_object_id != expected["subject_object_id"]
            or actual.predicate != expected["predicate"]
            or actual.object_object_id != expected["object_object_id"]
            or actual.evidence_ref_ids != expected["evidence_ref_ids"]
        ):
            _fail("output_graph_validation")
    for evidence_ref_id, expected in accepted_evidence.items():
        actual = output_snapshot.evidence.get(evidence_ref_id)
        if actual is None or actual.model_dump(mode="json") != expected:
            _fail("output_graph_validation")

    result_payload = copy.deepcopy(payload)
    result_digest = canonical_sha256(result_payload)
    try:
        return FinalizedReviewGraphMaterialization(
            world_id=record.world_id,
            review_id=record.review_id,
            reviewed_contribution_id=record.reviewed_contribution_id,
            reviewed_contribution_sha256=record.reviewed_contribution_sha256,
            review_intent_sha256=record.review_intent_sha256,
            confirmation_id=record.confirmation_id,
            operation_id=record.operation_id,
            expected_parent_revision_id=plan_ref.expected_parent_revision_id,
            parent_graph_payload_sha256=plan_ref.base_graph_payload_sha256,
            graph_schema=GRAPH_SCHEMA_V3,
            graph_payload=result_payload,
            graph_payload_sha256=result_digest,
        )
    except Exception:
        _fail("output_graph_validation")
