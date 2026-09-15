#!/usr/bin/env python3
"""Scale characterization lane: 10k legacy-v6 compatibility decoding and semantic parity.

Measures:
- Historical reader parse elapsed;
- Compatibility decode & index build elapsed;
- Peak traced memory;
- Full semantic parity verification;
- Exact lookup latencies (entity, subject assertion, adjacency, alias, literal, lexical).

Usage:
    uv run python benchmarks/vnext_legacy_v6_compatibility_10k.py --size 10000
    uv run python benchmarks/vnext_legacy_v6_compatibility_10k.py \
        --size 10000 --output Docs/Benchmarks/legacy_v6_compatibility_10k_v1.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.vnext.legacy_compat import (
    COMPATIBILITY_MANIFEST_SHA256,
    COMPATIBILITY_MAPPING_REVISION,
    decode_legacy_graph_revision,
    verify_historical_semantic_parity,
)
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.domain.canonical import canonical_sha256

DEFAULT_OUTPUT_PATH = Path("Docs/Benchmarks/legacy_v6_compatibility_10k_v1.json")


def generate_synthetic_v6_workload(
    target_assertion_count: int = 10000,
    seed: int = 42,
) -> tuple[WorldGraphRevision, dict[str, Any], Any]:
    """Generate a deterministic synthetic 10k legacy-v6 graph workload."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import tests.unit.test_graph_snapshot_v6 as tu6
    rng = random.Random(seed)

    world_id = "world:benchmark-v6-scale"
    registry = tu6._registry()
    profile_ref = tu6._profile_ref()

    # Budget:
    # ~3000 objects (each has existence assertion -> 3000 assertions)
    # ~1000 objects have an aspect assertion -> 1000 assertions
    # ~500 objects have summary -> 500 assertions
    # ~500 objects have 1 alias -> 500 assertions
    # ~5000 relationships (each is an assertion -> 5000 assertions)
    # Total assertions = ~10,000 assertions!
    num_objects = max(100, int(target_assertion_count * 0.30))
    num_relationships = max(100, int(target_assertion_count * 0.50))
    num_aspects = max(50, int(target_assertion_count * 0.10))
    num_evidence = max(50, num_objects // 2)

    evidence_refs = []
    for i in range(num_evidence):
        ev_id = f"ev:bench-{i:05d}"
        evidence_refs.append({
            "schema_version": "dm_evidence_ref_v2",
            "evidence_ref_id": ev_id,
            "source_artifact_id": f"src:doc-{i % 50:03d}",
            "source_revision_id": f"srcrev:doc-{i % 50:03d}-v1",
            "source_domain_key": "buddy.worldbuilding",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
            "can_open_source": True,
            "can_highlight_span": False,
            "session_id": None,
            "source_span_ref_id": None,
            "locator": f"bench://source/{i}",
            "uri": None,
            "source_locator": None,
            "line_ref": None,
        })

    kinds = ["test:person", "test:location", "test:artifact", "test:faction", "test:event"]
    predicates = [
        "test:allied_with",
        "test:resides_in",
        "test:leads",
        "test:opposes",
        "test:safeguards",
        "test:created",
    ]

    objects = []
    aspect_map: dict[str, list[str]] = {}

    for i in range(num_objects):
        obj_id = f"obj:bench-{i:05d}"
        kind = kinds[i % len(kinds)]
        label = f"Entity {i} {kind.split(':')[1].capitalize()}"
        ev_ids = [evidence_refs[i % len(evidence_refs)]["evidence_ref_id"]]

        # Aspects
        obj_aspects = []
        if i < num_aspects:
            asp_id = f"asrt:bench-aspect-{i:05d}"
            asp_key = f"aspect_{i % 5}"
            obj_aspects.append({
                "aspect_key": asp_key,
                "kind": kinds[(i + 1) % len(kinds)],
                "assertion_metadata": {
                    "schema_version": "dm_knowledge_assertion_metadata_v1",
                    "assertion_id": asp_id,
                    "campaign_scope": "camp:scale",
                    "visibility": "player",
                    "epistemic_kind": "asserted",
                    "canon_state": "canonical",
                    "evidence_ref_ids": ev_ids,
                    "session_refs": [f"sess:{i % 20}"],
                    "temporal_scope": {
                        "schema_version": "dm_temporal_scope_ref_v1",
                        "kind": "unknown",
                    },
                },
            })
            aspect_map[obj_id] = [asp_id]

        # Aliases
        aliases = []
        if i % 6 == 0:
            aliases.append({
                "value": f"Alias-{i}",
                "assertion_metadata": {
                    "schema_version": "dm_knowledge_assertion_metadata_v1",
                    "assertion_id": f"asrt:bench-alias-{i:05d}",
                    "campaign_scope": "camp:scale" if i % 12 == 0 else None,
                    "visibility": "player" if i % 18 == 0 else "gm",
                    "epistemic_kind": "asserted",
                    "canon_state": "canonical",
                    "evidence_ref_ids": ev_ids,
                    "session_refs": [],
                    "temporal_scope": {
                        "schema_version": "dm_temporal_scope_ref_v1",
                        "kind": "world_timeless",
                    },
                },
            })

        # Summary
        summary = None
        if i % 6 == 1:
            summary = {
                "value": f"Summary prose for entity {i}",
                "assertion_metadata": {
                    "schema_version": "dm_knowledge_assertion_metadata_v1",
                    "assertion_id": f"asrt:bench-summary-{i:05d}",
                    "campaign_scope": None,
                    "visibility": "player",
                    "epistemic_kind": "inferred",
                    "canon_state": "canonical",
                    "evidence_ref_ids": ev_ids,
                    "session_refs": [],
                    "temporal_scope": {
                        "schema_version": "dm_temporal_scope_ref_v1",
                        "kind": "unknown",
                    },
                },
            }

        objects.append({
            "object_id": obj_id,
            "kind": kind,
            "label": label,
            "assertion_metadata": {
                "schema_version": "dm_knowledge_assertion_metadata_v1",
                "assertion_id": f"asrt:bench-exist-{i:05d}",
                "campaign_scope": None,
                "visibility": "player",
                "epistemic_kind": "fact",
                "canon_state": "canonical",
                "evidence_ref_ids": ev_ids,
                "session_refs": [],
                "temporal_scope": {
                    "schema_version": "dm_temporal_scope_ref_v1",
                    "kind": "world_timeless",
                },
            },
            "aliases": aliases,
            "summary": summary,
            "properties": [],
            "aspects": obj_aspects,
        })

    # Relationships
    relationships = []
    for r in range(num_relationships):
        rel_id = f"rel:bench-{r:05d}"
        src_idx = rng.randint(0, num_objects - 1)
        tgt_idx = (src_idx + rng.randint(1, num_objects - 1)) % num_objects
        src_id = objects[src_idx]["object_id"]
        tgt_id = objects[tgt_idx]["object_id"]
        pred = predicates[r % len(predicates)]
        ev_ids = [evidence_refs[r % len(evidence_refs)]["evidence_ref_id"]]

        # Optional aspect attachment
        src_aspect_id = None
        tgt_aspect_id = None
        if src_id in aspect_map and r % 4 == 0:
            src_aspect_id = aspect_map[src_id][0]
        if tgt_id in aspect_map and r % 4 == 1:
            tgt_aspect_id = aspect_map[tgt_id][0]

        relationships.append({
            "relationship_id": rel_id,
            "source_object_id": src_id,
            "target_object_id": tgt_id,
            "predicate": pred,
            "assertion_metadata": {
                "schema_version": "dm_knowledge_assertion_metadata_v1",
                "assertion_id": f"asrt:bench-rel-{r:05d}",
                "campaign_scope": "camp:scale" if r % 3 == 0 else None,
                "visibility": "player" if r % 5 != 0 else "gm",
                "epistemic_kind": "asserted",
                "canon_state": "canonical",
                "evidence_ref_ids": ev_ids,
                "session_refs": [f"sess:{r % 10}"],
                "temporal_scope": {
                    "schema_version": "dm_temporal_scope_ref_v1",
                    "kind": "unknown",
                },
            },
            "source_aspect_assertion_id": src_aspect_id,
            "target_aspect_assertion_id": tgt_aspect_id,
        })

    payload: dict[str, Any] = {
        "world_id": world_id,
        "semantic_profile": profile_ref,
        "relationship_endpoint_aspect_schema": "dm_relationship_endpoint_aspect_v1",
        "objects": objects,
        "relationships": relationships,
        "evidence_refs": evidence_refs,
    }

    payload_sha256 = canonical_sha256(payload)

    revision = WorldGraphRevision(
        schema_version="dm_graph_revision_v1",
        world_id=world_id,
        revision_id="rev:bench-v6-scale-10k",
        parent_revision_id=None,
        created_at=datetime.now(UTC),
        operation_ids=["op:bench-scale-init"],
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload_sha256=payload_sha256,
        status="published",
    )

    return revision, payload, registry


def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    sorted_d = sorted(data)
    idx = int(len(sorted_d) * pct)
    return sorted_d[min(idx, len(sorted_d) - 1)]


def run_benchmark(
    size: int = 10000,
    seed: int = 42,
    sample_size: int = 200,
) -> dict[str, Any]:
    print(f"Generating synthetic 10k v6 workload (target={size}, seed={seed})...")
    rev, payload, registry = generate_synthetic_v6_workload(
        target_assertion_count=size, seed=seed
    )

    # 1. Historical Reader parse baseline
    print("Parsing with historical VersionedUnionGraphSnapshotReader...")
    t0_hist = time.perf_counter()
    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(
        graph_schema=rev.graph_schema,
        graph_payload=payload,
    )
    hist_parse_ms = (time.perf_counter() - t0_hist) * 1000

    # 2. Compatibility decoder + index build
    print("Decoding with compatibility decoder (ParsedKnowledgeRevision build)...")
    tracemalloc.start()
    t0_compat = time.perf_counter()
    parsed_rev = decode_legacy_graph_revision(
        revision=rev,
        graph_payload=payload,
        profile_registry=registry,
    )
    compat_build_ms = (time.perf_counter() - t0_compat) * 1000
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 3. Parity verification
    print("Verifying canonical semantic parity...")
    t0_parity = time.perf_counter()
    parity_ok, hist_sha, parsed_sha = verify_historical_semantic_parity(
        hist_snapshot, parsed_rev
    )
    parity_check_ms = (time.perf_counter() - t0_parity) * 1000

    if not parity_ok:
        raise RuntimeError(
            f"10k scale parity mismatch! hist={hist_sha} parsed={parsed_sha}"
        )

    # 4. Lookup latency characterizations
    print("Characterizing lookup latencies on normalized indexes...")
    rng = random.Random(seed)

    # Entity lookup
    ent_keys = list(parsed_rev.entities_by_id.keys())
    ent_sample = rng.sample(ent_keys, min(sample_size, len(ent_keys)))
    timings_entity = []
    for k in ent_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.get_entity(k)
        timings_entity.append((time.perf_counter() - t_start) * 1_000_000)

    # Subject assertion lookup
    timings_subj = []
    for k in ent_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.get_subject_assertion_ids(k)
        timings_subj.append((time.perf_counter() - t_start) * 1_000_000)

    # Adjacency lookup
    timings_adj = []
    for k in ent_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.get_adjacent_entities(k)
        timings_adj.append((time.perf_counter() - t_start) * 1_000_000)

    # Evidence lookup
    ev_keys = list(parsed_rev.evidence_by_id.keys())
    ev_sample = rng.sample(ev_keys, min(sample_size, len(ev_keys)))
    timings_ev = []
    for k in ev_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.get_evidence(k)
        timings_ev.append((time.perf_counter() - t_start) * 1_000_000)

    # Literal lookup
    lit_keys = list(parsed_rev.literal_exact_index.keys())
    lit_sample = rng.sample(lit_keys, min(sample_size, len(lit_keys)))
    timings_lit = []
    for pred, c_json in lit_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.lookup_literal(pred, c_json)
        timings_lit.append((time.perf_counter() - t_start) * 1_000_000)

    # Lexical candidate lookup
    lex_keys = list(parsed_rev.lexical_candidate_index.keys())
    lex_sample = rng.sample(lex_keys, min(sample_size, len(lex_keys)))
    timings_lex = []
    for tok in lex_sample:
        t_start = time.perf_counter()
        _ = parsed_rev.lookup_lexical_candidates(tok)
        timings_lex.append((time.perf_counter() - t_start) * 1_000_000)

    entity_ref_count = sum(
        1 for asrt in parsed_rev.assertions_by_id.values()
        if isinstance(asrt.value, ParsedEntityRefValue)
    )

    result = {
        "benchmark_schema": "legacy_v6_compatibility_benchmark_v1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "graph_schema": GRAPH_SCHEMA_V6,
        "compatibility_mapping_revision": COMPATIBILITY_MAPPING_REVISION,
        "manifest_sha256": COMPATIBILITY_MANIFEST_SHA256,
        "legacy_payload_sha256": rev.graph_payload_sha256,
        "historical_parse_compatibility_id": reader.parse_compatibility_id,
        "workload": {
            "target_size": size,
            "seed": seed,
            "sample_size": sample_size,
            "legacy_payload_sha256": rev.graph_payload_sha256,
        },
        "parity_verification": {
            "parity": "PASS",
            "historical_witness_sha256": hist_sha,
            "compat_witness_sha256": parsed_sha,
            "parity_verification_ms": round(parity_check_ms, 3),
        },
        "cardinalities": {
            "entity_count": len(parsed_rev.entities_by_id),
            "assertion_count": len(parsed_rev.assertions_by_id),
            "entity_ref_assertion_count": entity_ref_count,
            "evidence_count": len(parsed_rev.evidence_by_id),
            "identity_alias_count": len(parsed_rev.aliases_by_id),
            "unique_subjects_indexed": len(parsed_rev.assertions_by_subject),
            "unique_literal_keys_indexed": len(parsed_rev.literal_exact_index),
            "unique_lexical_tokens_indexed": len(parsed_rev.lexical_candidate_index),
        },
        "performance": {
            "historical_reader_parse_ms": round(hist_parse_ms, 3),
            "compatibility_decode_build_ms": round(compat_build_ms, 3),
            "peak_traced_memory_bytes": peak_mem,
            "peak_traced_memory_mb": round(peak_mem / (1024 * 1024), 2),
        },
        "lookup_latencies_us": {
            "exact_entity_lookup": {
                "p50_us": round(percentile(timings_entity, 0.50), 3),
                "p95_us": round(percentile(timings_entity, 0.95), 3),
                "samples": len(timings_entity),
            },
            "subject_assertion_lookup": {
                "p50_us": round(percentile(timings_subj, 0.50), 3),
                "p95_us": round(percentile(timings_subj, 0.95), 3),
                "samples": len(timings_subj),
            },
            "adjacency_lookup": {
                "p50_us": round(percentile(timings_adj, 0.50), 3),
                "p95_us": round(percentile(timings_adj, 0.95), 3),
                "samples": len(timings_adj),
            },
            "evidence_lookup": {
                "p50_us": round(percentile(timings_ev, 0.50), 3),
                "p95_us": round(percentile(timings_ev, 0.95), 3),
                "samples": len(timings_ev),
            },
            "literal_exact_lookup": {
                "p50_us": round(percentile(timings_lit, 0.50), 3),
                "p95_us": round(percentile(timings_lit, 0.95), 3),
                "samples": len(timings_lit),
            },
            "lexical_candidate_lookup": {
                "p50_us": round(percentile(timings_lex, 0.50), 3),
                "p95_us": round(percentile(timings_lex, 0.95), 3),
                "samples": len(timings_lex),
            },
        },
        "semantic_digest": parsed_rev.semantic_digest,
        "compatibility_key": parsed_rev.compatibility_key,
    }

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark and characterization for 10k legacy-v6 compatibility decoding."
    )
    parser.add_argument("--size", type=int, default=10000, help="Target assertion count")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON artifact path",
    )

    args = parser.parse_args()

    data = run_benchmark(size=args.size, seed=args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    args.output.write_text(serialized, encoding="utf-8")

    print(f"\nCharacterization complete. Artifact written to {args.output}")
    print(f"  Assertions: {data['cardinalities']['assertion_count']}")
    print(f"  Historical parse: {data['performance']['historical_reader_parse_ms']} ms")
    print(f"  Compatibility decode: {data['performance']['compatibility_decode_build_ms']} ms")
    print(f"  Peak memory: {data['performance']['peak_traced_memory_mb']} MB")
    print(f"  Parity: {data['parity_verification']['parity']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
