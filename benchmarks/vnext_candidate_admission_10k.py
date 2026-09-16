"""Structural characterization of vNext candidate-local admission work."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
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

ASSERTION_COUNT = 10_000
SOURCE_ARTIFACT_COUNT = 200
REVISIONS_PER_ARTIFACT = 2


def _synthetic_workload() -> tuple[
    KnowledgeRevision,
    list[Entity],
    list[Assertion],
    list[EvidenceRefV3],
    InMemoryKnowledgeSourceReader,
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    str,
]:
    domain_contract = DomainContractDescriptor(
        domain_id="bench.domain",
        domain_revision="1",
        scope_axes=["bench:scope"],
        visibility_labels=["bench:audience"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    semantic_profile = SemanticProfileDescriptorV2(
        profile_id="bench.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:relates", allowed_value_kinds=["entity_ref"])
        ],
    )
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))

    entities = [Entity(entity_id="ent:subject")]
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
            content_sha256="a" * 64,
            body_storage="inline",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        revisions[rev_b] = SourceRevisionV2(
            source_revision_id=rev_b,
            source_artifact_id=artifact_id,
            content_sha256="b" * 64,
            body_storage="inline",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

    assertions: list[Assertion] = []
    evidence: list[EvidenceRefV3] = []
    for index in range(ASSERTION_COUNT):
        artifact_index = index % SOURCE_ARTIFACT_COUNT
        artifact_id = f"src:art-{artifact_index:04d}"
        revision_id = (
            f"srcrev:{artifact_index:04d}-a" if index % 2 == 0 else f"srcrev:{artifact_index:04d}-b"
        )
        evidence_id = f"evidence:{index:05d}"
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_id,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
            )
        )
        assertions.append(
            Assertion(
                assertion_id=f"asrt:{index:05d}",
                subject_entity_id="ent:subject",
                predicate="bench:relates",
                value=EntityRefValue(entity_id="ent:subject"),
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

    revision = KnowledgeRevision(
        space_id="space:bench-10k",
        revision_id="rev:bench-10k",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
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
    reader = InMemoryKnowledgeSourceReader(artifacts=artifacts, revisions=revisions)
    workload_digest = canonical_sha256(
        {
            "space_id": revision.space_id,
            "revision_id": revision.revision_id,
            "assertion_ids": [item.assertion_id for item in assertions],
            "evidence": [
                {
                    "evidence_ref_id": item.evidence_ref_id,
                    "source_artifact_id": item.source_artifact_id,
                    "source_revision_id": item.source_revision_id,
                    "evidence_role": item.evidence_role,
                }
                for item in evidence
            ],
            "artifacts": {
                artifact_id: artifact.model_dump(mode="json")
                for artifact_id, artifact in sorted(artifacts.items())
            },
            "revisions": {
                revision_id: revision_row.model_dump(mode="json")
                for revision_id, revision_row in sorted(revisions.items())
            },
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
        workload_digest,
    )


def _request(*, candidate_axes: bool = True) -> ProjectionRequest:
    return ProjectionRequest(
        space_id="space:bench-10k",
        revision_id="rev:bench-10k",
        scope_selector=ScopeSelector(
            include_unscoped=False,
            bindings=[ScopeBinding(axis="bench:scope", value="one")] if candidate_axes else [],
        ),
        audience_labels=[],
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )


def _run_batch(context: KnowledgeReadContext, assertion_ids: list[str]) -> dict[str, float | int]:
    start = time.perf_counter()
    result = context.admit_candidates(assertion_ids)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return {
        "candidate_count": result.work.candidate_count,
        "assertions_evaluated": result.work.assertions_evaluated,
        "policy_evaluations": result.work.policy_evaluations,
        "evidence_ids_resolved": result.work.evidence_ids_resolved,
        "artifact_ids_requested": result.work.artifact_ids_requested,
        "revision_ids_requested": result.work.revision_ids_requested,
        "provenance_snapshot_calls": result.work.provenance_snapshot_calls,
        "admitted_count": len(result.admitted_assertion_ids),
        "elapsed_ms": elapsed_ms,
    }


def _git_head() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="Docs/Benchmarks/vnext_candidate_admission_10k_v1.json",
    )
    args = parser.parse_args()

    (
        revision,
        entities,
        assertions,
        evidence,
        reader,
        domain_contract,
        semantic_profile,
        workload_digest,
    ) = _synthetic_workload()
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    policy = AlwaysAdmitPolicy(policy_id="bench.always")
    context = KnowledgeReadContext(
        parsed=parsed,
        request=_request(),
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=policy,
        source_reader=reader,
    )

    single = _run_batch(context, ["asrt:00000"])
    batch_10 = _run_batch(
        KnowledgeReadContext(
            parsed=parsed,
            request=_request(),
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
            domain_policy=policy,
            source_reader=reader,
        ),
        [f"asrt:{index:05d}" for index in range(10)],
    )
    batch_100 = _run_batch(
        KnowledgeReadContext(
            parsed=parsed,
            request=_request(),
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
            domain_policy=policy,
            source_reader=reader,
        ),
        [f"asrt:{index:05d}" for index in range(100)],
    )

    artifact = {
        "schema_version": "vnext_candidate_admission_10k_v1",
        "characterization_only": True,
        "exact_base": _git_head(),
        "workload_digest": workload_digest,
        "parsed_semantic_digest": parsed.semantic_digest,
        "assertion_count": ASSERTION_COUNT,
        "runs": {
            "single_candidate": single,
            "batch_10": batch_10,
            "batch_100": batch_100,
        },
        "structural_gate": {
            "single_candidate_max_artifact_ids_requested": 1,
            "observed_single_candidate_artifact_ids_requested": single["artifact_ids_requested"],
            "passes": single["artifact_ids_requested"] <= 1,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not artifact["structural_gate"]["passes"]:
        raise SystemExit(
            "structural gate failed: single-candidate path requested too many artifacts"
        )


if __name__ == "__main__":
    main()
