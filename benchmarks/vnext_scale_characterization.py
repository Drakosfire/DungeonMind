"""Sequential, bounded in-memory characterization for the accepted vNext lane."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.vnext_scale_fixtures import GENERATOR_VERSION, SEED, WORLD_ID, make_payload
from benchmarks.world_graph_reads import _seed_sources, result_digest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
from dungeonmind.application.vnext.materialization import (
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    materialize_governed_revision,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import EvidenceTarget, WorldGraphRetrievalService
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeEntity,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    Entity,
    SemanticProfileDescriptorV2,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

MAIN_ANCHOR = "ccd06cb119c834a3d7950d5109b85c7b6a683430"
RUNTIME_ANCHOR = "7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc"
SIZES = (100, 1_000, 10_000, 50_000, 100_000)
OPERATIONS = (
    "cold_parse",
    "full_projection",
    "exact_entity",
    "complete_entity",
    "neighborhood_d1",
    "neighborhood_d2",
    "evidence",
    "source_anchor",
    "deterministic_search",
    "source_snapshot",
    "tiny_delta_publication",
    "canonical_serialize_hash",
)
NOW = datetime(2026, 9, 28, tzinfo=UTC)


def _digest(value: Any) -> str:
    return result_digest(value)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], check=True, text=True, capture_output=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def _hard_memory_limit_bytes() -> int | None:
    """Return the active cgroup v2 hard limit, if the process can read one."""
    try:
        entry = next(
            line
            for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
        group = entry.split("::", 1)[1].lstrip("/")
        value = Path("/sys/fs/cgroup", group, "memory.max").read_text().strip()
        return None if value == "max" else int(value)
    except (OSError, StopIteration, ValueError):
        return None


def _setup(shape: str, size: int) -> dict[str, Any]:
    payload, params = make_payload(shape=shape, size=size)
    # Independent fixture truth: counts, IDs, and hand-authored labels do not
    # come from any operation timed below.
    expected_objects = size
    expected_relationships = size + size // 2
    expected_evidence = size + expected_relationships
    assert len(payload["objects"]) == expected_objects
    assert len(payload["relationships"]) == expected_relationships
    assert len(payload["evidence_refs"]) == expected_evidence
    assert payload["objects"][0]["object_id"] == "obj:000000"
    assert payload["objects"][-1]["label"] == f"Hold {size - 1:05d}"
    assert payload["evidence_refs"][0]["evidence_ref_id"] == "ev:o:000000"

    world_graph = InMemoryWorldGraphRepository()
    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=[f"op:scale:{shape}:{size}"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=NOW,
        )
    )
    sources = _seed_sources()
    descriptor = load_builtin_v3_descriptor()
    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    projection = WorldGraphProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=reader,
        reviewed_world_initializations=InMemoryReviewedWorldInitializationRepository(
            world_graph, sources, InMemoryContributionRepository()
        ),
    )
    retrieval = WorldGraphRetrievalService(projection=projection, sources=sources)
    request = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
    )
    player = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id="camp:alpha",
        admissibility=Admissibility.PLAYER,
        scope_mode=ScopeModeV2.CAMPAIGN,
    )
    target = f"obj:{size - 1:06d}"
    # Semantic preflight: exact identity and a hand-built visibility exclusion.
    exact = retrieval.get_object(request, object_id=target)
    assert exact.found and exact.object.object_id == target
    excluded = retrieval.get_object(player, object_id="obj:000003")
    assert not excluded.found  # fixture index 3 is GM-only and scope-independent
    search = retrieval.search(request, query_text=f"Hold {size - 1:05d}")
    assert any(item.object_id == target for item in search.objects)
    evidence = retrieval.get_evidence(
        request, target=EvidenceTarget(kind="object", target_id=target)
    )
    assert evidence.found and evidence.target.target_id == target
    complete = retrieval.get_complete_object(request, object_id=target)
    assert complete.found and complete.object.object_id == target
    if not complete.anchors:
        raise AssertionError("semantic preflight expected source-linked anchors")
    anchor_id = complete.anchors[-1].anchor_id

    source_ids = {row["source_artifact_id"] for row in payload["evidence_refs"]}
    revision_ids = {row["source_revision_id"] for row in payload["evidence_refs"]}
    source_repo = sources
    cases: dict[str, Callable[[], Any]] = {
        "cold_parse": lambda: reader.parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload),
        "full_projection": lambda: projection.project(request),
        "exact_entity": lambda: retrieval.get_object(request, object_id=target),
        "complete_entity": lambda: retrieval.get_complete_object(request, object_id=target),
        "neighborhood_d1": lambda: retrieval.get_neighborhood(
            request, seed_object_ids=["obj:000000"], depth=1
        ),
        "neighborhood_d2": lambda: retrieval.get_neighborhood(
            request, seed_object_ids=["obj:000000"], depth=2
        ),
        "evidence": lambda: retrieval.get_evidence(
            request, target=EvidenceTarget(kind="object", target_id=target)
        ),
        "source_anchor": lambda: retrieval.resolve_source_anchor(request, anchor_id=anchor_id),
        "deterministic_search": lambda: retrieval.search(request, query_text="hold"),
        "source_snapshot": lambda: (
            lambda snapshot: (
                snapshot.fingerprint,
                snapshot.artifact_count,
                snapshot.revision_count,
                snapshot.missing_artifact_count,
                snapshot.missing_revision_count,
            )
        )(
            source_repo.get_provenance_snapshot(
                artifact_ids=sorted(source_ids), revision_ids=sorted(revision_ids)
            )
        ),
        "tiny_delta_publication": None,
        "canonical_serialize_hash": lambda: _digest(payload),
    }
    return {
        "payload": payload,
        "params": params,
        "cases": cases,
        "input_sha256": _digest(payload),
        "world_graph": world_graph,
        "revision_id": published.revision_id,
        "fixture_counts": {
            "objects": expected_objects,
            "relationships": expected_relationships,
            "evidence_refs": expected_evidence,
        },
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _measure(call: Callable[[], Any], repeats: int) -> dict[str, Any]:
    # The independent fixture/query oracle ran before the case in _setup.
    # Derive semantic identity after each timed call (outside the timer), then
    # require every measured/memory result to agree with the same digest.
    samples: list[float] = []
    digest: str | None = None
    for _ in range(repeats):
        gc.collect()
        started = time.perf_counter()
        result = call()
        samples.append(time.perf_counter() - started)
        observed_digest = _digest(result)
        if digest is not None and observed_digest != digest:
            raise RuntimeError("repeated semantic output digest mismatch")
        digest = observed_digest
    gc.collect()
    tracemalloc.start()
    memory_result = call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_digest = _digest(memory_result)
    if digest is not None and memory_digest != digest:
        raise RuntimeError("memory-observation semantic digest mismatch")
    digest = memory_digest
    return {
        "result_sha256": digest,
        "samples_seconds": samples,
        "median_seconds": statistics.median(samples),
        "peak_tracemalloc_bytes": peak,
    }


def _tiny_delta_state(*, shape: str, size: int) -> dict[str, Any]:
    """Build and durably publish an N-entity native parent outside timing."""
    repo = InMemoryKnowledgeRevisionRepository()
    space_id = f"space:scale:{shape}:{size}"
    domain = DomainContractDescriptor(
        domain_id="benchmark.generic",
        domain_revision="1",
        admission_policy_id="benchmark.generic.accepted",
    )
    profile = SemanticProfileDescriptorV2(
        profile_id="benchmark.profile",
        profile_revision="1",
        term_namespaces=["benchmark"],
    )
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id=space_id,
        initialization_id=f"init:{shape}:{size}",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    stored_genesis = repo.get_revision(space_id, genesis.published_revision_id)
    assert stored_genesis is not None
    parent = build_parsed_knowledge_revision(
        revision=stored_genesis.revision,
        decoded_content=decode_native_graph_payload(stored_genesis.graph_payload),
    )
    items = [
        ProposeEntity(item_id=f"bulk:{i:06d}", entity=Entity(entity_id=f"ent:{i:06d}"))
        for i in range(size)
    ]
    contribution = KnowledgeContribution(
        contribution_id=f"contrib:bulk:{shape}:{size}",
        space_id=space_id,
        producer="benchmark:scale",
        produced_at=NOW,
        status="finalized",
        items=items,
    )
    dispositions = [
        ContributionDisposition(item_id=item.item_id, disposition="accepted") for item in items
    ]
    bulk = materialize_governed_revision(
        parent=parent,
        contribution=contribution,
        dispositions=dispositions,
        publication=GovernedPublicationIdentity(
            operation_ids=(f"op:bulk:{shape}:{size}",),
            created_at=NOW,
            expected_parent_revision_id=genesis.published_revision_id,
        ),
        domain_contract=domain,
        semantic_profile=profile,
    )
    bulk_receipt = publish_governed_materialization(
        bulk, repository=repo, publication_id=f"pub:bulk:{shape}:{size}"
    )
    stored_parent = repo.get_revision(space_id, bulk_receipt.published_revision_id)
    assert stored_parent is not None
    parsed_parent = build_parsed_knowledge_revision(
        revision=stored_parent.revision,
        decoded_content=decode_native_graph_payload(stored_parent.graph_payload),
    )
    assert len(parsed_parent.entities_by_id) == size
    return {
        "repo": repo,
        "parent": parsed_parent,
        "domain": domain,
        "profile": profile,
        "sequence": 0,
        "entity_count": size,
    }


def _publish_one_tiny_delta(state: dict[str, Any]) -> tuple[Any, int]:
    parent = state["parent"]
    sequence = state["sequence"]
    item_id = f"tiny:item:{sequence:02d}"
    contribution = KnowledgeContribution(
        contribution_id=f"tiny:contribution:{sequence:02d}",
        space_id=parent.space_id,
        producer="benchmark:tiny-delta",
        produced_at=NOW,
        status="finalized",
        items=[ProposeEntity(item_id=item_id, entity=Entity(entity_id=f"ent:tiny:{sequence:02d}"))],
    )
    materialized = materialize_governed_revision(
        parent=parent,
        contribution=contribution,
        dispositions=[ContributionDisposition(item_id=item_id, disposition="accepted")],
        publication=GovernedPublicationIdentity(
            operation_ids=(f"tiny:operation:{sequence:02d}",),
            created_at=NOW,
            expected_parent_revision_id=parent.revision_id,
        ),
        domain_contract=state["domain"],
        semantic_profile=state["profile"],
    )
    receipt = publish_governed_materialization(
        materialized, repository=state["repo"], publication_id=f"tiny:publication:{sequence:02d}"
    )
    stored = state["repo"].get_revision(parent.space_id, receipt.published_revision_id)
    assert stored is not None
    state["parent"] = build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )
    state["sequence"] += 1
    return receipt, len(parent.entities_by_id)


def _measure_tiny_delta(state: dict[str, Any], input_sha256: str, repeats: int) -> dict[str, Any]:
    samples: list[float] = []
    receipt_digests: list[str] = []
    parent_counts: list[int] = []
    for _ in range(repeats):
        started = time.perf_counter()
        receipt, parent_count = _publish_one_tiny_delta(state)
        samples.append(time.perf_counter() - started)
        parent_counts.append(parent_count)
        receipt_digests.append(_digest(receipt))

    gc.collect()
    tracemalloc.start()
    memory_sample, memory_parent_count = _publish_one_tiny_delta(state)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    receipt_digests.append(_digest(memory_sample))
    return {
        "input_sha256": input_sha256,
        "result_sha256": _digest(receipt_digests),
        "publication_receipt_sha256_samples": receipt_digests,
        "samples_seconds": samples,
        "median_seconds": statistics.median(samples),
        "peak_tracemalloc_bytes": peak,
        "parent_entity_counts_before_samples": parent_counts,
        "memory_sample_parent_entity_count": memory_parent_count,
        "delta_entities_per_sample": 1,
    }


def run(sizes: tuple[int, ...], output: Path, repeats: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_shapes = ("world_like", "rules_like")
    stop_after_memory = False
    for shape_index, shape in enumerate(all_shapes):
        if stop_after_memory:
            break
        for size_index, size in enumerate(SIZES):
            if size not in sizes:
                # The checked-in matrix remains exhaustive even for a narrowed
                # diagnostic run; unselected sizes are explicitly not attempted.
                for operation in OPERATIONS:
                    rows.append(
                        {
                            "shape": shape,
                            "size": size,
                            "operation": operation,
                            "adapter": "memory",
                            "api_family": "classic_v6_world_graph",
                            "disposition": "not_measured",
                            "reason": (
                                "Not attempted: this host has no enforceable 8 GiB peak-RSS limit; "
                                "PR #91 activation prohibits 50k/100k until "
                                "revised activation/waiver."
                            )
                            if size > 10_000
                            else (
                                "Size omitted from this diagnostic invocation; "
                                "not an accepted full run."
                            ),
                        }
                    )
                continue
            print(f"SETUP {shape} {size}", flush=True)
            try:
                env = _setup(shape, size)
            except MemoryError:
                stop_after_memory = True
                for remaining_shape in all_shapes[shape_index:]:
                    start_size = size_index if remaining_shape == shape else 0
                    for remaining_size in SIZES[start_size:]:
                        for operation in OPERATIONS:
                            rows.append(
                                {
                                    "shape": remaining_shape,
                                    "size": remaining_size,
                                    "operation": operation,
                                    "adapter": "memory",
                                    "api_family": "classic_v6_world_graph",
                                    "disposition": "resource_limited",
                                    "reason": (
                                        "Fixture setup raised MemoryError under enforced "
                                        "8 GiB virtual-memory ceiling."
                                    ),
                                    "elapsed_seconds": 0,
                                }
                            )
                break
            for operation in OPERATIONS:
                required_large = operation in {
                    "full_projection",
                    "exact_entity",
                    "complete_entity",
                    "neighborhood_d1",
                    "neighborhood_d2",
                    "evidence",
                    "source_anchor",
                    "deterministic_search",
                }
                required_size = size <= 10_000 or required_large
                row = {
                    "shape": shape,
                    "size": size,
                    "operation": operation,
                    "adapter": "memory",
                    "api_family": (
                        "native_vnext"
                        if operation == "tiny_delta_publication"
                        else "classic_v6_world_graph"
                    ),
                    "input_sha256": env["input_sha256"],
                    "fixture_counts": env["fixture_counts"],
                    "result_contract": f"DungeonMind current public API: {operation}",
                    "disposition": "measured" if required_size else "not_measured",
                }
                if required_size:
                    count = repeats if size <= 1_000 else 1
                    print(f"MEASURE {shape} {size} {operation}", flush=True)
                    try:
                        if operation == "tiny_delta_publication":
                            tiny_state = _tiny_delta_state(shape=shape, size=size)
                            tiny_input = _digest(
                                {
                                    "shape": shape,
                                    "parent_entity_count": size,
                                    "parent_entity_ids_sha256": _digest(
                                        [f"ent:{i:06d}" for i in range(size)]
                                    ),
                                    "delta_entity_count_per_sample": 1,
                                }
                            )
                            row.update(_measure_tiny_delta(tiny_state, tiny_input, count))
                            row["fixture_counts"] = {"native_parent_entities": size}
                            row["result_contract"] = (
                                "materialize_governed_revision + publish_governed_materialization"
                            )
                        else:
                            row.update(_measure(env["cases"][operation], count))
                    except MemoryError:
                        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        row.update(
                            {
                                "disposition": "resource_limited",
                                "reason": (
                                    "Measurement/preflight raised MemoryError under enforced "
                                    "8 GiB virtual-memory ceiling."
                                ),
                                "peak_rss_observed_kib": usage,
                                "input_sha256": env["input_sha256"],
                            }
                        )
                else:
                    row["reason"] = (
                        "Beyond activated large-scale core-operation cohort; no waiver supplied."
                    )
                rows.append(row)
            del env
            gc.collect()
    # PG cells are expressly inactive; preserve explicit dispositions.
    for shape in ("world_like", "rules_like"):
        for size in SIZES:
            for operation in OPERATIONS:
                rows.append(
                    {
                        "shape": shape,
                        "size": size,
                        "operation": operation,
                        "adapter": "postgresql",
                        "api_family": "inactive_postgresql",
                        "disposition": "not_measured",
                        "reason": "No PostgreSQL target authorized by PR #91 activation.",
                    }
                )
    document = {
        "schema": "dungeonmind.vnext-scale-characterization.v1",
        "acceptance_status": "PARTIAL_MEMORY_BASELINE_THROUGH_10K_PENDING_PRIME_REVIEW",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "main_anchor": MAIN_ANCHOR,
        "runtime_anchor": RUNTIME_ANCHOR,
        "measured_checkout_head": _git("rev-parse", "HEAD"),
        "generator_version": GENERATOR_VERSION,
        "seed": SEED,
        "workload_parameters": {
            "sizes": list(sizes),
            "shapes": ["world_like", "rules_like"],
            "sequential": True,
            "repeat_count_100_1000": repeats,
            "repeat_count_10000": 1,
            "repeat_count_50k_100k": 1,
        },
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "command": " ".join(sys.argv),
        },
        "postgresql": {
            "activated": False,
            "disposition": "not_measured",
            "reason": "No PostgreSQL target authorized by PR #91 activation.",
        },
        "resource_envelope": {
            "wall_time_limit_seconds": 5400,
            "peak_rss_limit_bytes": 8589934592,
            "execution": "sequential",
            "host_enforcement": {
                "timeout_seconds": 5400,
                "virtual_address_space_ulimit_bytes": 8589934592,
                "peak_rss_cgroup_hard_limit_bytes": _hard_memory_limit_bytes(),
                "peak_rss_enforced": (
                    _hard_memory_limit_bytes() is not None
                    and _hard_memory_limit_bytes() <= 8589934592
                ),
            },
        },
        "matrix": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    report = [
        "# vNext scale characterization — partial memory baseline through 10k",
        "",
        f"Main anchor: `{MAIN_ANCHOR}`",
        "",
        f"Measured runtime anchor: `{RUNTIME_ANCHOR}`",
        "",
        f"Measurement checkout: `{document['measured_checkout_head']}`",
        "",
        (
            "This report records synthetic World-like and Rules-like stress shapes. "
            "Eleven measured "
            "operations use the classic V6 World Graph projection/retrieval API family; only "
            "tiny-delta publication uses native vNext. These classic timings are not claims about "
            "native-vNext entity/evidence/search performance. Rules-like is a workload shape "
            "only; it "
            "does not assert Rules domain semantics. No production/user data, PostgreSQL "
            "target, provider, or external service was used."
        ),
        "",
        (
            f"Environment: {platform.platform()}, {platform.machine()}, "
            f"{platform.python_implementation()} {platform.python_version()}, "
            f"{os.cpu_count()} logical CPUs."
        ),
        "",
        (
            "The activation is sequential and bounded to 90 minutes and 8 GiB peak RSS. "
            "A virtual-address-space ulimit is recorded separately and is not misrepresented "
            "as an RSS limit. Timing and tracemalloc peaks are machine-dependent observations; "
            "digests/counts are deterministic identity. No aggregate score or universal latency "
            "threshold is claimed."
        ),
        "",
        "## Measurement matrix",
        "",
        (
            "| Shape | Size | Operation | API family | Adapter | Disposition | Median seconds | "
            "Peak traced bytes | Result digest | Reason |"
        ),
        "|---|---:|---|---|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        samples = row.get("samples_seconds", [])
        median = f"{statistics.median(samples):.6g}" if samples else "—"
        peak = str(row.get("peak_tracemalloc_bytes", "—"))
        digest = f"`{row['result_sha256'][:12]}…`" if row.get("result_sha256") else "—"
        reason = row.get("reason", "").replace("|", "\\|")
        report.append(
            f"| {row['shape']} | {row['size']} | {row['operation']} | "
            f"{row.get('api_family', 'classic_v6_world_graph')} | {row['adapter']} | "
            f"{row['disposition']} | {median} | {peak} | "
            f"{digest} | {reason} |"
        )
    report.extend(
        [
            "",
            "## Interpretation and limits",
            "",
            (
                "The semantic preflight checks fixture counts and stable IDs directly from the "
                "deterministic generator, then hand-authored exact-identity, visibility-exclusion, "
                "search, evidence, complete-object, and source-anchor expectations through "
                "supported APIs before timing. Repeated semantic digests are an additional "
                "determinism check, not the correctness oracle."
            ),
            "",
            (
                "PostgreSQL is explicitly inactive under PR #91; every PostgreSQL matrix cell is "
                "`not_measured` for lack of an authorized target. Large-scale non-core operations "
                "outside the activated cohort are explicitly not measured. `resource_limited` rows "
                "name the enforced host limit and observed process high-water RSS where available."
            ),
            "",
            (
                f"Acceptance state: **{document['acceptance_status']}**. PRIME authorized this "
                "partial baseline through 10k; 50k/100k attempts are deferred and not accepted. "
                "This does not accept the full characterization, V8, or V11."
            ),
            "",
            (
                "Regenerate with the command and environment recorded in the JSON artifact. "
                "Compare timings only on materially comparable hosts and interpreter builds. "
                "This artifact is not V8 acceptance, V11 acceptance, or permission to dispatch a "
                "cutover."
            ),
            "",
        ]
    )
    output.with_name("REPORT-vnext-scale-characterization.md").write_text("\n".join(report))
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output", type=Path, default=Path("Docs/Reports/VNEXT-scale-characterization-v1.json")
    )
    args = parser.parse_args()
    if any(n not in SIZES for n in args.sizes):
        parser.error(f"sizes must be selected from {SIZES}")
    hard_limit = _hard_memory_limit_bytes()
    if any(n > 10_000 for n in args.sizes) and (hard_limit is None or hard_limit > 8 * 1024**3):
        parser.error(
            "50k/100k attempts require an enforceable cgroup hard memory limit <= 8 GiB; "
            "host limit unavailable"
        )
    run(tuple(args.sizes), args.output, args.repeats)


if __name__ == "__main__":
    main()
