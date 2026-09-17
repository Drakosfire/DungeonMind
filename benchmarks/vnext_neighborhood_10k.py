"""Structural characterization of vNext bounded neighborhood reads."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
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

KNOWN_MERGE_BASE = "82a5c3e6889ad4e5648fef8f358423b5a576cb9b"
HIGH_DEGREE = 30
NOISY_LITERALS = 2_000
DEPTH_BOUNDARY_EDGES = 2_000
SOURCE_ARTIFACT_COUNT = 250


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _git_merge_base() -> str:
    try:
        return subprocess.check_output(
            ["git", "merge-base", "HEAD", "origin/main"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return KNOWN_MERGE_BASE


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
            "decoy_count": decoy_count,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="Docs/Benchmarks/vnext_neighborhood_10k_v1.json")
    parser.add_argument("--iterations", type=int, default=40)
    args = parser.parse_args()

    space_10k = _build_space(decoy_count=10_000)
    space_1k = _build_space(decoy_count=1_000)
    context_10k = space_10k["context"]
    context_1k = space_1k["context"]

    low_d1_10k = _time_neighborhood(
        context=context_10k,
        seed_entity_ids=["ent:low"],
        depth=1,
        iterations=args.iterations,
    )
    low_d1_1k = _time_neighborhood(
        context=context_1k,
        seed_entity_ids=["ent:low"],
        depth=1,
        iterations=max(20, args.iterations // 2),
    )
    branch_d2_10k = _time_neighborhood(
        context=context_10k,
        seed_entity_ids=["ent:branch"],
        depth=2,
        iterations=args.iterations,
    )
    branch_d2_1k = _time_neighborhood(
        context=context_1k,
        seed_entity_ids=["ent:branch"],
        depth=2,
        iterations=max(20, args.iterations // 2),
    )
    noisy_d2 = _time_neighborhood(
        context=context_10k,
        seed_entity_ids=["ent:noisy-seed"],
        depth=2,
        iterations=max(16, args.iterations // 2),
    )
    boundary_d2 = _time_neighborhood(
        context=context_10k,
        seed_entity_ids=["ent:bound-seed"],
        depth=2,
        iterations=max(16, args.iterations // 2),
    )
    high_d1 = _time_neighborhood(
        context=context_10k,
        seed_entity_ids=["ent:hub"],
        depth=1,
        iterations=args.iterations,
    )

    locality_ok = (
        low_d1_10k["assertions_evaluated"] == low_d1_1k["assertions_evaluated"]
        and low_d1_10k["deduped_candidate_assertions"] == low_d1_1k["deduped_candidate_assertions"]
        and low_d1_10k["artifact_ids_requested"] == low_d1_1k["artifact_ids_requested"]
        and branch_d2_10k["assertions_evaluated"] == branch_d2_1k["assertions_evaluated"]
        and branch_d2_10k["deduped_candidate_assertions"]
        == branch_d2_1k["deduped_candidate_assertions"]
        and branch_d2_10k["artifact_ids_requested"] == 1
        and branch_d2_10k["revision_ids_requested"] == 1
        and branch_d2_10k["provenance_snapshot_calls"] == 2
        and noisy_d2["assertions_evaluated"] < NOISY_LITERALS
        and all(
            layer["touching_assertion_candidates"] < DEPTH_BOUNDARY_EDGES
            for layer in boundary_d2["layers"]
        )
        and high_d1["assertions_evaluated"] == HIGH_DEGREE
    )

    artifact = {
        "schema_version": "vnext_neighborhood_10k_v1",
        "characterization_only": True,
        "exact_base": KNOWN_MERGE_BASE,
        "exact_head": _git_head(),
        "workloads": {
            "space_10k": {
                "decoy_count": 10_000,
                "entity_count": space_10k["entity_count"],
                "assertion_count": space_10k["assertion_count"],
                "workload_digest": space_10k["workload_digest"],
                "parsed_semantic_digest": space_10k["parsed_semantic_digest"],
            },
            "space_1k": {
                "decoy_count": 1_000,
                "entity_count": space_1k["entity_count"],
                "assertion_count": space_1k["assertion_count"],
                "workload_digest": space_1k["workload_digest"],
                "parsed_semantic_digest": space_1k["parsed_semantic_digest"],
            },
        },
        "runs": {
            "low_degree_depth_1_10k": low_d1_10k,
            "low_degree_depth_1_1k": low_d1_1k,
            "branching_depth_2_10k": branch_d2_10k,
            "branching_depth_2_1k": branch_d2_1k,
            "noisy_neighbor_depth_2_10k": noisy_d2,
            "depth_boundary_depth_2_10k": boundary_d2,
            "high_degree_depth_1_10k": high_d1,
        },
        "structural_gate": {
            "claim": (
                "fixed local neighborhood candidate/source work does not grow with unrelated "
                "space size; noisy-neighbor literals and depth-2 extra edges are not scanned; "
                "high-degree seed work scales with actual touching degree"
            ),
            "passes": locality_ok,
            "directional_target": "10k depth-1 neighborhood p95 < 50 ms",
            "observed_low_degree_depth_1_10k_p95_ms": low_d1_10k["p95_ms"],
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not locality_ok:
        raise SystemExit("structural gate failed: neighborhood work escaped the visited frontier")


if __name__ == "__main__":
    main()
