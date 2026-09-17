"""Bounded depth-1/depth-2 neighborhood reads over one pinned KnowledgeReadContext."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from dungeonmind.domain.canonical import canonical_sha256

from .entity_reads import (
    EntityReadCompleteness,
    EntityReadSourceArtifact,
    EntityReadSourceRevision,
    _dedupe_sorted,
    _support_for_admitted,
)
from .errors import NeighborhoodReadIntegrityError
from .model import ParsedKnowledgeRevision
from .provenance import KnowledgeProvenanceSnapshot
from .read_context import KnowledgeReadContext
from .records import ParsedAssertion, ParsedEntity, ParsedEntityRefValue, ParsedEvidenceRef

MAX_NEIGHBORHOOD_SEED_COUNT = 8
ALLOWED_NEIGHBORHOOD_DEPTHS = frozenset({1, 2})

NeighborhoodCompleteness = EntityReadCompleteness
NeighborhoodSourceArtifact = EntityReadSourceArtifact
NeighborhoodSourceRevision = EntityReadSourceRevision


@dataclass(frozen=True, slots=True)
class NeighborhoodReadIdentity:
    space_id: str
    revision_id: str
    domain_contract_id: str
    domain_contract_revision: str
    semantic_profile_id: str
    semantic_profile_revision: str


@dataclass(frozen=True, slots=True)
class NeighborhoodLayerWork:
    layer: int
    frontier_entities_expanded: int
    touching_assertion_candidates: int
    deduped_candidate_assertions: int
    assertions_evaluated: int
    policy_evaluations: int
    endpoint_entity_lookups: int


@dataclass(frozen=True, slots=True)
class NeighborhoodWorkCounts:
    seed_entity_lookups: int
    frontier_entities_expanded: int
    touching_assertion_candidates: int
    deduped_candidate_assertions: int
    assertions_evaluated: int
    policy_evaluations: int
    endpoint_entity_lookups: int
    evidence_ids_returned: int
    artifact_ids_requested: int
    revision_ids_requested: int
    provenance_snapshot_calls: int
    returned_entities: int
    returned_traversal_assertions: int
    layers: tuple[NeighborhoodLayerWork, ...]


@dataclass(frozen=True, slots=True)
class NeighborhoodResult:
    identity: NeighborhoodReadIdentity
    requested_seed_entity_ids: tuple[str, ...]
    found_seed_entity_ids: tuple[str, ...]
    missing_seed_entity_ids: tuple[str, ...]
    requested_depth: Literal[1, 2]
    entity_depths: tuple[tuple[str, int], ...]
    entities: tuple[ParsedEntity, ...]
    traversal_assertions: tuple[ParsedAssertion, ...]
    evidence: tuple[ParsedEvidenceRef, ...]
    source_artifacts: tuple[EntityReadSourceArtifact, ...]
    source_revisions: tuple[EntityReadSourceRevision, ...]
    completeness: EntityReadCompleteness
    work: NeighborhoodWorkCounts
    result_digest: str


def _identity(context: KnowledgeReadContext) -> NeighborhoodReadIdentity:
    parsed = context.parsed
    return NeighborhoodReadIdentity(
        space_id=parsed.space_id,
        revision_id=parsed.revision_id,
        domain_contract_id=parsed.domain_contract_ref.domain_id,
        domain_contract_revision=parsed.domain_contract_ref.domain_revision,
        semantic_profile_id=parsed.semantic_profile_ref.profile_id,
        semantic_profile_revision=parsed.semantic_profile_ref.profile_revision,
    )


def _normalize_seeds(seed_entity_ids: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for seed in seed_entity_ids:
        if not isinstance(seed, str) or seed == "":
            raise NeighborhoodReadIntegrityError("seed entity IDs must be non-empty strings")
        if seed in seen:
            continue
        seen.add(seed)
        normalized.append(seed)
    if not normalized:
        raise NeighborhoodReadIntegrityError("at least one seed entity ID is required")
    if len(normalized) > MAX_NEIGHBORHOOD_SEED_COUNT:
        raise NeighborhoodReadIntegrityError(
            f"at most {MAX_NEIGHBORHOOD_SEED_COUNT} seed entity IDs are allowed"
        )
    return tuple(sorted(normalized))


def _normalize_depth(depth: object) -> Literal[1, 2]:
    if (
        isinstance(depth, bool)
        or not isinstance(depth, int)
        or depth not in ALLOWED_NEIGHBORHOOD_DEPTHS
    ):
        raise NeighborhoodReadIntegrityError("neighborhood depth must be exactly 1 or 2")
    return 1 if depth == 1 else 2


def _touching_assertion_ids(parsed: ParsedKnowledgeRevision, entity_id: str) -> tuple[str, ...]:
    return (
        *parsed.get_outgoing_entity_ref_assertion_ids(entity_id),
        *parsed.get_incoming_entity_ref_assertion_ids(entity_id),
    )


def _assertion_endpoints(assertion: ParsedAssertion) -> tuple[str, str]:
    if not isinstance(assertion.value, ParsedEntityRefValue):
        raise NeighborhoodReadIntegrityError(
            f"admitted traversal assertion is not an entity-ref: {assertion.assertion_id}"
        )
    return assertion.subject_entity_id, assertion.value.entity_id


def _compute_result_digest(
    *,
    identity: NeighborhoodReadIdentity,
    requested_seed_entity_ids: tuple[str, ...],
    found_seed_entity_ids: tuple[str, ...],
    missing_seed_entity_ids: tuple[str, ...],
    requested_depth: Literal[1, 2],
    entity_depths: tuple[tuple[str, int], ...],
    traversal_assertion_ids: tuple[str, ...],
    evidence: tuple[ParsedEvidenceRef, ...],
    source_artifacts: tuple[EntityReadSourceArtifact, ...],
    source_revisions: tuple[EntityReadSourceRevision, ...],
    completeness: EntityReadCompleteness,
) -> str:
    return canonical_sha256(
        {
            "space_id": identity.space_id,
            "revision_id": identity.revision_id,
            "domain_contract_id": identity.domain_contract_id,
            "domain_contract_revision": identity.domain_contract_revision,
            "semantic_profile_id": identity.semantic_profile_id,
            "semantic_profile_revision": identity.semantic_profile_revision,
            "requested_seed_entity_ids": list(_dedupe_sorted(requested_seed_entity_ids)),
            "found_seed_entity_ids": list(found_seed_entity_ids),
            "missing_seed_entity_ids": list(missing_seed_entity_ids),
            "requested_depth": requested_depth,
            "entity_depths": [[entity_id, depth] for entity_id, depth in entity_depths],
            "traversal_assertion_ids": list(traversal_assertion_ids),
            "evidence": [
                {
                    "evidence_ref_id": item.evidence_ref_id,
                    "source_artifact_id": item.source_artifact_id,
                    "source_revision_id": item.source_revision_id,
                    "evidence_role": item.evidence_role,
                    "locator": item.locator,
                    "uri": item.uri,
                    "source_locator": item.source_locator,
                    "line_ref": item.line_ref,
                    "source_span_ref_id": item.source_span_ref_id,
                }
                for item in evidence
            ],
            "source_artifacts": [
                {
                    "source_artifact_id": item.source_artifact_id,
                    "status": item.status,
                    "current_revision_id": item.current_revision_id,
                    "source_classification": item.source_classification,
                    "authority": item.authority,
                }
                for item in source_artifacts
            ],
            "source_revisions": [
                {
                    "source_revision_id": item.source_revision_id,
                    "source_artifact_id": item.source_artifact_id,
                    "content_sha256": item.content_sha256,
                }
                for item in source_revisions
            ],
            "completeness": {"status": completeness.status, "reason": completeness.reason},
        }
    )


class NeighborhoodReadService:
    """Admitted-edge BFS over revision-local entity-ref assertion indexes."""

    def get_neighborhood(
        self,
        context: KnowledgeReadContext,
        seed_entity_ids: Sequence[str],
        depth: Literal[1, 2] = 1,
    ) -> NeighborhoodResult:
        requested_depth = _normalize_depth(depth)
        requested_seeds = _normalize_seeds(seed_entity_ids)
        identity = _identity(context)
        parsed = context.parsed

        entities: dict[str, ParsedEntity] = {}
        entity_depth_map: dict[str, int] = {}
        found_seeds: list[str] = []
        missing_seeds: list[str] = []
        for seed in requested_seeds:
            entity = parsed.get_entity(seed)
            if entity is None:
                missing_seeds.append(seed)
                continue
            found_seeds.append(seed)
            entities[seed] = entity
            entity_depth_map[seed] = 0
        seed_entity_lookups = len(requested_seeds)
        found_seed_ids = tuple(sorted(found_seeds))
        missing_seed_ids = tuple(sorted(missing_seeds))

        evaluated_assertion_ids: set[str] = set()
        returned_assertions: dict[str, ParsedAssertion] = {}
        snapshots: list[KnowledgeProvenanceSnapshot] = []
        layers: list[NeighborhoodLayerWork] = []
        frontier_entities_expanded = 0
        touching_assertion_candidates = 0
        deduped_candidate_assertions = 0
        assertions_evaluated = 0
        policy_evaluations = 0
        endpoint_entity_lookups = 0
        requested_artifact_ids: set[str] = set()
        requested_revision_ids: set[str] = set()
        provenance_snapshot_calls = 0

        frontier = tuple(sorted(found_seeds))
        for layer in range(1, requested_depth + 1):
            if not frontier:
                break
            discovered: list[str] = []
            layer_touching = 0
            for entity_id in frontier:
                touching = _touching_assertion_ids(parsed, entity_id)
                layer_touching += len(touching)
                discovered.extend(touching)
            layer_expanded = len(frontier)
            frontier_entities_expanded += layer_expanded
            touching_assertion_candidates += layer_touching

            new_candidates = tuple(
                sorted({assertion_id for assertion_id in discovered} - evaluated_assertion_ids)
            )
            evaluated_assertion_ids.update(new_candidates)
            deduped_candidate_assertions += len(new_candidates)

            layer_evaluated = 0
            layer_policy = 0
            layer_endpoints = 0
            newly_discovered: list[str] = []
            if new_candidates:
                admission, provenance = context.evaluate_candidates(new_candidates)
                snapshots.append(provenance)
                layer_evaluated = admission.work.assertions_evaluated
                layer_policy = admission.work.policy_evaluations
                assertions_evaluated += layer_evaluated
                policy_evaluations += layer_policy
                requested_artifact_ids.update(provenance.requested_artifact_ids)
                requested_revision_ids.update(provenance.requested_revision_ids)
                provenance_snapshot_calls += admission.work.provenance_snapshot_calls
                for assertion_id in admission.admitted_assertion_ids:
                    assertion = parsed.get_assertion(assertion_id)
                    if assertion is None:
                        raise NeighborhoodReadIntegrityError(
                            f"admitted assertion missing from parsed revision: {assertion_id}"
                        )
                    returned_assertions[assertion_id] = assertion
                    subject_id, target_id = _assertion_endpoints(assertion)
                    for endpoint_id in (subject_id, target_id):
                        if endpoint_id in entity_depth_map:
                            continue
                        layer_endpoints += 1
                        endpoint = parsed.get_entity(endpoint_id)
                        if endpoint is None:
                            raise NeighborhoodReadIntegrityError(
                                f"admitted traversal assertion {assertion_id} has dangling "
                                f"endpoint {endpoint_id}"
                            )
                        entity_depth_map[endpoint_id] = layer
                        entities[endpoint_id] = endpoint
                        newly_discovered.append(endpoint_id)
            endpoint_entity_lookups += layer_endpoints
            layers.append(
                NeighborhoodLayerWork(
                    layer=layer,
                    frontier_entities_expanded=layer_expanded,
                    touching_assertion_candidates=layer_touching,
                    deduped_candidate_assertions=len(new_candidates),
                    assertions_evaluated=layer_evaluated,
                    policy_evaluations=layer_policy,
                    endpoint_entity_lookups=layer_endpoints,
                )
            )
            frontier = tuple(sorted(newly_discovered))

        admitted_ids = tuple(sorted(returned_assertions))
        assertions_tuple = tuple(returned_assertions[assertion_id] for assertion_id in admitted_ids)
        entity_ids = tuple(sorted(entities))
        entities_tuple = tuple(entities[entity_id] for entity_id in entity_ids)
        entity_depths = tuple((entity_id, entity_depth_map[entity_id]) for entity_id in entity_ids)
        evidence, artifacts, revisions = _support_for_admitted(
            context=context,
            admitted_ids=admitted_ids,
            provenance=snapshots,
            integrity_error=NeighborhoodReadIntegrityError,
        )
        completeness = EntityReadCompleteness(status="complete", reason=None)
        work = NeighborhoodWorkCounts(
            seed_entity_lookups=seed_entity_lookups,
            frontier_entities_expanded=frontier_entities_expanded,
            touching_assertion_candidates=touching_assertion_candidates,
            deduped_candidate_assertions=deduped_candidate_assertions,
            assertions_evaluated=assertions_evaluated,
            policy_evaluations=policy_evaluations,
            endpoint_entity_lookups=endpoint_entity_lookups,
            evidence_ids_returned=len(evidence),
            artifact_ids_requested=len(requested_artifact_ids),
            revision_ids_requested=len(requested_revision_ids),
            provenance_snapshot_calls=provenance_snapshot_calls,
            returned_entities=len(entities_tuple),
            returned_traversal_assertions=len(assertions_tuple),
            layers=tuple(layers),
        )
        digest = _compute_result_digest(
            identity=identity,
            requested_seed_entity_ids=requested_seeds,
            found_seed_entity_ids=found_seed_ids,
            missing_seed_entity_ids=missing_seed_ids,
            requested_depth=requested_depth,
            entity_depths=entity_depths,
            traversal_assertion_ids=admitted_ids,
            evidence=evidence,
            source_artifacts=artifacts,
            source_revisions=revisions,
            completeness=completeness,
        )
        return NeighborhoodResult(
            identity=identity,
            requested_seed_entity_ids=requested_seeds,
            found_seed_entity_ids=found_seed_ids,
            missing_seed_entity_ids=missing_seed_ids,
            requested_depth=requested_depth,
            entity_depths=entity_depths,
            entities=entities_tuple,
            traversal_assertions=assertions_tuple,
            evidence=evidence,
            source_artifacts=artifacts,
            source_revisions=revisions,
            completeness=completeness,
            work=work,
            result_digest=digest,
        )
