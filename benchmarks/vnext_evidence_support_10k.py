"""Structural characterization of vNext exact evidence support and source anchors."""

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
from dungeonmind.application.vnext.evidence_reads import EvidenceReadService, EvidenceReadTrace
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.source_anchors import decode_anchor_token
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
    PublicVisibility,
    ScopeBinding,
    ScopeSelector,
    TimelessTemporalScope,
    VisibilityRequirement,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

KNOWN_MERGE_BASE = "7f5df9eace6f1ab23a0d817e0b350c379923641f"
UNUSED_SOURCE_COUNT = 2_000
HUB_DEGREES = (4, 64, 256)
TARGET_ASSERTION_ID = "asrt:target"
TARGET_EVIDENCE_ID = "evidence:target"
HIDDEN_EVIDENCE_ID = "evidence:hidden"
MIXED_EVIDENCE_ID = "evidence:mixed"


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _domain_and_profile() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2]:
    domain_contract = DomainContractDescriptor(
        domain_id="bench.evidence",
        domain_revision="1",
        scope_axes=["bench:scope"],
        visibility_labels=["bench:audience", "bench:hidden"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    semantic_profile = SemanticProfileDescriptorV2(
        profile_id="bench.evidence.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:title", allowed_value_kinds=["literal"]),
        ],
    )
    return domain_contract, semantic_profile


def _meta(
    evidence_id: str, *, visibility: VisibilityRequirement | None = None
) -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="bench:scope", value="one")],
        visibility=visibility if visibility is not None else PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="bench:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=[evidence_id],
        temporal_scope=TimelessTemporalScope(),
    )


def _literal(
    assertion_id: str,
    subject: str,
    evidence_id: str,
    *,
    visibility: VisibilityRequirement | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="bench:title",
        value=LiteralValue(value={"n": assertion_id}),
        metadata=_meta(evidence_id, visibility=visibility),
    )


def _source_bundle(
    index: int, *, prefix: str
) -> tuple[str, SourceArtifactV3, SourceRevisionV2, EvidenceRefV3]:
    artifact_id = f"src:{prefix}-{index:05d}"
    revision_id = f"srcrev:{prefix}-{index:05d}"
    evidence_id = f"evidence:{prefix}-{index:05d}"
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
        locator=f"loc:{prefix}-{index:05d}",
        uri=f"uri:{prefix}-{index:05d}",
    )
    return evidence_id, artifact, revision, evidence


def _named_source(
    *, evidence_id: str, artifact_id: str, revision_id: str
) -> tuple[SourceArtifactV3, SourceRevisionV2, EvidenceRefV3]:
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
        content_sha256=canonical_sha256({"id": revision_id}),
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
        locator=f"loc:{evidence_id}",
        uri=f"uri:{evidence_id}",
    )
    return artifact, revision, evidence


def _build_space(*, decoy_count: int, unused_sources: int) -> dict[str, Any]:
    domain_contract, semantic_profile = _domain_and_profile()
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))

    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    evidence: list[EvidenceRefV3] = []
    entities = [
        Entity(entity_id="ent:target"),
        Entity(entity_id="ent:target-b"),
        Entity(entity_id="ent:hidden"),
        Entity(entity_id="ent:mixed-visible"),
        Entity(entity_id="ent:mixed-hidden"),
    ]
    assertions = [
        _literal(TARGET_ASSERTION_ID, "ent:target", TARGET_EVIDENCE_ID),
        _literal("asrt:target-b", "ent:target-b", TARGET_EVIDENCE_ID),
        _literal(
            "asrt:hidden-only",
            "ent:hidden",
            HIDDEN_EVIDENCE_ID,
            visibility=LabelsAllVisibility(labels=["bench:hidden"]),
        ),
        _literal("asrt:mixed-visible", "ent:mixed-visible", MIXED_EVIDENCE_ID),
        _literal(
            "asrt:mixed-hidden",
            "ent:mixed-hidden",
            MIXED_EVIDENCE_ID,
            visibility=LabelsAllVisibility(labels=["bench:hidden"]),
        ),
    ]
    for evidence_id, artifact_id, revision_id in (
        (TARGET_EVIDENCE_ID, "src:target", "srcrev:target"),
        (HIDDEN_EVIDENCE_ID, "src:hidden", "srcrev:hidden"),
        (MIXED_EVIDENCE_ID, "src:mixed", "srcrev:mixed"),
    ):
        artifact, revision, evidence_ref = _named_source(
            evidence_id=evidence_id,
            artifact_id=artifact_id,
            revision_id=revision_id,
        )
        artifacts[artifact_id] = artifact
        revisions[revision_id] = revision
        evidence.append(evidence_ref)

    for degree in HUB_DEGREES:
        evidence_id = f"evidence:hub-{degree}"
        artifact, revision, evidence_ref = _named_source(
            evidence_id=evidence_id,
            artifact_id=f"src:hub-{degree}",
            revision_id=f"srcrev:hub-{degree}",
        )
        artifacts[artifact.source_artifact_id] = artifact
        revisions[revision.source_revision_id] = revision
        evidence.append(evidence_ref)
        for index in range(degree):
            entity_id = f"ent:hub-{degree}-{index:03d}"
            entities.append(Entity(entity_id=entity_id))
            assertions.append(_literal(f"asrt:hub-{degree}-{index:03d}", entity_id, evidence_id))

    for index in range(decoy_count):
        evidence_id, artifact, revision, evidence_ref = _source_bundle(index, prefix="decoy")
        artifacts[artifact.source_artifact_id] = artifact
        revisions[revision.source_revision_id] = revision
        evidence.append(evidence_ref)
        entity_id = f"ent:decoy-{index:05d}"
        entities.append(Entity(entity_id=entity_id))
        assertions.append(_literal(f"asrt:decoy-{index:05d}", entity_id, evidence_id))

    for index in range(unused_sources):
        _evidence_id, artifact, revision, evidence_ref = _source_bundle(index, prefix="unused")
        artifacts[artifact.source_artifact_id] = artifact
        revisions[revision.source_revision_id] = revision
        evidence.append(evidence_ref)

    revision = KnowledgeRevision(
        space_id="space:bench-evidence",
        revision_id=f"rev:bench-{decoy_count}-{unused_sources}",
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
            "unused_sources": unused_sources,
            "entity_count": len(entities),
            "assertion_count": len(assertions),
            "evidence_count": len(evidence),
            "artifact_count": len(artifacts),
            "hub_degrees": list(HUB_DEGREES),
        }
    )
    return {
        "context": context,
        "parsed_semantic_digest": parsed.semantic_digest,
        "workload_digest": workload_digest,
        "entity_count": len(entities),
        "assertion_count": len(assertions),
        "evidence_count": len(evidence),
        "artifact_count": len(artifacts),
    }


def _percentiles(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    if not ordered:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    p50 = statistics.median(ordered)
    idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {"p50_ms": p50, "p95_ms": ordered[idx]}


def _fresh(context: KnowledgeReadContext) -> KnowledgeReadContext:
    return KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )


def _trace_payload(trace: EvidenceReadTrace) -> dict[str, int]:
    return {
        "assertion_lookups": trace.assertion_lookups,
        "evidence_lookups": trace.evidence_lookups,
        "supporter_candidates": trace.supporter_candidates,
        "assertions_evaluated": trace.assertions_evaluated,
        "policy_evaluations": trace.policy_evaluations,
        "evidence_ids_consulted": trace.evidence_ids_consulted,
        "unique_artifact_ids_requested": trace.unique_artifact_ids_requested,
        "unique_revision_ids_requested": trace.unique_revision_ids_requested,
        "provenance_snapshot_calls": trace.provenance_snapshot_calls,
        "anchors_constructed": trace.anchors_constructed,
        "anchors_revalidated": trace.anchors_revalidated,
    }


def _time_operation(
    *,
    context: KnowledgeReadContext,
    kind: Literal["assertion", "evidence", "resolve", "create_then_resolve"],
    target: str,
    iterations: int,
) -> dict[str, Any]:
    service = EvidenceReadService()
    samples: list[float] = []
    last_available = False
    last_resolved: bool | None = None
    last_digest = ""
    last_anchor_id = ""
    last_evidence_count = 0
    last_supporter_count = 0
    recovered_evidence_id = ""
    for _ in range(iterations):
        read_context = _fresh(context)
        start = time.perf_counter()
        if kind == "assertion":
            result = service.get_assertion_evidence(read_context, target)
            last_available = result.available
            last_digest = result.result_digest
            last_evidence_count = len(result.evidence)
            last_supporter_count = 1 if result.assertion is not None else 0
            last_anchor_id = result.anchors[0].anchor_id if result.anchors else ""
            last_resolved = None
        elif kind == "evidence":
            result = service.get_evidence(read_context, target)
            last_available = result.available
            last_digest = result.result_digest
            last_evidence_count = 1 if result.evidence is not None else 0
            last_supporter_count = len(result.admitted_supporter_assertions)
            last_anchor_id = result.anchors[0].anchor_id if result.anchors else ""
            last_resolved = None
        elif kind == "resolve":
            resolved = service.resolve_source_anchor(read_context, target)
            last_available = resolved.resolved
            last_resolved = resolved.resolved
            last_digest = resolved.result_digest
            last_evidence_count = 1 if resolved.evidence is not None else 0
            last_supporter_count = len(resolved.admitted_supporter_assertions)
            last_anchor_id = resolved.anchor.anchor_id if resolved.anchor is not None else ""
        else:
            created = service.get_evidence(read_context, target)
            resolved = service.resolve_source_anchor(read_context, created.anchors[0].anchor_id)
            last_available = created.available and resolved.resolved
            last_resolved = resolved.resolved
            last_digest = resolved.result_digest
            last_evidence_count = 1 if resolved.evidence is not None else 0
            last_supporter_count = len(resolved.admitted_supporter_assertions)
            last_anchor_id = resolved.anchor.anchor_id if resolved.anchor is not None else ""
        samples.append((time.perf_counter() - start) * 1000.0)
    decoded = decode_anchor_token(last_anchor_id) if last_anchor_id else None
    if decoded is not None:
        recovered_evidence_id = decoded[0]
    timing = _percentiles(samples)
    return {
        **timing,
        **_trace_payload(service.last_trace),
        "available": last_available,
        "resolved": last_resolved,
        "result_digest": last_digest,
        "anchor_id": last_anchor_id,
        "returned_evidence_count": last_evidence_count,
        "returned_admitted_supporters": last_supporter_count,
        "recovered_evidence_ref_id": recovered_evidence_id,
        "public_exposes_supporter_candidates": False,
    }


def _structural_equal(left: dict[str, Any], right: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(left[key] == right[key] for key in keys)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="Docs/Benchmarks/vnext_evidence_support_10k_v1.json")
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument(
        "--exact-head",
        default="",
        help="Pin the substantive implementation HEAD rather than this process HEAD.",
    )
    args = parser.parse_args()

    space_10k = _build_space(decoy_count=10_000, unused_sources=UNUSED_SOURCE_COUNT)
    space_1k = _build_space(decoy_count=1_000, unused_sources=0)
    context_10k = space_10k["context"]
    context_1k = space_1k["context"]
    half = max(20, args.iterations // 2)

    assertion_10k = _time_operation(
        context=context_10k,
        kind="assertion",
        target=TARGET_ASSERTION_ID,
        iterations=args.iterations,
    )
    assertion_1k = _time_operation(
        context=context_1k,
        kind="assertion",
        target=TARGET_ASSERTION_ID,
        iterations=half,
    )
    evidence_10k = _time_operation(
        context=context_10k,
        kind="evidence",
        target=TARGET_EVIDENCE_ID,
        iterations=args.iterations,
    )
    evidence_1k = _time_operation(
        context=context_1k,
        kind="evidence",
        target=TARGET_EVIDENCE_ID,
        iterations=half,
    )
    high_support = {
        degree: _time_operation(
            context=context_10k,
            kind="evidence",
            target=f"evidence:hub-{degree}",
            iterations=max(12, args.iterations // 2),
        )
        for degree in HUB_DEGREES
    }
    created = EvidenceReadService().get_evidence(_fresh(context_10k), TARGET_EVIDENCE_ID)
    created_1k = EvidenceReadService().get_evidence(_fresh(context_1k), TARGET_EVIDENCE_ID)
    anchor_10k = _time_operation(
        context=context_10k,
        kind="resolve",
        target=created.anchors[0].anchor_id,
        iterations=args.iterations,
    )
    anchor_1k = _time_operation(
        context=context_1k,
        kind="resolve",
        target=created_1k.anchors[0].anchor_id,
        iterations=half,
    )
    privacy_visible = _time_operation(
        context=context_10k,
        kind="evidence",
        target=TARGET_EVIDENCE_ID,
        iterations=max(12, args.iterations // 3),
    )
    privacy_hidden = _time_operation(
        context=context_10k,
        kind="evidence",
        target=HIDDEN_EVIDENCE_ID,
        iterations=max(12, args.iterations // 3),
    )
    privacy_mixed = _time_operation(
        context=context_10k,
        kind="evidence",
        target=MIXED_EVIDENCE_ID,
        iterations=max(12, args.iterations // 3),
    )

    locality_keys = (
        "assertion_lookups",
        "evidence_lookups",
        "supporter_candidates",
        "assertions_evaluated",
        "unique_artifact_ids_requested",
        "unique_revision_ids_requested",
        "provenance_snapshot_calls",
        "returned_evidence_count",
        "returned_admitted_supporters",
    )
    locality_ok = (
        _structural_equal(assertion_10k, assertion_1k, locality_keys)
        and _structural_equal(evidence_10k, evidence_1k, locality_keys)
        and _structural_equal(anchor_10k, anchor_1k, locality_keys)
        and assertion_10k["returned_evidence_count"] == 1
        and evidence_10k["supporter_candidates"] == 2
        and evidence_10k["returned_admitted_supporters"] == 2
        and all(
            high_support[degree]["supporter_candidates"] == degree
            and high_support[degree]["returned_admitted_supporters"] == degree
            for degree in HUB_DEGREES
        )
        and privacy_hidden["available"] is False
        and privacy_hidden["returned_evidence_count"] == 0
        and privacy_hidden["anchor_id"] == ""
        and privacy_hidden["supporter_candidates"] == 1
        and privacy_mixed["available"] is True
        and privacy_mixed["returned_admitted_supporters"] == 1
        and privacy_mixed["supporter_candidates"] == 2
        and privacy_visible["available"] is True
    )
    recovered_anchor = decode_anchor_token(str(anchor_10k["anchor_id"]))
    if recovered_anchor is None or recovered_anchor[0] != TARGET_EVIDENCE_ID:
        locality_ok = False
    if space_10k["assertion_count"] < 10_000 or space_10k["evidence_count"] < 10_000:
        locality_ok = False
    directional_ok = evidence_10k["p95_ms"] < 25.0

    artifact = {
        "schema_version": "vnext_evidence_support_10k_v1",
        "characterization_only": True,
        "exact_base": KNOWN_MERGE_BASE,
        "exact_head": args.exact_head or _git_head(),
        "target_assertion_id": TARGET_ASSERTION_ID,
        "target_evidence_ref_id": TARGET_EVIDENCE_ID,
        "workloads": {
            "space_10k": {
                "decoy_count": 10_000,
                "unused_sources": UNUSED_SOURCE_COUNT,
                "entity_count": space_10k["entity_count"],
                "assertion_count": space_10k["assertion_count"],
                "evidence_count": space_10k["evidence_count"],
                "artifact_count": space_10k["artifact_count"],
                "workload_digest": space_10k["workload_digest"],
                "parsed_semantic_digest": space_10k["parsed_semantic_digest"],
            },
            "space_1k": {
                "decoy_count": 1_000,
                "unused_sources": 0,
                "entity_count": space_1k["entity_count"],
                "assertion_count": space_1k["assertion_count"],
                "evidence_count": space_1k["evidence_count"],
                "artifact_count": space_1k["artifact_count"],
                "workload_digest": space_1k["workload_digest"],
                "parsed_semantic_digest": space_1k["parsed_semantic_digest"],
            },
        },
        "runs": {
            "assertion_support_10k": assertion_10k,
            "assertion_support_1k": assertion_1k,
            "evidence_support_10k": evidence_10k,
            "evidence_support_1k": evidence_1k,
            "high_support_4": high_support[4],
            "high_support_64": high_support[64],
            "high_support_256": high_support[256],
            "anchor_revalidation_10k": anchor_10k,
            "anchor_revalidation_1k": anchor_1k,
            "privacy_visible": privacy_visible,
            "privacy_hidden_only": privacy_hidden,
            "privacy_mixed": privacy_mixed,
        },
        "structural_gate": {
            "claim": (
                "fixed assertion/evidence/anchor work does not grow with unrelated corpus size; "
                "unrelated evidence and unused sources are not scanned; high-support work equals "
                "the actual supporter set; hidden-only public results stay unavailable"
            ),
            "passes": locality_ok,
            "directional_target": "10k exact evidence p95 < 25 ms",
            "observed_exact_evidence_10k_p95_ms": evidence_10k["p95_ms"],
            "directional_target_met": directional_ok,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not locality_ok:
        raise SystemExit("structural gate failed: evidence-support work escaped the requested set")


if __name__ == "__main__":
    main()
