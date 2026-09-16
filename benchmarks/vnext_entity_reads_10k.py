"""Structural characterization of vNext exact / complete entity reads."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.entity_reads import EntityReadService
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
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
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

KNOWN_MERGE_BASE = "8a68894e40a56a115b2f44ad5410bec28fc81d3e"
HIGH_DEGREE = 30
SOURCE_ARTIFACT_COUNT = 250
REVISIONS_PER_ARTIFACT = 2


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _git_merge_base() -> str:
    try:
        return subprocess.check_output(
            ["git", "merge-base", "HEAD", "origin/main"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return KNOWN_MERGE_BASE


def _domain_and_profile() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2, str, str]:
    domain_contract = DomainContractDescriptor(
        domain_id="bench.entity-reads",
        domain_revision="1",
        scope_axes=["bench:scope"],
        visibility_labels=["bench:audience"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    semantic_profile = SemanticProfileDescriptorV2(
        profile_id="bench.entity-reads.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:relates", allowed_value_kinds=["entity_ref"])
        ],
    )
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))
    return domain_contract, semantic_profile, contract_digest, profile_digest


def _build_workload(
    *,
    assertion_count: int,
    high_degree: int,
) -> tuple[
    KnowledgeRevision,
    list[Entity],
    list[Assertion],
    list[EvidenceRefV3],
    InMemoryKnowledgeSourceReader,
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    str,
]:
    domain_contract, semantic_profile, contract_digest, profile_digest = _domain_and_profile()

    entities: list[Entity] = [
        Entity(entity_id="ent:selected-low"),
        Entity(entity_id="ent:high-hub"),
    ]
    for index in range(high_degree):
        entities.append(Entity(entity_id=f"ent:high-target-{index:02d}"))
    decoy_entity_count = max(1, (assertion_count - high_degree - 2) // 3)
    for index in range(decoy_entity_count):
        entities.append(Entity(entity_id=f"ent:decoy-{index:05d}"))

    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    for index in range(SOURCE_ARTIFACT_COUNT):
        artifact_id = f"src:art-{index:04d}"
        rev_a = f"srcrev:{index:04d}-a"
        rev_b = f"srcrev:{index:04d}-b"
        artifacts[artifact_id] = SourceArtifactV3(
            source_artifact_id=artifact_id,
            source_classification="bench:doc",
            current_revision_id=rev_b,
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
        revisions[rev_a] = SourceRevisionV2(
            source_revision_id=rev_a,
            source_artifact_id=artifact_id,
            content_sha256=f"{index:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        revisions[rev_b] = SourceRevisionV2(
            source_revision_id=rev_b,
            source_artifact_id=artifact_id,
            content_sha256=f"{index + 1:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

    assertions: list[Assertion] = []
    evidence: list[EvidenceRefV3] = []

    def _append_assertion(
        *,
        assertion_id: str,
        subject: str,
        target: str,
        evidence_id: str,
        artifact_index: int,
    ) -> None:
        artifact_id = f"src:art-{artifact_index % SOURCE_ARTIFACT_COUNT:04d}"
        revision_id = (
            f"srcrev:{artifact_index % SOURCE_ARTIFACT_COUNT:04d}-a"
            if artifact_index % 2 == 0
            else f"srcrev:{artifact_index % SOURCE_ARTIFACT_COUNT:04d}-b"
        )
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_id,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
                locator=f"loc:{evidence_id}",
            )
        )
        assertions.append(
            Assertion(
                assertion_id=assertion_id,
                subject_entity_id=subject,
                predicate="bench:relates",
                value=EntityRefValue(entity_id=target),
                metadata=AssertionMetadata(
                    scope=[ScopeBinding(axis="bench:scope", value="one")],
                    visibility=PublicVisibility(),
                    epistemic_basis="asserted",
                    claim_mode="bench:fact",
                    standing=KnowledgeStanding.ESTABLISHED,
                    evidence_ref_ids=[evidence_id],
                    temporal_scope=TimelessTemporalScope(),
                ),
            )
        )

    _append_assertion(
        assertion_id="asrt:selected-low",
        subject="ent:selected-low",
        target="ent:selected-low",
        evidence_id="evidence:selected-low",
        artifact_index=0,
    )
    for index in range(high_degree):
        _append_assertion(
            assertion_id=f"asrt:high-{index:02d}",
            subject="ent:high-hub",
            target=f"ent:high-target-{index:02d}",
            evidence_id=f"evidence:high-{index:02d}",
            artifact_index=index + 1,
        )

    remaining = assertion_count - len(assertions)
    for offset in range(remaining):
        decoy_entity = f"ent:decoy-{offset % decoy_entity_count:05d}"
        _append_assertion(
            assertion_id=f"asrt:decoy-{offset:05d}",
            subject=decoy_entity,
            target=decoy_entity,
            evidence_id=f"evidence:decoy-{offset:05d}",
            artifact_index=(offset + high_degree + 3) % SOURCE_ARTIFACT_COUNT,
        )

    revision = KnowledgeRevision(
        space_id=f"space:bench-entity-reads-{assertion_count}",
        revision_id=f"rev:bench-entity-reads-{assertion_count}",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:bench-entity-reads"],
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
    reader = InMemoryKnowledgeSourceReader(artifacts=artifacts, revisions=revisions)
    workload_digest = canonical_sha256(
        {
            "space_id": revision.space_id,
            "revision_id": revision.revision_id,
            "assertion_ids": [item.assertion_id for item in assertions],
            "entity_ids": [item.entity_id for item in entities],
            "evidence": [
                {
                    "evidence_ref_id": item.evidence_ref_id,
                    "source_artifact_id": item.source_artifact_id,
                    "source_revision_id": item.source_revision_id,
                    "locator": item.locator,
                }
                for item in evidence
            ],
        }
    )
    return (
        revision,
        entities,
        assertions,
        evidence,
        reader,
        domain_contract,
        semantic_profile,
        contract_digest,
        profile_digest,
        workload_digest,
    )


def _build_incoming_heavy_workload(
    *,
    neighbor_subject_count: int,
) -> tuple[
    KnowledgeRevision,
    list[Entity],
    list[Assertion],
    list[EvidenceRefV3],
    InMemoryKnowledgeSourceReader,
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    str,
    str,
    str,
]:
    domain_contract, semantic_profile, contract_digest, profile_digest = _domain_and_profile()
    entities = [
        Entity(entity_id="ent:incoming-selected"),
        Entity(entity_id="ent:noisy-neighbor"),
    ]
    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    for index in range(SOURCE_ARTIFACT_COUNT):
        artifact_id = f"src:art-{index:04d}"
        rev_a = f"srcrev:{index:04d}-a"
        rev_b = f"srcrev:{index:04d}-b"
        artifacts[artifact_id] = SourceArtifactV3(
            source_artifact_id=artifact_id,
            source_classification="bench:doc",
            current_revision_id=rev_b,
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
        revisions[rev_a] = SourceRevisionV2(
            source_revision_id=rev_a,
            source_artifact_id=artifact_id,
            content_sha256=f"{index:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        revisions[rev_b] = SourceRevisionV2(
            source_revision_id=rev_b,
            source_artifact_id=artifact_id,
            content_sha256=f"{index + 1:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

    assertions: list[Assertion] = []
    evidence: list[EvidenceRefV3] = []

    def _append_assertion(
        *,
        assertion_id: str,
        subject: str,
        target: str,
        evidence_id: str,
        artifact_index: int,
    ) -> None:
        artifact_id = f"src:art-{artifact_index % SOURCE_ARTIFACT_COUNT:04d}"
        revision_id = (
            f"srcrev:{artifact_index % SOURCE_ARTIFACT_COUNT:04d}-a"
            if artifact_index % 2 == 0
            else f"srcrev:{artifact_index % SOURCE_ARTIFACT_COUNT:04d}-b"
        )
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_id,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
                locator=f"loc:{evidence_id}",
            )
        )
        assertions.append(
            Assertion(
                assertion_id=assertion_id,
                subject_entity_id=subject,
                predicate="bench:relates",
                value=EntityRefValue(entity_id=target),
                metadata=AssertionMetadata(
                    scope=[ScopeBinding(axis="bench:scope", value="one")],
                    visibility=PublicVisibility(),
                    epistemic_basis="asserted",
                    claim_mode="bench:fact",
                    standing=KnowledgeStanding.ESTABLISHED,
                    evidence_ref_ids=[evidence_id],
                    temporal_scope=TimelessTemporalScope(),
                ),
            )
        )

    for index in range(neighbor_subject_count):
        _append_assertion(
            assertion_id=f"asrt:neighbor-noise-{index:05d}",
            subject="ent:noisy-neighbor",
            target="ent:noisy-neighbor",
            evidence_id=f"evidence:neighbor-noise-{index:05d}",
            artifact_index=index,
        )
    _append_assertion(
        assertion_id="asrt:neighbor-points-at-selected",
        subject="ent:noisy-neighbor",
        target="ent:incoming-selected",
        evidence_id="evidence:neighbor-points-at-selected",
        artifact_index=neighbor_subject_count,
    )

    revision = KnowledgeRevision(
        space_id=f"space:bench-incoming-heavy-{neighbor_subject_count}",
        revision_id=f"rev:bench-incoming-heavy-{neighbor_subject_count}",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:bench-incoming-heavy"],
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
    reader = InMemoryKnowledgeSourceReader(artifacts=artifacts, revisions=revisions)
    workload_digest = canonical_sha256(
        {
            "space_id": revision.space_id,
            "revision_id": revision.revision_id,
            "assertion_ids": [item.assertion_id for item in assertions],
            "entity_ids": [item.entity_id for item in entities],
            "evidence": [
                {
                    "evidence_ref_id": item.evidence_ref_id,
                    "source_artifact_id": item.source_artifact_id,
                    "source_revision_id": item.source_revision_id,
                    "locator": item.locator,
                }
                for item in evidence
            ],
        }
    )
    return (
        revision,
        entities,
        assertions,
        evidence,
        reader,
        domain_contract,
        semantic_profile,
        contract_digest,
        profile_digest,
        workload_digest,
    )


def _request(*, space_id: str, revision_id: str) -> ProjectionRequest:
    return ProjectionRequest(
        space_id=space_id,
        revision_id=revision_id,
        scope_selector=ScopeSelector(
            include_unscoped=False,
            bindings=[ScopeBinding(axis="bench:scope", value="one")],
        ),
        audience_labels=[],
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )


def _context_from_workload(
    workload: tuple[Any, ...],
) -> tuple[KnowledgeReadContext, str]:
    (
        revision,
        entities,
        assertions,
        evidence,
        reader,
        domain_contract,
        semantic_profile,
        _contract_digest,
        _profile_digest,
        _workload_digest,
    ) = workload
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    context = KnowledgeReadContext(
        parsed=parsed,
        request=_request(space_id=revision.space_id, revision_id=revision.revision_id),
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id="bench.always"),
        source_reader=reader,
    )
    return context, parsed.semantic_digest


def _percentiles(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    if not ordered:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    p50 = statistics.median(ordered)
    idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {"p50_ms": p50, "p95_ms": ordered[idx]}


def _time_entity_read(
    *,
    context: KnowledgeReadContext,
    entity_id: str,
    complete: bool,
    iterations: int,
) -> dict[str, Any]:
    service = EntityReadService()
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
        if complete:
            last = service.get_complete_entity(read_context, entity_id)
        else:
            last = service.get_entity(read_context, entity_id)
        samples.append((time.perf_counter() - start) * 1000.0)
    assert last is not None
    timing = _percentiles(samples)
    return {
        **timing,
        "entity_id": entity_id,
        "found": last.found,
        "returned_assertion_count": len(last.assertions),
        "returned_related_endpoint_count": len(getattr(last, "related_entities", ())),
        "returned_evidence_count": len(last.evidence),
        "candidate_assertion_count": last.work.deduped_candidate_assertions,
        "subject_assertion_candidates": last.work.subject_assertion_candidates,
        "incoming_entity_ref_candidates": last.work.incoming_entity_ref_candidates,
        "outgoing_entity_ref_candidates": last.work.outgoing_entity_ref_candidates,
        "assertions_evaluated": last.work.assertions_evaluated,
        "policy_evaluations": last.work.policy_evaluations,
        "evidence_ids_returned": last.work.evidence_ids_returned,
        "artifact_ids_requested": last.work.artifact_ids_requested,
        "revision_ids_requested": last.work.revision_ids_requested,
        "provenance_snapshot_calls": last.work.provenance_snapshot_calls,
        "endpoint_entity_lookups": last.work.endpoint_entity_lookups,
        "result_digest": last.result_digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="Docs/Benchmarks/vnext_entity_reads_10k_v1.json",
    )
    parser.add_argument("--iterations", type=int, default=60)
    args = parser.parse_args()

    workload_10k = _build_workload(assertion_count=10_000, high_degree=HIGH_DEGREE)
    workload_1k = _build_workload(assertion_count=1_000, high_degree=HIGH_DEGREE)
    incoming_10k = _build_incoming_heavy_workload(neighbor_subject_count=10_000)
    incoming_1k = _build_incoming_heavy_workload(neighbor_subject_count=1_000)
    context_10k, parsed_digest_10k = _context_from_workload(workload_10k)
    context_1k, parsed_digest_1k = _context_from_workload(workload_1k)
    context_incoming_10k, parsed_digest_incoming_10k = _context_from_workload(incoming_10k)
    context_incoming_1k, parsed_digest_incoming_1k = _context_from_workload(incoming_1k)

    low_exact_10k = _time_entity_read(
        context=context_10k,
        entity_id="ent:selected-low",
        complete=False,
        iterations=args.iterations,
    )
    low_complete_10k = _time_entity_read(
        context=context_10k,
        entity_id="ent:selected-low",
        complete=True,
        iterations=args.iterations,
    )
    high_complete_10k = _time_entity_read(
        context=context_10k,
        entity_id="ent:high-hub",
        complete=True,
        iterations=args.iterations,
    )
    low_exact_1k = _time_entity_read(
        context=context_1k,
        entity_id="ent:selected-low",
        complete=False,
        iterations=max(20, args.iterations // 2),
    )
    incoming_complete_10k = _time_entity_read(
        context=context_incoming_10k,
        entity_id="ent:incoming-selected",
        complete=True,
        iterations=args.iterations,
    )
    incoming_complete_1k = _time_entity_read(
        context=context_incoming_1k,
        entity_id="ent:incoming-selected",
        complete=True,
        iterations=max(20, args.iterations // 2),
    )

    structural_gate_passes = (
        low_exact_10k["artifact_ids_requested"] == low_exact_1k["artifact_ids_requested"]
        and low_exact_10k["assertions_evaluated"] == low_exact_1k["assertions_evaluated"]
        and low_exact_10k["candidate_assertion_count"] == low_exact_1k["candidate_assertion_count"]
        and incoming_complete_10k["assertions_evaluated"]
        == incoming_complete_1k["assertions_evaluated"]
        and incoming_complete_10k["candidate_assertion_count"]
        == incoming_complete_1k["candidate_assertion_count"]
        and incoming_complete_10k["incoming_entity_ref_candidates"] == 1
        and incoming_complete_1k["incoming_entity_ref_candidates"] == 1
    )

    artifact = {
        "schema_version": "vnext_entity_reads_10k_v1",
        "characterization_only": True,
        "exact_base": _git_merge_base(),
        "exact_head": _git_head(),
        "workloads": {
            "space_10k": {
                "assertion_count": 10_000,
                "workload_digest": workload_10k[-1],
                "parsed_semantic_digest": parsed_digest_10k,
            },
            "space_1k": {
                "assertion_count": 1_000,
                "workload_digest": workload_1k[-1],
                "parsed_semantic_digest": parsed_digest_1k,
            },
            "incoming_heavy_10k": {
                "neighbor_subject_count": 10_000,
                "workload_digest": incoming_10k[-1],
                "parsed_semantic_digest": parsed_digest_incoming_10k,
            },
            "incoming_heavy_1k": {
                "neighbor_subject_count": 1_000,
                "workload_digest": incoming_1k[-1],
                "parsed_semantic_digest": parsed_digest_incoming_1k,
            },
        },
        "runs": {
            "get_entity_low_degree_10k": low_exact_10k,
            "get_complete_entity_low_degree_10k": low_complete_10k,
            "get_complete_entity_high_degree_10k": high_complete_10k,
            "get_entity_low_degree_1k": low_exact_1k,
            "get_complete_entity_incoming_heavy_10k": incoming_complete_10k,
            "get_complete_entity_incoming_heavy_1k": incoming_complete_1k,
        },
        "structural_gate": {
            "claim": (
                "low-degree get_entity source work does not grow with unrelated revision size; "
                "incoming-heavy get_complete_entity work stays proportional to touching assertions"
            ),
            "observed_10k_artifact_ids_requested": low_exact_10k["artifact_ids_requested"],
            "observed_1k_artifact_ids_requested": low_exact_1k["artifact_ids_requested"],
            "observed_10k_assertions_evaluated": low_exact_10k["assertions_evaluated"],
            "observed_1k_assertions_evaluated": low_exact_1k["assertions_evaluated"],
            "observed_incoming_heavy_10k_assertions_evaluated": incoming_complete_10k[
                "assertions_evaluated"
            ],
            "observed_incoming_heavy_1k_assertions_evaluated": incoming_complete_1k[
                "assertions_evaluated"
            ],
            "observed_incoming_heavy_10k_incoming_candidates": incoming_complete_10k[
                "incoming_entity_ref_candidates"
            ],
            "passes": structural_gate_passes,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not structural_gate_passes:
        raise SystemExit(
            "structural gate failed: entity read scaled with unrelated neighbor/space size"
        )


if __name__ == "__main__":
    main()
