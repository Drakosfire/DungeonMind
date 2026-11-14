"""Structural characterization of vNext bounded neighborhood reads."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from typing import Any, Literal

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.neighborhood import NeighborhoodReadService
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    PublicVisibility,
    ScopeBinding,
    ScopeSelector,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    EntityRefValue,
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

HIGH_DEGREE = 30
NOISY_LITERALS = 2_000
DEPTH_BOUNDARY_EDGES = 2_000
SOURCE_ARTIFACT_COUNT = 250


def _domain_and_profile() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2]:
    domain_contract = DomainContractDescriptor(
        domain_id="bench.neighborhood",
        domain_revision="1",
        scope_axes=["bench:scope"],
        visibility_labels=["bench:audience"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    semantic_profile = SemanticProfileDescriptorV2(
        profile_id="bench.neighborhood.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:relates", allowed_value_kinds=["entity_ref"]),
            SemanticProfilePredicate(term="bench:title", allowed_value_kinds=["literal"]),
        ],
    )
    return domain_contract, semantic_profile


def _meta(evidence_id: str) -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="bench:scope", value="one")],
        visibility=PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="bench:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=[evidence_id],
        temporal_scope=TimelessTemporalScope(),
    )


def _edge(assertion_id: str, subject: str, target: str, evidence_id: str) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="bench:relates",
        value=EntityRefValue(entity_id=target),
        metadata=_meta(evidence_id),
    )


def _literal(assertion_id: str, subject: str, evidence_id: str) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="bench:title",
        value=LiteralValue(value={"n": assertion_id}),
        metadata=_meta(evidence_id),
    )


def _source_pair(index: int) -> tuple[str, str, SourceArtifactV3, SourceRevisionV2, EvidenceRefV3]:
    artifact_id = f"src:art-{index:04d}"
    revision_id = f"srcrev:{index:04d}"
    evidence_id = f"evidence:{index:04d}"
    artifact = SourceArtifactV3(
        source_artifact_id=artifact_id,
        source_classification="bench:doc",
        current_revision_id=revision_id,
        authority="primary",
        visibility=PublicVisibility(),
        status="active",
    )
    revision = SourceRevisionV2(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256=f"{index:064x}"[:64],
        body_storage="inline",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    evidence = EvidenceRefV3(
        evidence_ref_id=evidence_id,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )
    return artifact_id, evidence_id, artifact, revision, evidence


def _build_space(*, decoy_count: int) -> dict[str, Any]:
    domain_contract, semantic_profile = _domain_and_profile()
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))

    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    evidence: list[EvidenceRefV3] = []
    evidence_ids: dict[int, str] = {}
    for index in range(SOURCE_ARTIFACT_COUNT + 8):
        _artifact_id, evidence_id, artifact, revision, evidence_ref = _source_pair(index)
        artifacts[artifact.source_artifact_id] = artifact
        revisions[revision.source_revision_id] = revision
        evidence.append(evidence_ref)
        evidence_ids[index] = evidence_id

    local_evidence = evidence_ids[0]
    noisy_evidence = evidence_ids[1]
    boundary_evidence = evidence_ids[2]

    entities = [
        Entity(entity_id="ent:low"),
        Entity(entity_id="ent:low-n"),
        Entity(entity_id="ent:branch"),
        Entity(entity_id="ent:branch-a"),
        Entity(entity_id="ent:branch-b"),
        Entity(entity_id="ent:branch-c"),
        Entity(entity_id="ent:noisy-seed"),
        Entity(entity_id="ent:noisy"),
        Entity(entity_id="ent:noisy-leaf"),
        Entity(entity_id="ent:bound-seed"),
        Entity(entity_id="ent:bound-mid"),
        Entity(entity_id="ent:boundary"),
        Entity(entity_id="ent:hub"),
    ]
    assertions = [
        _edge("asrt:low", "ent:low", "ent:low-n", local_evidence),
        _edge("asrt:branch-a", "ent:branch", "ent:branch-a", local_evidence),
        _edge("asrt:branch-ab", "ent:branch-a", "ent:branch-b", local_evidence),
        _edge("asrt:branch-c", "ent:branch", "ent:branch-c", local_evidence),
        _edge("asrt:noisy-seed", "ent:noisy-seed", "ent:noisy", local_evidence),
        _edge("asrt:noisy-leaf", "ent:noisy", "ent:noisy-leaf", local_evidence),
        _edge("asrt:bound-seed", "ent:bound-seed", "ent:bound-mid", local_evidence),
        _edge("asrt:bound-mid", "ent:bound-mid", "ent:boundary", local_evidence),
    ]
    for index in range(HIGH_DEGREE):
        entities.append(Entity(entity_id=f"ent:hub-n-{index:02d}"))
        assertions.append(
            _edge(f"asrt:hub-{index:02d}", "ent:hub", f"ent:hub-n-{index:02d}", local_evidence)
        )
    for index in range(NOISY_LITERALS):
        assertions.append(_literal(f"asrt:noisy-lit-{index:04d}", "ent:noisy", noisy_evidence))
    for index in range(DEPTH_BOUNDARY_EDGES):
        entities.append(Entity(entity_id=f"ent:bound-n-{index:04d}"))
        assertions.append(
            _edge(
                f"asrt:bound-{index:04d}",
                "ent:boundary",
                f"ent:bound-n-{index:04d}",
                boundary_evidence,
            )
        )
    for index in range(decoy_count):
        source_index = 3 + (index % SOURCE_ARTIFACT_COUNT)
        entities.append(Entity(entity_id=f"ent:decoy-{index:05d}"))
        assertions.append(
            _literal(
                f"asrt:decoy-{index:05d}",
                f"ent:decoy-{index:05d}",
                evidence_ids[source_index],
            )
        )

    for i in range(decoy_count):
        edge = _edge(f"asrt:rules-{i:05d}", f"ent:decoy-{i:05d}",
                     f"ent:decoy-{(i+1)%decoy_count:05d}", evidence_ids[0])
        assertions.append(edge.model_copy(update={"metadata": edge.metadata.model_copy(
            update={"evidence_ref_ids": [evidence_ids[0], evidence_ids[1]]})}))

    revision = KnowledgeRevision(
        space_id="space:bench-neighborhood",
        revision_id=f"rev:bench-{decoy_count}",
        created_at=datetime(2026, 9, 16, tzinfo=UTC),
        operation_ids=["op:bench"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            descriptor_sha256=contract_digest,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            descriptor_sha256=profile_digest,
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    reader = InMemoryKnowledgeSourceReader(artifacts=artifacts, revisions=revisions)
    request = ProjectionRequest(
        space_id=revision.space_id,
        revision_id=revision.revision_id,
        scope_selector=ScopeSelector(
            include_unscoped=True,
            bindings=[ScopeBinding(axis="bench:scope", value="one")],
        ),
        audience_labels=["bench:audience"],
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )
    context = KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id),
        source_reader=reader,
    )
    workload_digest = canonical_sha256(
        {
            "ring_edges": decoy_count,
            "evidence_refs_per_ring_edge": 2,
            "entity_count": len(entities),
            "assertion_count": len(assertions),
            "high_degree": HIGH_DEGREE,
            "noisy_literals": NOISY_LITERALS,
            "depth_boundary_edges": DEPTH_BOUNDARY_EDGES,
        }
    )
    return {
        "context": context,
        "parsed_semantic_digest": parsed.semantic_digest,
        "workload_digest": workload_digest,
        "entity_count": len(entities),
        "assertion_count": len(assertions),
    }


def _percentiles(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    if not ordered:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    p50 = statistics.median(ordered)
    idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {"p50_ms": p50, "p95_ms": ordered[idx]}


def _time_neighborhood(
    *,
    context: KnowledgeReadContext,
    seed_entity_ids: list[str],
    depth: Literal[1, 2],
    iterations: int,
) -> dict[str, Any]:
    service = NeighborhoodReadService()
    samples: list[float] = []
    last = None
    for _ in range(iterations):
        read_context = KnowledgeReadContext(
            parsed=context.parsed,
            request=context.request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )
        start = time.perf_counter()
        last = service.get_neighborhood(read_context, seed_entity_ids, depth=depth)
        samples.append((time.perf_counter() - start) * 1000.0)
    assert last is not None
    timing = _percentiles(samples)
    return {
        **timing,
        "requested_seeds": list(seed_entity_ids),
        "requested_depth": depth,
        "found_seed_entity_ids": list(last.found_seed_entity_ids),
        "missing_seed_entity_ids": list(last.missing_seed_entity_ids),
        "returned_entity_count": last.work.returned_entities,
        "returned_traversal_assertion_count": last.work.returned_traversal_assertions,
        "seed_entity_lookups": last.work.seed_entity_lookups,
        "frontier_entities_expanded": last.work.frontier_entities_expanded,
        "touching_assertion_candidates": last.work.touching_assertion_candidates,
        "deduped_candidate_assertions": last.work.deduped_candidate_assertions,
        "assertions_evaluated": last.work.assertions_evaluated,
        "policy_evaluations": last.work.policy_evaluations,
        "endpoint_entity_lookups": last.work.endpoint_entity_lookups,
        "evidence_ids_returned": last.work.evidence_ids_returned,
        "artifact_ids_requested": last.work.artifact_ids_requested,
        "revision_ids_requested": last.work.revision_ids_requested,
        "provenance_snapshot_calls": last.work.provenance_snapshot_calls,
        "layers": [
            {
                "layer": item.layer,
                "frontier_entities_expanded": item.frontier_entities_expanded,
                "touching_assertion_candidates": item.touching_assertion_candidates,
                "deduped_candidate_assertions": item.deduped_candidate_assertions,
                "assertions_evaluated": item.assertions_evaluated,
            }
            for item in last.work.layers
        ],
        "result_digest": last.result_digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure native neighborhood reads on a synthetic evidence-backed ring."
    )
    parser.add_argument("--ring-edges", type=int, default=10000, choices=(100, 10000))
    parser.add_argument("--iterations", type=int, default=40)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    fixture = _build_space(decoy_count=args.ring_edges)
    rows = []
    for depth in (1, 2):
        row = _time_neighborhood(
            context=fixture["context"],
            seed_entity_ids=["ent:decoy-00000"],
            depth=depth,
            iterations=args.iterations,
        )
        assert row["returned_entity_count"] == 2 * depth + 1
        assert row["returned_traversal_assertion_count"] == 2 * depth
        assert row["evidence_ids_returned"] == 2
        assert row["assertions_evaluated"] == 2 * depth
        rows.append(row)
    report = {key: value for key, value in fixture.items() if key != "context"}
    report.update(iterations=args.iterations, ring_edges=args.ring_edges, rows=rows)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
