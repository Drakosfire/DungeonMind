"""Pure B.2f-0 characterization of finalized review graph effects.

This module is deliberately test-only. It does not materialize graph objects,
write a repository row, publish a revision, or assign durable relationship IDs.
Its output is a deterministic characterization fixture for the later B.2f-a
materializer.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import (
    GraphSnapshotReader,
    ParsedGraphSnapshot,
)
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    GraphContributionAssertion,
)
from dungeonmind.contracts.contribution_review import ContributionReviewState
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.domain.canonical import canonical_sha256

CHARACTERIZATION_VERSION = "b2f-0-review-effect-spec-v1"


class ReviewEffectCharacterizationError(ValueError):
    """The finalized review cannot be characterized against this parent."""


def _canonical_unique(values: list[Any]) -> list[Any]:
    return sorted(
        {canonical_sha256(value): value for value in values}.values(),
        key=canonical_sha256,
    )


def _assert_same(value: object, expected: object, message: str) -> None:
    if value != expected:
        raise ReviewEffectCharacterizationError(message)


def _assertion_effect(assertion: GraphContributionAssertion) -> dict[str, Any]:
    return {
        "assertion_id": assertion.assertion_id,
        "assertion_kind": assertion.assertion_kind,
        "subject_object_id": assertion.subject_object_id,
        "object_object_id": assertion.object_object_id,
        "predicate": assertion.predicate,
        "label": assertion.label,
        "value": assertion.value,
        "evidence_ref_ids": sorted(
            ref.evidence_ref_id for ref in assertion.evidence_refs
        ),
        "source_artifact_id": assertion.source_artifact_id,
        "source_revision_id": assertion.source_revision_id,
        "campaign_scope": assertion.campaign_scope,
        "temporal_scope": assertion.temporal_scope,
        "visibility": assertion.visibility.value,
        "epistemic_kind": assertion.epistemic_kind.value,
    }


def _lineage(assertions: list[GraphContributionAssertion]) -> list[dict[str, str | None]]:
    return _canonical_unique(
        [
            {
                "source_artifact_id": assertion.source_artifact_id,
                "source_revision_id": assertion.source_revision_id,
            }
            for assertion in assertions
        ]
    )


def characterize_finalized_review(
    state: ContributionReviewState,
    *,
    parent_revision: WorldGraphRevision,
    parent_graph_payload: dict[str, Any],
    graph_reader: GraphSnapshotReader,
) -> dict[str, Any]:
    """Return deterministic, write-free effects proposed by a finalized review."""

    try:
        state = ContributionReviewState.model_validate(
            state.model_dump(mode="json")
        )
    except ValidationError:
        raise ReviewEffectCharacterizationError(
            "finalized review state failed reload validation"
        ) from None

    record = state.record
    plan_ref = record.plan_ref
    if parent_revision.world_id != record.world_id:
        raise ReviewEffectCharacterizationError("parent world differs from review")
    _assert_same(
        parent_revision.revision_id,
        plan_ref.expected_parent_revision_id,
        "parent revision does not match the exact expected parent",
    )
    _assert_same(
        parent_revision.graph_schema,
        plan_ref.base_graph_schema,
        "parent graph schema differs from the pinned plan",
    )
    _assert_same(
        parent_revision.graph_payload_sha256,
        plan_ref.base_graph_payload_sha256,
        "parent graph payload digest differs from the pinned plan",
    )
    _assert_same(
        canonical_sha256(parent_graph_payload),
        parent_revision.graph_payload_sha256,
        "parent graph payload does not match the exact revision",
    )
    parent_snapshot: ParsedGraphSnapshot = graph_reader.parse(
        graph_schema=parent_revision.graph_schema,
        graph_payload=parent_graph_payload,
    )
    _assert_same(
        parent_snapshot.world_id,
        record.world_id,
        "parsed parent world differs from review",
    )
    _assert_same(
        parent_snapshot.graph_schema,
        plan_ref.base_graph_schema,
        "parsed parent graph schema differs from the pinned plan",
    )
    if parent_snapshot.semantic_profile_ref != plan_ref.semantic_profile:
        raise ReviewEffectCharacterizationError(
            "parent semantic profile differs from the pinned plan"
        )

    proposals = {item.candidate_id: item for item in record.identity_proposals}
    verdicts = {item.candidate_id: item for item in record.identity_verdicts}
    assertion_verdicts = {
        item.assertion_id: item.acceptance_state for item in record.assertion_verdicts
    }
    reviewed_assertions = {
        item.assertion_id: item for item in state.reviewed_contribution.assertions
    }
    accepted_assertions = [
        assertion
        for assertion in state.reviewed_contribution.assertions
        if assertion.acceptance_state is AcceptanceState.ACCEPTED
    ]
    rejected_assertion_ids = sorted(
        assertion.assertion_id
        for assertion in state.reviewed_contribution.assertions
        if assertion.acceptance_state is AcceptanceState.REJECTED
    )
    if set(reviewed_assertions) != set(assertion_verdicts):
        raise ReviewEffectCharacterizationError(
            "reviewed assertions and durable assertion verdicts do not cover the same IDs"
        )

    accepted_by_target: dict[str, list[GraphContributionAssertion]] = defaultdict(list)
    accepted_relationships: list[GraphContributionAssertion] = []
    evidence: dict[str, dict[str, Any]] = {}
    for assertion in accepted_assertions:
        verdict_state = assertion_verdicts.get(assertion.assertion_id)
        if verdict_state is not AcceptanceState.ACCEPTED:
            raise ReviewEffectCharacterizationError(
                "reviewed assertion acceptance disagrees with durable verdict"
            )
        for evidence_ref in assertion.evidence_refs:
            dumped = evidence_ref.model_dump(mode="json")
            prior = evidence.get(evidence_ref.evidence_ref_id)
            if prior is not None and prior != dumped:
                raise ReviewEffectCharacterizationError(
                    "one evidence ID has conflicting serialized content"
                )
            evidence[evidence_ref.evidence_ref_id] = dumped
        if assertion.assertion_kind == "relationship":
            accepted_relationships.append(assertion)
        else:
            if assertion.subject_object_id is None:
                raise ReviewEffectCharacterizationError(
                    "accepted node assertion has no target"
                )
            accepted_by_target[assertion.subject_object_id].append(assertion)

    identity_effects: list[dict[str, Any]] = []
    object_effects: list[dict[str, Any]] = []
    for candidate_id in sorted(proposals):
        proposal = proposals[candidate_id]
        verdict = verdicts[candidate_id]
        target = verdict.target_object_id
        if verdict.verdict.value == "reject_candidate":
            identity_effects.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_kind": proposal.candidate_kind,
                    "verdict": verdict.verdict.value,
                    "target_object_id": target,
                    "effect": "exclude_from_graph_truth",
                }
            )
            continue

        existing = parent_snapshot.objects.get(target)
        if verdict.verdict.value == "create_new":
            if existing is not None:
                raise ReviewEffectCharacterizationError(
                    "create_new target already exists in exact parent"
                )
            effect = "create_object"
            object_kind = proposal.candidate_kind
        else:
            if existing is None:
                raise ReviewEffectCharacterizationError(
                    "confirm_existing target is absent from exact parent"
                )
            if existing.kind != proposal.candidate_kind:
                raise ReviewEffectCharacterizationError(
                    "confirm_existing target kind differs from proposal"
                )
            effect = "reuse_existing_object"
            object_kind = existing.kind

        target_assertions = accepted_by_target.get(target, [])
        label_assertions = [
            item for item in target_assertions if item.assertion_kind == "label"
        ]
        if verdict.verdict.value == "create_new" and len(label_assertions) != 1:
            raise ReviewEffectCharacterizationError(
                "create_new characterization requires exactly one accepted label"
            )
        if len(label_assertions) > 1:
            raise ReviewEffectCharacterizationError(
                "characterization supports one canonical label slot per object"
            )
        summary_assertions = [
            item for item in target_assertions if item.assertion_kind == "summary"
        ]
        if len(summary_assertions) > 1:
            raise ReviewEffectCharacterizationError(
                "characterization supports one canonical summary slot per object"
            )
        aliases = sorted(
            item.value
            for item in target_assertions
            if item.assertion_kind == "alias" and item.value is not None
        )
        normalized_aliases = [value.casefold().strip() for value in aliases]
        if len(normalized_aliases) != len(set(normalized_aliases)):
            raise ReviewEffectCharacterizationError(
                "accepted aliases contain duplicate normalized values"
            )
        parent_aliases = [] if existing is None else list(existing.aliases)
        if existing is not None:
            parent_alias_keys = {
                value.casefold().strip() for value in parent_aliases
            }
            if parent_alias_keys.intersection(normalized_aliases):
                raise ReviewEffectCharacterizationError(
                    "accepted alias collides with an existing alias"
                )
        label_value = (
            label_assertions[0].label
            if label_assertions
            else (existing.label if existing is not None else None)
        )
        summary_value = (
            summary_assertions[0].value
            if summary_assertions
            else (existing.summary if existing is not None else None)
        )
        label_operation = (
            "replace"
            if existing is not None and label_assertions
            else "retain"
            if existing is not None
            else "set"
        )
        summary_operation = (
            "replace"
            if existing is not None and summary_assertions
            else "retain"
            if existing is not None
            else "set"
            if summary_assertions
            else "omit"
        )
        alias_operation = (
            "append"
            if existing is not None and aliases
            else "retain"
            if existing is not None
            else "set"
        )
        proposed_fields = {
            "label": {
                "operation": label_operation,
                "expected_parent_value": (
                    existing.label if existing is not None else None
                ),
                "result_value": label_value,
                "assertion_ids": [
                    item.assertion_id for item in label_assertions
                ],
            },
            "aliases": {
                "operation": alias_operation,
                "expected_parent_values": parent_aliases,
                "added_values": aliases if existing is not None else [],
                "result_values": (
                    parent_aliases + aliases if existing is not None else aliases
                ),
                "assertion_ids": [
                    item.assertion_id
                    for item in target_assertions
                    if item.assertion_kind == "alias"
                ],
            },
            "summary": {
                "operation": summary_operation,
                "expected_parent_value": (
                    existing.summary if existing is not None else None
                ),
                "result_value": summary_value,
                "assertion_ids": [
                    item.assertion_id for item in summary_assertions
                ],
            },
        }
        created_fields = (
            {
                "label": label_assertions[0].label,
                "aliases": aliases,
                "summary": (
                    summary_assertions[0].value
                    if summary_assertions
                    else None
                ),
            }
            if verdict.verdict.value == "create_new"
            else None
        )
        parent_object = (
            None
            if existing is None
            else {"object_id": existing.object_id, "kind": existing.kind}
        )
        all_target_evidence = sorted(
            {
                ref.evidence_ref_id
                for item in target_assertions
                for ref in item.evidence_refs
            }
        )
        identity_effects.append(
            {
                "candidate_id": candidate_id,
                "candidate_kind": proposal.candidate_kind,
                "verdict": verdict.verdict.value,
                "target_object_id": target,
                "effect": effect,
            }
        )
        object_effects.append(
            {
                "object_id": target,
                "kind": object_kind,
                "effect": effect,
                "parent_object": parent_object,
                "created_fields": created_fields,
                "proposed_fields": proposed_fields,
                "accepted_assertion_ids": sorted(
                    item.assertion_id for item in target_assertions
                ),
                "assertions": [
                    _assertion_effect(item)
                    for item in sorted(
                        target_assertions, key=lambda item: item.assertion_id
                    )
                ],
                "evidence_ref_ids": all_target_evidence,
                "source_lineage": _lineage(target_assertions),
                "campaign_scopes": sorted(
                    {
                        item.campaign_scope
                        for item in target_assertions
                        if item.campaign_scope is not None
                    }
                ),
                "temporal_scopes": _canonical_unique(
                    [item.temporal_scope for item in target_assertions]
                ),
                "visibilities": sorted({item.visibility.value for item in target_assertions}),
                "epistemic_kinds": sorted(
                    {item.epistemic_kind.value for item in target_assertions}
                ),
            }
        )

    relationship_groups: dict[
        tuple[str, str, str], list[GraphContributionAssertion]
    ] = defaultdict(list)
    for assertion in accepted_relationships:
        key = (
            assertion.subject_object_id or "",
            assertion.predicate or "",
            assertion.object_object_id or "",
        )
        relationship_groups[key].append(assertion)

    identity_effect_by_target = {
        item["target_object_id"]: item["effect"]
        for item in identity_effects
        if item["effect"] != "exclude_from_graph_truth"
    }
    relationship_effects: list[dict[str, Any]] = []
    for (subject, predicate, object_id), assertions in sorted(relationship_groups.items()):
        if len(assertions) != 1:
            raise ReviewEffectCharacterizationError(
                "duplicate accepted relationship triples are unsupported"
            )
        endpoint_effects = []
        for endpoint in (subject, object_id):
            effect = identity_effect_by_target.get(endpoint)
            if effect is None:
                if endpoint not in parent_snapshot.objects:
                    raise ReviewEffectCharacterizationError(
                        "relationship endpoint is absent from review and parent"
                    )
                effect = "reuse_existing_object"
            endpoint_effects.append(
                {
                    "object_id": endpoint,
                    "kind": (
                        next(
                            item["kind"]
                            for item in object_effects
                            if item["object_id"] == endpoint
                        )
                        if endpoint in identity_effect_by_target
                        else parent_snapshot.objects[endpoint].kind
                    ),
                    "effect": effect,
                }
            )
        existing_ids = sorted(
            rel.relationship_id
            for rel in parent_snapshot.relationships.values()
            if (
                rel.subject_object_id,
                rel.predicate,
                rel.object_object_id,
            )
            == (subject, predicate, object_id)
        )
        if existing_ids:
            raise ReviewEffectCharacterizationError(
                "pre-existing relationship triples are unsupported"
            )
        relationship_effects.append(
            {
                "relationship_key": {
                    "subject_object_id": subject,
                    "predicate": predicate,
                    "object_object_id": object_id,
                },
                "endpoint_effects": endpoint_effects,
                "effect": "propose_new_relationship",
                "source_assertion_ids": sorted(
                    item.assertion_id for item in assertions
                ),
                "assertions": [
                    _assertion_effect(item)
                    for item in sorted(assertions, key=lambda item: item.assertion_id)
                ],
                "evidence_ref_ids": sorted(
                    {
                        ref.evidence_ref_id
                        for item in assertions
                        for ref in item.evidence_refs
                    }
                ),
                "source_lineage": _lineage(assertions),
                "campaign_scopes": sorted(
                    {
                        item.campaign_scope
                        for item in assertions
                        if item.campaign_scope is not None
                    }
                ),
                "temporal_scopes": _canonical_unique(
                    [item.temporal_scope for item in assertions]
                ),
                "visibilities": sorted({item.visibility.value for item in assertions}),
                "epistemic_kinds": sorted(
                    {item.epistemic_kind.value for item in assertions}
                ),
            }
        )

    material = {
        "characterization_version": CHARACTERIZATION_VERSION,
        "review_binding": {
            "world_id": record.world_id,
            "campaign_id": record.campaign_id,
            "review_id": record.review_id,
            "operation_id": record.operation_id,
            "source_plan_id": plan_ref.source_plan_id,
            "review_intent_sha256": record.review_intent_sha256,
            "confirmation_id": record.confirmation_id,
            "expected_parent_revision_id": plan_ref.expected_parent_revision_id,
        },
        "parent_pin": {
            "revision_id": parent_revision.revision_id,
            "graph_schema": parent_revision.graph_schema,
            "graph_payload_sha256": parent_revision.graph_payload_sha256,
            "semantic_profile": plan_ref.semantic_profile.model_dump(mode="json"),
        },
        "identity_effects": identity_effects,
        "object_effects": sorted(object_effects, key=lambda item: item["object_id"]),
        "relationship_effects": relationship_effects,
        "accepted_evidence": {
            evidence_id: evidence[evidence_id] for evidence_id in sorted(evidence)
        },
        "rejected_assertion_ids": rejected_assertion_ids,
        "rejected_assertions_excluded_from_graph_truth": True,
        "durable_writes": [],
        "graph_head_effect": "unchanged",
        "identity_decision_effect": "unchanged",
    }
    return {
        **material,
        "effect_digest": canonical_sha256(material),
    }
