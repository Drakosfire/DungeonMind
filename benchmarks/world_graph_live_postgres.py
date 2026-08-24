#!/usr/bin/env python3
"""Local PostgreSQL witness for native World Graph reads (R.3a).

Measures DungeonMind projection + retrieval against a live authority store.
Private graph/source identity is never printed or written: stdout and the
optional JSON artifact carry counts, timings, cache hits, and repository
call counts only.

This is a characterization runner, not a CI gate. Identity preflight hashes
are the same public V4 Eldyrwild constants recorded in the R.3 Buddy witness.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from world_graph_reads import result_digest

from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.world_graph_observability import WorldGraphReadObservation
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

EXPECTED_RECEIPT_SCHEMA = "dm_existing_world_adoption_receipt_v4"
EXPECTED_M0 = "538195e399158bfb4fafce01f9c5af3c63e2137f70694fdead7a26e5800e0890"
EXPECTED_M1 = "16d3161d270691460ccbf6d183055ad9f29f00bdbecf5c26dfe0189da2b9914e"
EXPECTED_DA = "rev:34b1f8e2625d5ba693fc726a2a1a4720"
EXPECTED_HEAD = "rev:680c246047d67f9fe0293ee90526f670"

R3_DIRECT_PROJECTION_MEDIAN_MS = 20_739.0
OPTIMIZATION_FACTOR_TARGET = 5.0


class _CollectingObserver:
    def __init__(self) -> None:
        self.observations: list[WorldGraphReadObservation] = []

    def observe(self, observation: WorldGraphReadObservation) -> None:
        self.observations.append(observation)

    def last_project(self) -> WorldGraphReadObservation | None:
        for observation in reversed(self.observations):
            if observation.operation == "project":
                return observation
        return None


class _CountingSources:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.artifact_gets = 0
        self.revision_gets = 0
        self.snapshot_gets = 0

    def get_artifact(self, *args: Any, **kwargs: Any) -> Any:
        self.artifact_gets += 1
        return self._inner.get_artifact(*args, **kwargs)

    def get_revision(self, *args: Any, **kwargs: Any) -> Any:
        self.revision_gets += 1
        return self._inner.get_revision(*args, **kwargs)

    def get_provenance_snapshot(self, *args: Any, **kwargs: Any) -> Any:
        self.snapshot_gets += 1
        return self._inner.get_provenance_snapshot(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def snapshot(self) -> dict[str, int]:
        return {
            "get_artifact": self.artifact_gets,
            "get_revision": self.revision_gets,
            "get_provenance_snapshot": self.snapshot_gets,
        }


class _CountingWorldGraph:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.head_lookups = 0
        self.revision_loads = 0

    def get_head(self, *args: Any, **kwargs: Any) -> Any:
        self.head_lookups += 1
        return self._inner.get_head(*args, **kwargs)

    def get_revision(self, *args: Any, **kwargs: Any) -> Any:
        self.revision_loads += 1
        return self._inner.get_revision(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def snapshot(self) -> dict[str, int]:
        return {
            "get_head": self.head_lookups,
            "get_revision": self.revision_loads,
        }


class _CountingReader:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.parse_calls = 0

    def parse(self, **kwargs: Any) -> Any:
        self.parse_calls += 1
        return self._inner.parse(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@dataclass
class _CaseResult:
    name: str
    samples_ms: list[float] = field(default_factory=list)
    phases_ms: dict[str, list[float]] = field(default_factory=dict)
    cache_hits: list[bool] = field(default_factory=list)
    source_calls: list[dict[str, int]] = field(default_factory=list)
    graph_calls: list[dict[str, int]] = field(default_factory=list)
    parse_calls: list[int] = field(default_factory=list)
    source_artifact_count: int | None = None
    source_revision_count: int | None = None
    admitted: dict[str, int] | None = None
    digest: str | None = None
    outcome: str | None = None


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _phase_map(observation: WorldGraphReadObservation) -> dict[str, float]:
    return {
        item.phase: item.duration_seconds * 1000.0 for item in observation.phase_durations
    }


def _request(
    *,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
    scope_mode: ScopeModeV2,
    revision_pin: str | None = None,
) -> WorldGraphProjectionRequestV2:
    return WorldGraphProjectionRequestV2(
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
        scope_mode=scope_mode,
        revision_pin=revision_pin,
    )


def _summarize_case(case: _CaseResult) -> dict[str, Any]:
    phases = {
        phase: round(_median(samples), 3) for phase, samples in sorted(case.phases_ms.items())
    }
    return {
        "name": case.name,
        "runs": len(case.samples_ms),
        "median_ms": round(_median(case.samples_ms), 1),
        "min_ms": round(min(case.samples_ms), 1) if case.samples_ms else None,
        "max_ms": round(max(case.samples_ms), 1) if case.samples_ms else None,
        "samples_ms": [round(v, 1) for v in case.samples_ms],
        "phase_median_ms": phases,
        "parsed_revision_cache_hit": case.cache_hits,
        "source_calls": case.source_calls,
        "graph_calls": case.graph_calls,
        "parse_calls": case.parse_calls,
        "source_artifact_count": case.source_artifact_count,
        "source_revision_count": case.source_revision_count,
        "admitted": case.admitted,
        "digest": case.digest,
        "outcome": case.outcome,
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
    parser.add_argument("--campaign-a", default="longmont-c1")
    parser.add_argument("--campaign-b", default="longmont-c2")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("-o", "--output", default="/tmp/r3a-live-eldyrwild.json")
    args = parser.parse_args(argv)
    if not args.database_url:
        print("error: --database-url required", file=sys.stderr)
        return 2
    if args.runs < 1:
        print("error: --runs must be >= 1", file=sys.stderr)
        return 2

    bundle = PostgresRepositoryBundle(PostgresDatabase(args.database_url))
    receipt = bundle.existing_world_adoptions.get_for_world(args.world_id)
    head = bundle.world_graph.get_head(args.world_id)
    if receipt is None or head is None:
        print("error: missing adoption receipt or graph head", file=sys.stderr)
        return 2

    served = getattr(receipt, "effective_membership_sha256", None) or receipt.membership_sha256
    failures: list[str] = []
    if receipt.schema_version != EXPECTED_RECEIPT_SCHEMA:
        failures.append(f"receipt schema {receipt.schema_version!r}")
    if receipt.published_revision_id != EXPECTED_DA:
        failures.append("D_A mismatch")
    if head.head_revision_id != EXPECTED_HEAD:
        failures.append("head mismatch")
    if receipt.membership_sha256 != EXPECTED_M0:
        failures.append("M0 mismatch")
    if served != EXPECTED_M1:
        failures.append("M1 mismatch")
    if failures:
        print("error: identity preflight failed:", *failures, sep="\n  ", file=sys.stderr)
        return 2

    print("identity preflight: ok")
    print(f"  receipt: {receipt.schema_version}")
    print("  D_A / head: match expected V4 Eldyrwild pins")
    print("  M0 / M1: match expected V4 membership digests")

    observer = _CollectingObserver()
    sources = _CountingSources(bundle.sources)
    world_graph = _CountingWorldGraph(bundle.world_graph)
    reader = _CountingReader(
        VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
        )
    )
    projection = WorldGraphProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=reader,
        read_observer=observer,
    )
    retrieval = WorldGraphRetrievalService(
        projection=projection,
        sources=sources,
        read_observer=observer,
    )

    gm_c1 = _request(
        world_id=args.world_id,
        campaign_id=args.campaign_a,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.CAMPAIGN,
    )
    gm_c1_head_pin = _request(
        world_id=args.world_id,
        campaign_id=args.campaign_a,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.CAMPAIGN,
        revision_pin=EXPECTED_HEAD,
    )
    gm_c1_historical = _request(
        world_id=args.world_id,
        campaign_id=args.campaign_a,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.CAMPAIGN,
        revision_pin=EXPECTED_DA,
    )
    player_c1 = _request(
        world_id=args.world_id,
        campaign_id=args.campaign_a,
        admissibility=Admissibility.PLAYER,
        scope_mode=ScopeModeV2.CAMPAIGN,
    )
    gm_world = _request(
        world_id=args.world_id,
        campaign_id=None,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD,
    )

    # Discover seeds from one untimed projection. Object IDs never leave this process.
    setup = projection.project(gm_c1)
    seed_object = next(iter(setup.graph.objects), None)
    seed_rel = next(iter(setup.graph.relationships), None)
    if seed_object is None:
        print("error: projected graph has no admitted objects", file=sys.stderr)
        return 2
    label_words = [
        word.casefold()
        for word in (setup.graph.objects[seed_object].label or "").split()
        if len(word) >= 4
    ]
    query_text = label_words[0] if label_words else "keep"
    lookup = retrieval.get_object(gm_c1, object_id=seed_object)
    anchor_id = max((anchor.anchor_id for anchor in lookup.anchors), default="")

    def run_case(name: str, call: Callable[[], Any], *, runs: int | None = None) -> _CaseResult:
        case = _CaseResult(name=name)
        for _ in range(args.runs if runs is None else runs):
            sources_before = sources.snapshot()
            graph_before = world_graph.snapshot()
            parse_before = reader.parse_calls
            observer.observations.clear()
            started = time.perf_counter()
            result = call()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            case.samples_ms.append(elapsed_ms)
            digest = result_digest(result)
            if case.digest is None:
                case.digest = digest
            elif case.digest != digest:
                raise SystemExit(f"digest drift in {name}: semantic result changed across runs")
            project_obs = observer.last_project()
            if project_obs is not None:
                for phase, ms in _phase_map(project_obs).items():
                    case.phases_ms.setdefault(phase, []).append(ms)
                if project_obs.parsed_revision_cache_hit is not None:
                    case.cache_hits.append(project_obs.parsed_revision_cache_hit)
                if case.source_artifact_count is None:
                    case.source_artifact_count = project_obs.source_artifact_count
                    case.source_revision_count = project_obs.source_revision_count
                    case.admitted = {
                        "objects": project_obs.admitted_object_count or 0,
                        "relationships": project_obs.admitted_relationship_count or 0,
                        "evidence": project_obs.admitted_evidence_count or 0,
                    }
            outer = observer.observations[-1] if observer.observations else None
            if outer is not None:
                case.outcome = outer.outcome
            after_s = sources.snapshot()
            after_g = world_graph.snapshot()
            case.source_calls.append(
                {key: after_s[key] - sources_before[key] for key in after_s}
            )
            case.graph_calls.append(
                {key: after_g[key] - graph_before[key] for key in after_g}
            )
            case.parse_calls.append(reader.parse_calls - parse_before)
        return case

    print("characterizing cold/warm parse on campaign GM head…")
    projection.parsed_revision_cache.clear()
    cold = run_case(
        "projection:campaign-gm:cold", lambda: projection.project(gm_c1), runs=1
    )
    warm = run_case("projection:campaign-gm:warm", lambda: projection.project(gm_c1))
    pin_head = run_case(
        "projection:campaign-gm:pin-head", lambda: projection.project(gm_c1_head_pin)
    )
    pin_da = run_case(
        "projection:campaign-gm:pin-DA", lambda: projection.project(gm_c1_historical)
    )
    after_da = run_case(
        "projection:campaign-gm:head-after-historical",
        lambda: projection.project(gm_c1),
    )

    cases = [
        cold,
        warm,
        pin_head,
        pin_da,
        after_da,
        run_case("projection:world-gm", lambda: projection.project(gm_world)),
        run_case("projection:campaign-player", lambda: projection.project(player_c1)),
        run_case("object:hit", lambda: retrieval.get_object(gm_c1, object_id=seed_object)),
        run_case("search", lambda: retrieval.search(gm_c1, query_text=query_text)),
        run_case(
            "neighborhood:depth-1",
            lambda: retrieval.get_neighborhood(gm_c1, seed_object_ids=[seed_object], depth=1),
        ),
        run_case(
            "neighborhood:depth-2",
            lambda: retrieval.get_neighborhood(gm_c1, seed_object_ids=[seed_object], depth=2),
        ),
        run_case(
            "evidence:object",
            lambda: retrieval.get_evidence(
                gm_c1, target=EvidenceTarget(kind="object", target_id=seed_object)
            ),
        ),
    ]
    if seed_rel is not None:
        cases.append(
            run_case(
                "evidence:relationship",
                lambda: retrieval.get_evidence(
                    gm_c1, target=EvidenceTarget(kind="relationship", target_id=seed_rel)
                ),
            )
        )
    if anchor_id:
        cases.append(
            run_case(
                "resolve_source_anchor",
                lambda: retrieval.resolve_source_anchor(gm_c1, anchor_id=anchor_id),
            )
        )

    summaries = [_summarize_case(case) for case in cases]
    warm_projection_ms = _median(warm.samples_ms)
    factor = (
        R3_DIRECT_PROJECTION_MEDIAN_MS / warm_projection_ms if warm_projection_ms else 0.0
    )
    optimized = factor >= OPTIMIZATION_FACTOR_TARGET
    disposition = "R3A_OPTIMIZED" if optimized else "R3A_NOT_OPTIMIZED"

    payload = {
        "lane": "r3a",
        "world_id": args.world_id,
        "runs": args.runs,
        "identity_preflight": "ok",
        "r3_direct_projection_median_ms": R3_DIRECT_PROJECTION_MEDIAN_MS,
        "r3a_warm_projection_median_ms": round(warm_projection_ms, 1),
        "speedup_vs_r3_direct": round(factor, 2),
        "disposition": disposition,
        "switch_ready": "SWITCH_NOT_READY",
        "cases": summaries,
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print()
    print(f"{'case':<42} {'median_ms':>10}  cache  snapshot  parse")
    for summary in summaries:
        cache = summary["parsed_revision_cache_hit"]
        cache_s = (
            "hit" if cache and all(cache) else ("miss" if cache and not any(cache) else str(cache))
        )
        if summary["source_calls"]:
            snap = summary["source_calls"][-1]["get_provenance_snapshot"]
        else:
            snap = "?"
        parse = summary["parse_calls"][-1] if summary["parse_calls"] else "?"
        print(
            f"{summary['name']:<42} {summary['median_ms']:>10.1f}  {cache_s:<6} {snap!s:<9} {parse}"
        )
        phases = summary["phase_median_ms"]
        if phases:
            rendered = "  ".join(f"{name}={ms:.1f}ms" for name, ms in phases.items())
            print(f"  phases: {rendered}")

    print()
    print(f"warm campaign GM projection median: {warm_projection_ms:.1f} ms")
    print(
        f"vs R.3 direct {R3_DIRECT_PROJECTION_MEDIAN_MS:.0f} ms -> {factor:.2f}x "
        f"(target >= {OPTIMIZATION_FACTOR_TARGET:.0f}x)"
    )
    print(f"disposition: {disposition}")
    print("switch: SWITCH_NOT_READY (gate remains default-off; successor Buddy pin+witness)")
    print(f"wrote {args.output}")
    last_source = warm.source_calls[-1]
    print(
        "N+1 check (warm projection last run): "
        f"get_artifact={last_source['get_artifact']} "
        f"get_revision={last_source['get_revision']} "
        f"get_provenance_snapshot={last_source['get_provenance_snapshot']}"
    )
    return 0 if optimized else 1


if __name__ == "__main__":
    sys.exit(main())
