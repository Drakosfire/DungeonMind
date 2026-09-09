#!/usr/bin/env python3
"""Live Eldyrwild witness for complete selected-object one-hop reads.

Characterizes ``get_complete_object`` against the V4 Eldyrwild authority store.
Source prose is never printed. Selected-object identity is recorded because
the owning handoff requires an exact-object completeness/timing handback.

This is a characterization runner, not a CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from world_graph_live_postgres import (
    EXPECTED_DA,
    EXPECTED_HEAD,
    EXPECTED_M0,
    EXPECTED_M1,
    EXPECTED_RECEIPT_SCHEMA,
    _CollectingObserver,
    _phase_map,
    _request,
)

from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

WARM_RUNS_DEFAULT = 3
FAST_ENOUGH_WARM_MS = 2000.0


def _highest_degree_object(graph: Any) -> tuple[str, int]:
    degrees: dict[str, int] = defaultdict(int)
    for rel in graph.relationships.values():
        degrees[rel.subject_object_id] += 1
        degrees[rel.object_object_id] += 1
    if not degrees:
        raise SystemExit("error: projected graph has no admitted relationships")
    object_id = max(degrees, key=lambda oid: degrees[oid])
    return object_id, degrees[object_id]


def _observation_payload(observation: Any) -> dict[str, Any]:
    return {
        "operation": observation.operation,
        "outcome": observation.outcome,
        "duration_ms": round(observation.duration_seconds * 1000.0, 3),
        "phase_ms": {
            phase: round(ms, 3) for phase, ms in _phase_map(observation).items()
        },
        "parsed_revision_cache_hit": observation.parsed_revision_cache_hit,
        "admitted_object_count": observation.admitted_object_count,
        "admitted_relationship_count": observation.admitted_relationship_count,
        "admitted_evidence_count": observation.admitted_evidence_count,
        "result_object_count": observation.result_object_count,
        "result_relationship_count": observation.result_relationship_count,
        "result_assertion_count": observation.result_assertion_count,
        "result_anchor_count": observation.result_anchor_count,
        "completeness_status": observation.completeness_status,
        "completeness_reason": observation.completeness_reason,
        "truncated_fields": list(observation.truncated_fields),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DUNGEONMIND_DATABASE_URL",
            os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", ""),
        ),
    )
    parser.add_argument("--world-id", default="eldyrwild")
    parser.add_argument("--object-id", default="")
    parser.add_argument("--warm-runs", type=int, default=WARM_RUNS_DEFAULT)
    parser.add_argument("-o", "--output", default="/tmp/complete-object-eldyrwild.json")
    args = parser.parse_args(argv)
    if not args.database_url:
        print("error: --database-url required", file=sys.stderr)
        return 2
    if args.warm_runs < 1:
        print("error: --warm-runs must be >= 1", file=sys.stderr)
        return 2

    bundle = PostgresRepositoryBundle(PostgresDatabase(args.database_url))
    receipt = bundle.existing_world_adoptions.get_for_world(args.world_id)
    head_before = bundle.world_graph.get_head(args.world_id)
    if receipt is None or head_before is None:
        print("error: missing adoption receipt or graph head", file=sys.stderr)
        return 2

    served = getattr(receipt, "effective_membership_sha256", None) or getattr(
        receipt, "membership_sha256", None
    )
    failures: list[str] = []
    if receipt.published_revision_id != EXPECTED_DA:
        failures.append("D_A mismatch")
    if head_before.head_revision_id != EXPECTED_HEAD:
        failures.append(
            f"head mismatch: {head_before.head_revision_id!r} != {EXPECTED_HEAD!r}"
        )
    if failures:
        print("error: identity preflight failed:", *failures, sep="\n  ", file=sys.stderr)
        return 2
    print("identity preflight: ok (living head and D_A match Eldyrwild pins)")
    if receipt.schema_version != EXPECTED_RECEIPT_SCHEMA:
        print(
            f"  note: receipt schema {receipt.schema_version!r} "
            f"(expected {EXPECTED_RECEIPT_SCHEMA!r})"
        )

    observer = _CollectingObserver()
    projection = WorldGraphProjectionService(
        world_graph=bundle.world_graph,
        sources=bundle.sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
        ),
        reviewed_world_initializations=bundle.reviewed_world_initializations,
        read_observer=observer,
    )
    retrieval = WorldGraphRetrievalService(
        projection=projection,
        sources=bundle.sources,
        read_observer=observer,
    )
    request = _request(
        world_id=args.world_id,
        campaign_id=None,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
    )

    setup = projection.project(request)
    if args.object_id:
        object_id = args.object_id
        touching = sum(
            1
            for rel in setup.graph.relationships.values()
            if rel.subject_object_id == object_id or rel.object_object_id == object_id
        )
        discovered_degree = touching
    else:
        object_id, discovered_degree = _highest_degree_object(setup.graph)

    projection.parsed_revision_cache.clear()
    observer.observations.clear()
    cold_started = time.perf_counter()
    cold_result = retrieval.get_complete_object(request, object_id=object_id)
    cold_wall_ms = (time.perf_counter() - cold_started) * 1000.0
    cold_obs = observer.observations[-1]
    cold_project = observer.last_project()

    warm_samples_ms: list[float] = []
    warm_observations: list[dict[str, Any]] = []
    last_result = cold_result
    for _ in range(args.warm_runs):
        observer.observations.clear()
        started = time.perf_counter()
        last_result = retrieval.get_complete_object(request, object_id=object_id)
        warm_samples_ms.append((time.perf_counter() - started) * 1000.0)
        warm_observations.append(_observation_payload(observer.observations[-1]))

    head_after = bundle.world_graph.get_head(args.world_id)
    head_unchanged = (
        head_after is not None
        and head_after.head_revision_id == head_before.head_revision_id
        == EXPECTED_HEAD
    )
    warm_median_ms = sorted(warm_samples_ms)[len(warm_samples_ms) // 2]
    complete = (
        last_result.found
        and last_result.completeness.status == "complete"
        and last_result.coverage.truncated_fields == ()
    )
    if complete and head_unchanged and warm_median_ms < FAST_ENOUGH_WARM_MS:
        disposition = "COMPLETE_OBJECT_FAST_ENOUGH"
        exit_code = 0
    elif complete and head_unchanged:
        disposition = "COMPLETE_OBJECT_NEEDS_INDEX"
        exit_code = 3
    else:
        disposition = "COMPLETE_OBJECT_FAILED"
        exit_code = 2

    payload = {
        "lane": "complete-selected-object-one-hop",
        "world_id": args.world_id,
        "scope_mode": str(request.scope_mode),
        "admissibility": str(request.admissibility),
        "revision_id": last_result.snapshot.revision_id,
        "head_revision_id_before": head_before.head_revision_id,
        "head_revision_id_after": None if head_after is None else head_after.head_revision_id,
        "head_unchanged": head_unchanged,
        "selected_object_id": object_id,
        "discovered_touching_degree": discovered_degree,
        "found": last_result.found,
        "completeness": last_result.completeness.status,
        "completeness_reason": last_result.completeness.reason,
        "truncated_fields": list(last_result.coverage.truncated_fields),
        "returned_relationship_count": len(last_result.relationships),
        "returned_related_object_count": len(last_result.related_objects),
        "returned_assertion_count": len(last_result.property_assertions),
        "returned_anchor_count": len(last_result.anchors),
        "admitted_object_count": len(setup.graph.objects),
        "admitted_relationship_count": len(setup.graph.relationships),
        "admitted_evidence_count": len(setup.graph.evidence),
        "cold": {
            "wall_ms": round(cold_wall_ms, 3),
            "observation": _observation_payload(cold_obs),
            "project_observation": (
                None if cold_project is None else _observation_payload(cold_project)
            ),
        },
        "warm": {
            "runs": args.warm_runs,
            "samples_ms": [round(sample, 3) for sample in warm_samples_ms],
            "median_ms": round(warm_median_ms, 3),
            "observations": warm_observations,
        },
        "disposition": disposition,
        "identity_preflight": "ok",
        "receipt_schema": receipt.schema_version,
        "membership_digest": served,
        "expected_receipt_schema": EXPECTED_RECEIPT_SCHEMA,
        "expected_m0": EXPECTED_M0,
        "expected_m1": EXPECTED_M1,
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"selected_object_id: {object_id}")
    print(f"discovered_touching_degree: {discovered_degree}")
    print(
        "returned: "
        f"relationships={len(last_result.relationships)} "
        f"endpoints={len(last_result.related_objects)} "
        f"assertions={len(last_result.property_assertions)} "
        f"anchors={len(last_result.anchors)}"
    )
    print(
        "admitted_graph: "
        f"objects={len(setup.graph.objects)} "
        f"relationships={len(setup.graph.relationships)} "
        f"evidence={len(setup.graph.evidence)}"
    )
    print(
        f"completeness={last_result.completeness.status} "
        f"reason={last_result.completeness.reason!r} "
        f"truncated_fields={list(last_result.coverage.truncated_fields)}"
    )
    print(
        f"cold_ms={cold_wall_ms:.1f} warm_median_ms={warm_median_ms:.1f} "
        f"cold_cache={cold_obs.parsed_revision_cache_hit} "
        f"warm_cache={warm_observations[-1]['parsed_revision_cache_hit']}"
    )
    print(f"head_unchanged={head_unchanged}")
    print(f"disposition: {disposition}")
    print(f"wrote {args.output}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
