"""Benchmark and characterization lane for vNext ParsedKnowledgeRevision and structural indexes.

Measures:
- normalized-model build elapsed;
- peak traced memory;
- exact entity lookup p50/p95;
- subject-assertion lookup p50/p95;
- adjacency lookup p50/p95;
- evidence-supporter lookup p50/p95;
- alias exact lookup p50/p95;
- literal exact lookup p50/p95;
- lexical candidate lookup p50/p95.

Usage:
    uv run python benchmarks/vnext_parsed_knowledge_revision.py --size 10000
    uv run python benchmarks/vnext_parsed_knowledge_revision.py \
        --size 10000 --output Docs/Benchmarks/vnext_parsed_knowledge_revision_10k_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.vnext import (
    build_parsed_knowledge_revision,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAnyVisibility,
    PublicVisibility,
    ScopeBinding,
    TimelessTemporalScope,
    UtcIntervalTemporalScope,
    canonical_json,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractRef,
    Entity,
    EntityRefValue,
    LiteralValue,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import (
    IdentityAlias,
    KnowledgeRevision,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3


def generate_synthetic_workload(
    size: int = 10000,
    seed: int = 42,
) -> tuple[
    KnowledgeRevision,
    list[Entity],
    list[Assertion],
    list[IdentityAlias],
    list[EvidenceRefV3],
    dict[str, Any],
]:
    """Generate a deterministic synthetic vNext knowledge workload."""
    rng = random.Random(seed)

    entity_count = max(100, size // 2)
    evidence_count = max(50, size // 4)
    alias_count = max(50, size // 5)
    assertion_count = size

    workload_config = {
        "workload_name": "vnext_parsed_revision_synthetic_characterization",
        "workload_version": "v1",
        "size": size,
        "seed": seed,
        "entity_count": entity_count,
        "assertion_count": assertion_count,
        "evidence_count": evidence_count,
        "alias_count": alias_count,
    }
    workload_digest = hashlib.sha256(canonical_json(workload_config)).hexdigest()
    workload_config["workload_digest"] = workload_digest

    # 1. Entities
    entities = [
        Entity(entity_id=f"ent_{i:06d}")
        for i in range(entity_count)
    ]

    # 2. Evidence
    evidence = [
        EvidenceRefV3(
            evidence_ref_id=f"ev_{i:06d}",
            source_artifact_id=f"art_{(i % 200):04d}",
            source_revision_id=f"rev_{(i % 200):04d}_v1",
            evidence_role=rng.choice(["support", "context", "contradiction"]),
            can_open_source=True,
            can_highlight_span=bool(i % 2 == 0),
            locator=f"doc://corpus/file_{(i % 50)}.md#L{i}",
            uri=f"https://corpus.internal/file_{(i % 50)}.md",
        )
        for i in range(evidence_count)
    ]

    # 3. Aliases
    common_names = ["Alden", "Braith", "Caelum", "Drakos", "Eldyr", "Faelen", "Gisla", "Harrow"]
    aliases = []
    for i in range(alias_count):
        eid = entities[i % entity_count].entity_id
        base_name = rng.choice(common_names)
        alias_text = f"{base_name} of the North {i % 50}"
        ev_sample = [
            evidence[(i * 3 + j) % evidence_count].evidence_ref_id
            for j in range(rng.randint(0, 2))
        ]
        aliases.append(
            IdentityAlias(
                alias_id=f"alias_{i:06d}",
                entity_id=eid,
                alias_text=alias_text,
                evidence_ref_ids=sorted(set(ev_sample)),
                standing=rng.choice([KnowledgeStanding.ESTABLISHED, KnowledgeStanding.PROVISIONAL]),
            )
        )

    # 4. Assertions
    predicates = [
        "core:name",
        "core:description",
        "core:status",
        "core:connected_to",
        "core:allied_with",
        "core:located_in",
        "core:classification",
    ]
    term_refs = ["core:npc", "core:location", "core:faction", "core:artifact"]

    assertions = []
    entity_ref_count = 0
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)

    for i in range(assertion_count):
        subject = entities[i % entity_count].entity_id
        pred = rng.choice(predicates)

        # 30% entity ref, 50% literal, 20% term ref
        r = rng.random()
        val: EntityRefValue | LiteralValue | TermRefValue
        if r < 0.30:
            target = entities[rng.randint(0, entity_count - 1)].entity_id
            val = EntityRefValue(entity_id=target)
            entity_ref_count += 1
        elif r < 0.80:
            val = LiteralValue(
                value={
                    "text": f"Descriptive payload for entity {subject} attribute {i}",
                    "metric": i * 17 % 1000,
                    "active": bool(i % 2 == 0),
                }
            )
        else:
            val = TermRefValue(term=rng.choice(term_refs))

        ev_sample = [
            evidence[(i * 7 + j) % evidence_count].evidence_ref_id
            for j in range(rng.randint(1, 3))
        ]

        vis = (
            PublicVisibility()
            if (i % 3 == 0)
            else LabelsAnyVisibility(labels=["scope:internal", "role:reviewer"])
        )

        temporal = (
            TimelessTemporalScope()
            if (i % 2 == 0)
            else UtcIntervalTemporalScope(
                valid_from=now,
                valid_until=None,
            )
        )

        meta = AssertionMetadata(
            scope=[ScopeBinding(axis="core:universe", value="canonical")],
            visibility=vis,
            epistemic_basis=rng.choice([EpistemicBasis.ASSERTED, EpistemicBasis.INFERRED]),
            claim_mode="core:fact",
            standing=rng.choice([
                KnowledgeStanding.ESTABLISHED,
                KnowledgeStanding.PROVISIONAL,
                KnowledgeStanding.RETRACTED,
            ]),
            evidence_ref_ids=sorted(set(ev_sample)),
            temporal_scope=temporal,
            domain_metadata=[],
        )

        assertions.append(
            Assertion(
                assertion_id=f"asrt_{i:07d}",
                subject_entity_id=subject,
                predicate=pred,
                value=val,
                metadata=meta,
            )
        )

    workload_config["entity_ref_assertion_count"] = entity_ref_count

    # 5. Revision header
    revision = KnowledgeRevision(
        space_id="space:benchmark-10k",
        revision_id="rev:synthetic-0001",
        created_at=now,
        operation_ids=["op:synth-0001"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id="benchmark.domain",
            domain_revision="1",
            descriptor_sha256="1" * 64,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id="benchmark.profile",
            profile_revision="1",
            descriptor_sha256="2" * 64,
        ),
    )

    return revision, entities, assertions, aliases, evidence, workload_config


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def run_benchmark(size: int = 10000, seed: int = 42) -> dict[str, Any]:
    (
        revision,
        entities,
        assertions,
        aliases,
        evidence,
        workload_config,
    ) = generate_synthetic_workload(size=size, seed=seed)

    # Measure build & memory
    tracemalloc.start()
    t0 = time.perf_counter()
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        aliases=aliases,
        evidence=evidence,
    )
    build_elapsed_sec = time.perf_counter() - t0
    _current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Query benchmark lanes (1000 samples each)
    sample_size = min(1000, len(entities))
    rng = random.Random(seed + 1)

    # 1. Exact entity lookup
    entity_sample = [rng.choice(entities).entity_id for _ in range(sample_size)]
    timings_entity = []
    for eid in entity_sample:
        t_start = time.perf_counter()
        _ = parsed.get_entity(eid)
        timings_entity.append((time.perf_counter() - t_start) * 1_000_000)

    # 2. Subject assertion lookup
    timings_subject = []
    for eid in entity_sample:
        t_start = time.perf_counter()
        _ = parsed.get_subject_assertions(eid)
        timings_subject.append((time.perf_counter() - t_start) * 1_000_000)

    # 3. Adjacency lookup
    timings_adj = []
    for eid in entity_sample:
        t_start = time.perf_counter()
        _ = parsed.get_adjacent_entities(eid)
        timings_adj.append((time.perf_counter() - t_start) * 1_000_000)

    # 4. Evidence supporter lookup
    evidence_sample = [
        rng.choice(evidence).evidence_ref_id
        for _ in range(min(sample_size, len(evidence)))
    ]
    timings_evidence = []
    for evid in evidence_sample:
        t_start = time.perf_counter()
        _ = parsed.get_evidence_supporters(evid)
        timings_evidence.append((time.perf_counter() - t_start) * 1_000_000)

    # 5. Alias lookup
    alias_sample = [
        rng.choice(aliases).alias_text
        for _ in range(min(sample_size, len(aliases)))
    ]
    timings_alias = []
    for txt in alias_sample:
        t_start = time.perf_counter()
        _ = parsed.lookup_alias(txt)
        timings_alias.append((time.perf_counter() - t_start) * 1_000_000)

    # 6. Literal exact lookup
    lit_sample = []
    for k in list(parsed.literal_exact_index.keys())[:sample_size]:
        lit_sample.append(k)
    timings_literal = []
    for pred, canon_json in lit_sample:
        t_start = time.perf_counter()
        _ = parsed.lookup_literal(pred, canon_json)
        timings_literal.append((time.perf_counter() - t_start) * 1_000_000)

    # 7. Lexical candidate lookup
    lex_sample = list(parsed.lexical_candidate_index.keys())[:sample_size]
    timings_lexical = []
    for tok in lex_sample:
        t_start = time.perf_counter()
        _ = parsed.lookup_lexical_candidates(tok)
        timings_lexical.append((time.perf_counter() - t_start) * 1_000_000)

    result = {
        "benchmark_schema": "vnext_parsed_revision_benchmark_v1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "workload": workload_config,
        "semantic_digest": parsed.semantic_digest,
        "compatibility_key": parsed.compatibility_key,
        "format_version": parsed.format_version,
        "cardinalities": {
            "entity_count": len(parsed.entities_by_id),
            "assertion_count": len(parsed.assertions_by_id),
            "evidence_count": len(parsed.evidence_by_id),
            "alias_count": len(parsed.aliases_by_id),
            "unique_subjects_indexed": len(parsed.assertions_by_subject),
            "unique_literal_keys_indexed": len(parsed.literal_exact_index),
            "unique_alias_keys_indexed": len(parsed.alias_exact_index),
            "unique_lexical_tokens_indexed": len(parsed.lexical_candidate_index),
        },
        "build_elapsed_ms": round(build_elapsed_sec * 1000, 3),
        "peak_traced_memory_bytes": peak_mem,
        "peak_traced_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "lookup_latencies_us": {
            "exact_entity_lookup": {
                "p50_us": round(percentile(timings_entity, 0.50), 3),
                "p95_us": round(percentile(timings_entity, 0.95), 3),
                "samples": len(timings_entity),
            },
            "subject_assertion_lookup": {
                "p50_us": round(percentile(timings_subject, 0.50), 3),
                "p95_us": round(percentile(timings_subject, 0.95), 3),
                "samples": len(timings_subject),
            },
            "adjacency_lookup": {
                "p50_us": round(percentile(timings_adj, 0.50), 3),
                "p95_us": round(percentile(timings_adj, 0.95), 3),
                "samples": len(timings_adj),
            },
            "evidence_supporter_lookup": {
                "p50_us": round(percentile(timings_evidence, 0.50), 3),
                "p95_us": round(percentile(timings_evidence, 0.95), 3),
                "samples": len(timings_evidence),
            },
            "alias_exact_lookup": {
                "p50_us": round(percentile(timings_alias, 0.50), 3),
                "p95_us": round(percentile(timings_alias, 0.95), 3),
                "samples": len(timings_alias),
            },
            "literal_exact_lookup": {
                "p50_us": round(percentile(timings_literal, 0.50), 3),
                "p95_us": round(percentile(timings_literal, 0.95), 3),
                "samples": len(timings_literal),
            },
            "lexical_candidate_lookup": {
                "p50_us": round(percentile(timings_lexical, 0.50), 3),
                "p95_us": round(percentile(timings_lexical, 0.95), 3),
                "samples": len(timings_lexical),
            },
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run vNext ParsedKnowledgeRevision structural benchmark"
    )
    parser.add_argument(
        "--size", type=int, default=10000, help="Target assertion count (default: 10000)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for deterministic generation (default: 42)",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    result = run_benchmark(size=args.size, seed=args.seed)
    formatted = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + "\n", encoding="utf-8")
        print(f"Wrote benchmark artifact to {args.output}")
    print(formatted)


if __name__ == "__main__":
    main()
