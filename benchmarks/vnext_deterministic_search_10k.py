"""Structural characterization of vNext deterministic indexed search."""

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
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.search import SearchReadService, _capture_search_read_trace
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
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
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

KNOWN_MERGE_BASE = "8aa654bc192c1aeb51a5f908a44fce9a1c4c5b4c"
HIGH_FREQUENCY_COUNT = 256
HIDDEN_DECOY_COUNT = 40
TARGET_ENTITY_ID = "id:target"
MIXED_ENTITY_ID = "id:mixed"
VISIBLE_RANK_ENTITY_ID = "id:visible-rank"


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _domain_and_profile() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2]:
    domain_contract = DomainContractDescriptor(
        domain_id="bench.search",
        domain_revision="1",
        scope_axes=["bench:scope"],
        visibility_labels=["bench:audience", "bench:hidden"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    semantic_profile = SemanticProfileDescriptorV2(
        profile_id="bench.search.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:title", allowed_value_kinds=["literal"]),
            SemanticProfilePredicate(term="bench:signal", allowed_value_kinds=["literal"]),
            SemanticProfilePredicate(term="bench:kind", allowed_value_kinds=["term_ref"]),
        ],
    )
    return domain_contract, semantic_profile


def _meta(
    evidence_id: str,
    *,
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
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
    text: str,
    evidence_id: str,
    *,
    predicate: str = "bench:title",
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate=predicate,
        value=LiteralValue(value=text),
        metadata=_meta(evidence_id, visibility=visibility),
    )


def _term(assertion_id: str, subject: str, evidence_id: str) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="bench:kind",
        value=TermRefValue(term="bench:kind_active"),
        metadata=_meta(evidence_id),
    )


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
        content_sha256="a" * 64,
        body_storage="inline",
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
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


def _build_space(*, decoy_count: int) -> dict[str, Any]:
    domain_contract, semantic_profile = _domain_and_profile()
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))
    hidden = LabelsAllVisibility(labels=["bench:hidden"])

    visible_art, visible_rev, visible_ev = _named_source(
        evidence_id="evidence:visible",
        artifact_id="src:visible",
        revision_id="srcrev:visible",
    )
    hidden_art, hidden_rev, hidden_ev = _named_source(
        evidence_id="evidence:hidden",
        artifact_id="src:hidden",
        revision_id="srcrev:hidden",
    )
    artifacts = {
        visible_art.source_artifact_id: visible_art,
        hidden_art.source_artifact_id: hidden_art,
    }
    revisions = {
        visible_rev.source_revision_id: visible_rev,
        hidden_rev.source_revision_id: hidden_rev,
    }
    evidence = [visible_ev, hidden_ev]
    entities = [
        Entity(entity_id=TARGET_ENTITY_ID),
        Entity(entity_id=MIXED_ENTITY_ID),
        Entity(entity_id=VISIBLE_RANK_ENTITY_ID),
    ]
    assertions = [
        _literal("asrt:target-rare", TARGET_ENTITY_ID, "raretoken marker", "evidence:visible"),
        _literal(
            "asrt:target-signal",
            TARGET_ENTITY_ID,
            "signalvalue",
            "evidence:visible",
            predicate="bench:signal",
        ),
        _term("asrt:target-kind", TARGET_ENTITY_ID, "evidence:visible"),
        _literal("asrt:mixed-visible", MIXED_ENTITY_ID, "mixedtoken chamber", "evidence:visible"),
        _literal(
            "asrt:mixed-hidden",
            MIXED_ENTITY_ID,
            "mixedtoken extra",
            "evidence:hidden",
            visibility=hidden,
        ),
        _literal(
            "asrt:visible-rank",
            VISIBLE_RANK_ENTITY_ID,
            "obsidian flake",
            "evidence:visible",
        ),
    ]

    for index in range(HIGH_FREQUENCY_COUNT):
        subject = f"id:hit{index:03d}"
        entities.append(Entity(entity_id=subject))
        assertions.append(
            _literal(f"asrt:hit-{index:03d}", subject, "commonstone marker", "evidence:visible")
        )

    for index in range(HIDDEN_DECOY_COUNT):
        subject = f"id:hdecoy{index:02d}"
        entities.append(Entity(entity_id=subject))
        for copy_n in range(4):
            assertions.append(
                _literal(
                    f"asrt:hdecoy-{index:02d}-{copy_n}",
                    subject,
                    "obsidian flake chamber vault marble extra",
                    "evidence:hidden",
                    visibility=hidden,
                )
            )

    for index in range(decoy_count):
        subject = f"id:decoy{index:05d}"
        entities.append(Entity(entity_id=subject))
        assertions.append(
            _literal(f"asrt:decoy-{index:05d}", subject, "unrelated filler", "evidence:visible")
        )

    revision = KnowledgeRevision(
        space_id="space:bench-search",
        revision_id=f"rev:bench-{decoy_count}",
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
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
            "high_frequency_count": HIGH_FREQUENCY_COUNT,
            "hidden_decoy_count": HIDDEN_DECOY_COUNT,
            "entity_count": len(entities),
            "assertion_count": len(assertions),
        }
    )
    return {
        "context": context,
        "parsed_semantic_digest": parsed.semantic_digest,
        "workload_digest": workload_digest,
        "entity_count": len(entities),
        "assertion_count": len(assertions),
        "evidence_count": len(evidence),
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


def _trace_payload(trace: Any) -> dict[str, int]:
    return {
        "index_lookups": trace.index_lookups,
        "exact_id_lookups": trace.exact_id_lookups,
        "structural_assertion_candidates": trace.structural_assertion_candidates,
        "deduped_match_witness_assertions": trace.deduped_match_witness_assertions,
        "assertions_evaluated": trace.assertions_evaluated,
        "policy_evaluations": trace.policy_evaluations,
        "unique_artifact_ids_requested": trace.unique_artifact_ids_requested,
        "unique_revision_ids_requested": trace.unique_revision_ids_requested,
        "provenance_snapshot_calls": trace.provenance_snapshot_calls,
        "admitted_match_assertions": trace.admitted_match_assertions,
        "returned_entities": trace.returned_entities,
    }


def _time_search(
    *,
    context: KnowledgeReadContext,
    query: str,
    limit: int,
    iterations: int,
) -> dict[str, Any]:
    service = SearchReadService()
    samples: list[float] = []
    last_digest = ""
    last_hit_ids: list[str] = []
    last_scores: list[int] = []
    traces: list[Any] = []
    for _ in range(iterations):
        start = time.perf_counter()
        with _capture_search_read_trace() as captured:
            result = service.search_entities(_fresh(context), query, limit=limit)
        samples.append((time.perf_counter() - start) * 1000.0)
        last_digest = result.result_digest
        last_hit_ids = [hit.entity.entity_id for hit in result.hits]
        last_scores = [hit.deterministic_score for hit in result.hits]
        traces = captured
    dumped = str(result)
    return {
        **_percentiles(samples),
        **_trace_payload(traces[-1]),
        "query": query,
        "limit": limit,
        "result_digest": last_digest,
        "returned_hit_ids": last_hit_ids,
        "returned_hit_count": len(last_hit_ids),
        "returned_scores": last_scores,
        "completeness": result.completeness.status,
        "public_exposes_candidate_counts": "structural_assertion_candidates" in dumped,
        "public_exposes_last_trace": "last_trace" in dumped,
    }


def _structural_equal(left: dict[str, Any], right: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(left[key] == right[key] for key in keys)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="Docs/Benchmarks/vnext_deterministic_search_10k_v1.json")
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument(
        "--exact-head",
        default="",
        help="Pin the substantive implementation HEAD rather than this process HEAD.",
    )
    args = parser.parse_args()

    space_10k = _build_space(decoy_count=10_000)
    space_1k = _build_space(decoy_count=1_000)
    half = max(20, args.iterations // 2)

    lexical_10k = _time_search(
        context=space_10k["context"],
        query="raretoken",
        limit=20,
        iterations=args.iterations,
    )
    lexical_1k = _time_search(
        context=space_1k["context"],
        query="raretoken",
        limit=20,
        iterations=half,
    )
    exact_id_10k = _time_search(
        context=space_10k["context"],
        query=TARGET_ENTITY_ID,
        limit=20,
        iterations=args.iterations,
    )
    predicate_10k = _time_search(
        context=space_10k["context"],
        query="bench:signal",
        limit=20,
        iterations=args.iterations,
    )
    term_10k = _time_search(
        context=space_10k["context"],
        query="bench:kind_active",
        limit=20,
        iterations=args.iterations,
    )
    mixed_10k = _time_search(
        context=space_10k["context"],
        query="mixedtoken",
        limit=20,
        iterations=args.iterations,
    )
    hidden_decoy_10k = _time_search(
        context=space_10k["context"],
        query="obsidian",
        limit=1,
        iterations=args.iterations,
    )
    high_frequency_10k = _time_search(
        context=space_10k["context"],
        query="commonstone",
        limit=HIGH_FREQUENCY_COUNT,
        iterations=max(12, args.iterations // 2),
    )

    locality_keys = (
        "structural_assertion_candidates",
        "deduped_match_witness_assertions",
        "assertions_evaluated",
        "unique_artifact_ids_requested",
        "unique_revision_ids_requested",
        "provenance_snapshot_calls",
        "admitted_match_assertions",
        "returned_hit_count",
    )
    locality_ok = (
        _structural_equal(lexical_10k, lexical_1k, locality_keys)
        and lexical_10k["structural_assertion_candidates"] == 1
        and lexical_10k["returned_hit_ids"] == [TARGET_ENTITY_ID]
        and exact_id_10k["returned_hit_ids"] == [TARGET_ENTITY_ID]
        and exact_id_10k["structural_assertion_candidates"] == 0
        and exact_id_10k["assertions_evaluated"] == 0
        and predicate_10k["structural_assertion_candidates"] == 1
        and predicate_10k["returned_hit_ids"] == [TARGET_ENTITY_ID]
        and term_10k["structural_assertion_candidates"] == 1
        and term_10k["returned_hit_ids"] == [TARGET_ENTITY_ID]
        and mixed_10k["returned_hit_ids"] == [MIXED_ENTITY_ID]
        and mixed_10k["admitted_match_assertions"] == 1
        and mixed_10k["structural_assertion_candidates"] == 2
        and hidden_decoy_10k["returned_hit_ids"] == [VISIBLE_RANK_ENTITY_ID]
        and hidden_decoy_10k["structural_assertion_candidates"] == 1 + HIDDEN_DECOY_COUNT * 4
        and hidden_decoy_10k["admitted_match_assertions"] == 1
        and high_frequency_10k["structural_assertion_candidates"] == HIGH_FREQUENCY_COUNT
        and high_frequency_10k["returned_hit_count"] == HIGH_FREQUENCY_COUNT
        and not lexical_10k["public_exposes_candidate_counts"]
        and not lexical_10k["public_exposes_last_trace"]
        and space_10k["assertion_count"] >= 10_000
    )
    directional_ok = lexical_10k["p95_ms"] < 100.0

    artifact = {
        "schema_version": "vnext_deterministic_search_10k_v1",
        "characterization_only": True,
        "exact_base": KNOWN_MERGE_BASE,
        "exact_head": args.exact_head or _git_head(),
        "seed": "deterministic-indexed-search-v1",
        "high_frequency_count": HIGH_FREQUENCY_COUNT,
        "hidden_decoy_count": HIDDEN_DECOY_COUNT,
        "workloads": {
            "space_10k": {
                "decoy_count": 10_000,
                "entity_count": space_10k["entity_count"],
                "assertion_count": space_10k["assertion_count"],
                "evidence_count": space_10k["evidence_count"],
                "workload_digest": space_10k["workload_digest"],
                "parsed_semantic_digest": space_10k["parsed_semantic_digest"],
            },
            "space_1k": {
                "decoy_count": 1_000,
                "entity_count": space_1k["entity_count"],
                "assertion_count": space_1k["assertion_count"],
                "evidence_count": space_1k["evidence_count"],
                "workload_digest": space_1k["workload_digest"],
                "parsed_semantic_digest": space_1k["parsed_semantic_digest"],
            },
        },
        "runs": {
            "lexical_10k": lexical_10k,
            "lexical_1k": lexical_1k,
            "exact_id_10k": exact_id_10k,
            "predicate_10k": predicate_10k,
            "term_ref_10k": term_10k,
            "mixed_visible_hidden_10k": mixed_10k,
            "hidden_decoy_ranking_10k": hidden_decoy_10k,
            "high_frequency_10k": high_frequency_10k,
        },
        "structural_gate": {
            "claim": (
                "fixed low-frequency search work does not grow with unrelated corpus size; "
                "hidden matches cannot change visible membership/order/digest; "
                "high-frequency work equals the real structural match set"
            ),
            "passes": locality_ok,
            "directional_target": "10k deterministic search p95 < 100 ms",
            "observed_lexical_10k_p95_ms": lexical_10k["p95_ms"],
            "directional_target_met": directional_ok,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not locality_ok:
        raise SystemExit("structural gate failed: indexed search escaped the real match set")


if __name__ == "__main__":
    main()
