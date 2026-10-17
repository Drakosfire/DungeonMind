"""CE-02: compare classic parse-cache lifetimes using deterministic memory fixtures.

No PostgreSQL, Buddy runtime, provider or retained knowledge is accessed. Each
sample constructs fresh operation services; only the injected immutable parse
cache differs. Counter-instrumented timing is observational. Profile timings
are recorded separately and must not be compared with ordinary samples.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import platform
import resource
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pydantic
from benchmarks.world_graph_reads import (
    GENERATOR_SEED,
    NOW,
    WORLD_ID,
    _git_commit,
    _seed_sources,
    _semantic_normalize,
    generate_payload,
    result_digest,
)

from dungeonmind.application import parsed_revision_cache as cache_module
from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.parsed_revision_cache import ParsedImmutableRevisionCache
from dungeonmind.application.world_graph_observability import WorldGraphReadObservation
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor


@dataclass
class Fixture:
    graph: InMemoryWorldGraphRepository
    sources: InMemorySourceRepository
    initializations: InMemoryReviewedWorldInitializationRepository
    request: WorldGraphProjectionRequestV2
    target: str
    metadata: dict[str, Any]


def build_fixture(size: int) -> Fixture:
    if size < 5:
        raise ValueError("size must be at least 5")
    payload, metadata = generate_payload(object_count=size, seed=GENERATOR_SEED)
    graph = InMemoryWorldGraphRepository()
    revision = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:ce02"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=NOW,
        )
    )
    sources = _seed_sources()
    metadata.update(
        payload_sha256=canonical_sha256(payload),
        payload_json_bytes=len(json.dumps(payload, separators=(",", ":")).encode()),
    )
    return Fixture(
        graph,
        sources,
        InMemoryReviewedWorldInitializationRepository(
            graph,
            sources,
            InMemoryContributionRepository(),
        ),
        WorldGraphProjectionRequestV2(
            world_id=WORLD_ID,
            admissibility=Admissibility.GM,
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            revision_pin=revision.revision_id,
        ),
        f"obj:{size - 1 - ((size - 1 - 3) % 7):06d}",
        metadata,
    )


class CountedPort:
    def __init__(self, inner: Any, counts: Counter[str], prefix: str) -> None:
        self.inner, self.counts, self.prefix = inner, counts, prefix

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.inner, name)
        if name not in {
            "get_head",
            "get_revision",
            "get_provenance_snapshot",
            "parse",
            "get_for_world",
        }:
            return value

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.counts[f"{self.prefix}.{name}"] += 1
            return value(*args, **kwargs)

        return counted


class Observer:
    def __init__(self) -> None:
        self.observations: list[WorldGraphReadObservation] = []

    def observe(self, observation: WorldGraphReadObservation) -> None:
        self.observations.append(observation)


def _rss_bytes() -> int | None:
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def measure(
    fixture: Fixture,
    cache: ParsedImmutableRevisionCache,
    *,
    profile: bool = False,
) -> tuple[dict[str, Any], Any]:
    counts: Counter[str] = Counter()
    observer = Observer()
    isolate = cache_module.isolate_parsed_graph

    def counted_copy(snapshot: Any) -> Any:
        counts["cache.isolated_snapshots"] += 1
        counts["cache.copied_objects"] += len(snapshot.objects)
        counts["cache.copied_relationships"] += len(snapshot.relationships)
        counts["cache.copied_evidence"] += len(snapshot.evidence)
        return isolate(snapshot)

    profiler = cProfile.Profile() if profile else None
    if profile:
        tracemalloc.start()
        assert profiler is not None
        profiler.enable()
    rss_before = _rss_bytes()
    start_cpu, start_wall = time.process_time_ns(), time.perf_counter_ns()
    with patch.object(cache_module, "isolate_parsed_graph", counted_copy):
        sources = CountedPort(fixture.sources, counts, "sources")
        reader = CountedPort(
            VersionedUnionGraphSnapshotReader(
                profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()]),
            ),
            counts,
            "reader",
        )
        projection = WorldGraphProjectionService(
            world_graph=CountedPort(fixture.graph, counts, "graph"),
            sources=sources,
            graph_reader=reader,
            reviewed_world_initializations=CountedPort(
                fixture.initializations,
                counts,
                "initializations",
            ),
            parsed_revision_cache=cache,
            read_observer=observer,
        )
        retrieval = WorldGraphRetrievalService(
            projection=projection,
            sources=sources,
            read_observer=observer,
        )
        result = retrieval.get_object(fixture.request, object_id=fixture.target)
    elapsed_ns, cpu_ns = time.perf_counter_ns() - start_wall, time.process_time_ns() - start_cpu
    allocation_peak = None
    if profile:
        assert profiler is not None
        profiler.disable()
        _, allocation_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    start_serialization = time.perf_counter_ns()
    output = json.dumps(_semantic_normalize(result), separators=(",", ":")).encode()
    serialization_ns = time.perf_counter_ns() - start_serialization
    projection_observation = next(o for o in observer.observations if o.operation == "project")
    return {
        "wall_ms": elapsed_ns / 1e6,
        "cpu_ms": cpu_ns / 1e6,
        "counts": dict(counts),
        "semantic_sha256": result_digest(result),
        "output_json_bytes": len(output),
        "serialization_ms": serialization_ns / 1e6,
        "rss_before_bytes": rss_before,
        "rss_after_bytes": _rss_bytes(),
        "process_high_water_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        * (1 if sys.platform == "darwin" else 1024),
        "traced_peak_bytes": allocation_peak,
        "profile_call_count": None
        if profiler is None
        else sum(stat.callcount for stat in profiler.getstats()),
        "cache_hit": projection_observation.parsed_revision_cache_hit,
        "projection_phases_ms": {
            phase.phase: phase.duration_seconds * 1000
            for phase in projection_observation.phase_durations
        },
    }, result


def run_experiment(sizes: list[int], repeats: int, *, profile: bool = False) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("repeats must be at least 2 to distinguish first and repeated cache reads")
    begin_ref = _git_commit()
    cells = []
    for size in sizes:
        fixture = build_fixture(size)
        shared = ParsedImmutableRevisionCache()
        samples: dict[str, list[dict[str, Any]]] = {"factory_local": [], "shared_parse": []}
        order = []
        for repetition in range(repeats):
            modes = ["factory_local", "shared_parse"]
            if repetition % 2:
                modes.reverse()
            for mode in modes:
                cache = shared if mode == "shared_parse" else ParsedImmutableRevisionCache()
                sample, _ = measure(fixture, cache, profile=profile)
                samples[mode].append(sample)
                order.append(mode)
        digests = {sample["semantic_sha256"] for group in samples.values() for sample in group}
        if len(digests) != 1:
            raise ValueError(f"semantic parity failed at size {size}")
        summaries = {}
        for mode, group in samples.items():
            counts = Counter()
            for sample in group:
                counts.update(sample["counts"])
            summaries[mode] = {
                "first_wall_ms": group[0]["wall_ms"],
                "repeated_median_wall_ms": statistics.median(s["wall_ms"] for s in group[1:]),
                "total_work": dict(counts),
            }
        cells.append(
            {
                "size": size,
                "fixture": fixture.metadata,
                "order": order,
                "semantic_sha256": digests.pop(),
                "samples": samples,
                "summary": summaries,
            }
        )
    return {
        "schema": "dm_classic_read_lifetime_experiment_v1",
        "begin_ref": begin_ref,
        "end_ref": _git_commit(),
        "python": sys.version,
        "executable": sys.executable,
        "pydantic": pydantic.__version__,
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "profile": profile,
        "timing_kind": "profiled" if profile else "counter_instrumented",
        "conditions": (
            "memory repositories; ready process; first cache read separate; alternating modes"
        ),
        "load_average": os.getloadavg(),
        "connections": None,
        "sql_statements": None,
        "not_measured": [
            "PostgreSQL/connect/fetch/decode",
            "Buddy binding and factory",
            "reviewed initialization D0",
            "model/provider",
            "true cold OS/DB",
            "cross-database cache namespace",
        ],
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; use a fresh evidence path")
    report = run_experiment(args.sizes, args.repeats, profile=args.profile)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for cell in report["cells"]:
        print(json.dumps({"size": cell["size"], "summary": cell["summary"]}))


if __name__ == "__main__":
    main()
