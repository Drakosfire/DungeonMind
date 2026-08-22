#!/usr/bin/env python3
"""Deterministic synthetic-v6 benchmark harness for direct World Graph reads (R.2a).

Characterizes the landed R.1/R.2 direct read seam — latency distribution and
peak traced memory — over deterministic synthetic ``dm_union_graph_v6`` graphs
parsed under the bundled D&D v3 semantic profile. No database, Buddy checkout,
network, or private campaign content is required.

Design rules (handoff §6):

* graph generation is deterministic (fixed seed; parameters recorded in
  benchmark metadata);
* setup (generation, publication, service construction, target/anchor
  selection) happens outside the timed function;
* every case passes a deterministic semantic digest preflight (repeated
  identical calls must produce identical digests) before it is timed — a
  digest mismatch is a correctness failure, not benchmark noise;
* result sizes stay bounded while the graph grows;
* ``resolve_source_anchor`` is exercised with a deliberately late anchor so
  the whole-projection/whole-anchor rederivation cost is characterized
  honestly rather than hidden behind a lucky early match.

Usage:

    uv run python benchmarks/world_graph_reads.py --help
    uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/smoke.json
    uv run python benchmarks/world_graph_reads.py -o baselines/latency.json
    uv run python benchmarks/world_graph_reads.py --tracemalloc -o baselines/memory.json
"""

from __future__ import annotations

import enum
import random
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from typing import Any

import pyperf  # dev-only benchmark tool; never imported by dungeonmind core
from pydantic import BaseModel

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_v3_descriptor,
)

GENERATOR_SEED = 20260822
SIZE_LADDER = (100, 1_000, 5_000, 10_000)

WORLD_ID = "world:bench"
CAMPAIGN_ALPHA = "camp:alpha"
CAMPAIGN_BETA = "camp:beta"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)

PREDICATES = ("dnd5e:near", "dnd5e:located_in", "dnd5e:connected_to")
PROPERTY_TERMS = ("dnd5e:population", "dnd5e:threat_level")
SEARCH_QUERY = "hold"


# ---------------------------------------------------------------------------
# Deterministic synthetic v6 fixture generation
# ---------------------------------------------------------------------------


def _meta(
    assertion_id: str,
    *,
    evidence: tuple[str, ...],
    visibility: str = "player",
    campaign_scope: str | None = None,
) -> dict:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": visibility,
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": list(evidence),
        "session_refs": [],
        "temporal_scope": {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
    }


def _evidence_row(
    evidence_ref_id: str, artifact_id: str, revision_id: str, *, span: str | None = None
) -> dict:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": artifact_id,
        "source_revision_id": revision_id,
        "source_domain_key": "buddy.worldbuilding",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": span is not None,
        "session_id": None,
        "source_span_ref_id": span,
        "locator": f"bench://{artifact_id}",
        "uri": None,
        "source_locator": None,
        "line_ref": None,
    }


def _scope_for(index: int) -> str | None:
    """Deterministic scope split: 20% world-owned, 40% alpha, 40% beta."""
    bucket = index % 5
    if bucket == 0:
        return None
    if bucket in (1, 2):
        return CAMPAIGN_ALPHA
    return CAMPAIGN_BETA


def _artifact_for_scope(scope: str | None) -> tuple[str, str]:
    if scope == CAMPAIGN_ALPHA:
        return "src:alpha-notes", "srcrev:alpha-notes-v1"
    if scope == CAMPAIGN_BETA:
        return "src:beta-notes", "srcrev:beta-notes-v1"
    return "src:world-lore", "srcrev:world-lore-v1"


def generate_payload(*, object_count: int, seed: int) -> tuple[dict, dict[str, Any]]:
    """One deterministic synthetic v6 payload plus its generation parameters."""
    rng = random.Random(seed)
    objects: list[dict] = []
    relationships: list[dict] = []
    evidence_rows: list[dict] = []
    gm_only_objects = 0
    alias_count = 0
    property_count = 0

    for i in range(object_count):
        object_id = f"obj:{i:06d}"
        scope = _scope_for(i)
        visibility = "gm" if i % 7 == 3 else "player"
        if visibility == "gm":
            gm_only_objects += 1
        evidence_id = f"ev:o:{i:06d}"
        artifact_id, revision_id = _artifact_for_scope(scope)
        span = f"span:o:{i:06d}" if i % 7 == 3 else None
        evidence_rows.append(_evidence_row(evidence_id, artifact_id, revision_id, span=span))

        aliases = [(f"The Old Hold {i:05d}", f"asrt:alias:o:{i:06d}", "player")]
        if i % 5 == 4:
            aliases.append((f"The Secret of Hold {i:05d}", f"asrt:alias2:o:{i:06d}", "gm"))
        alias_count += len(aliases)

        properties = []
        for p in range(1 + (i % 3)):
            term = PROPERTY_TERMS[(i + p) % len(PROPERTY_TERMS)]
            prop_visibility = "gm" if (i + p) % 4 == 3 else "player"
            properties.append(
                (
                    term,
                    f"value-{rng.randint(0, 10_000)}",
                    f"asrt:prop:o:{i:06d}:{p}",
                    prop_visibility,
                )
            )
        property_count += len(properties)

        objects.append(
            {
                "object_id": object_id,
                "kind": "dnd5e:location",
                "label": f"Hold {i:05d}",
                "assertion_metadata": _meta(
                    f"asrt:obj:{i:06d}",
                    evidence=(evidence_id,),
                    visibility=visibility,
                    campaign_scope=scope,
                ),
                "aliases": [
                    {
                        "value": alias_value,
                        "assertion_metadata": _meta(
                            alias_id,
                            evidence=(evidence_id,),
                            visibility=alias_visibility,
                            campaign_scope=scope,
                        ),
                    }
                    for alias_value, alias_id, alias_visibility in aliases
                ],
                "summary": {
                    "value": f"Generated hold {i:05d} of the benchmark world.",
                    "assertion_metadata": _meta(
                        f"asrt:obj:{i:06d}:summary",
                        evidence=(evidence_id,),
                        visibility=visibility,
                        campaign_scope=scope,
                    ),
                },
                "properties": [
                    {
                        "property_term": term,
                        "value": value,
                        "assertion_metadata": _meta(
                            prop_id,
                            evidence=(evidence_id,),
                            visibility=prop_visibility,
                            campaign_scope=scope,
                        ),
                    }
                    for term, value, prop_id, prop_visibility in properties
                ],
                "aspects": [],
            }
        )

    relationship_count = object_count + object_count // 2
    gm_only_relationships = 0
    for j in range(relationship_count):
        source_idx = j % object_count
        target_idx = (j * 7 + 11) % object_count
        if target_idx == source_idx:
            target_idx = (target_idx + 1) % object_count
        source_scope = _scope_for(source_idx)
        target_gm = target_idx % 7 == 3
        source_gm = source_idx % 7 == 3
        visibility = "gm" if (source_gm or target_gm) else "player"
        if visibility == "gm":
            gm_only_relationships += 1
        evidence_id = f"ev:r:{j:06d}"
        artifact_id, revision_id = _artifact_for_scope(source_scope)
        span = f"span:r:{j:06d}" if j % 7 == 5 else None
        evidence_rows.append(_evidence_row(evidence_id, artifact_id, revision_id, span=span))
        relationships.append(
            {
                "relationship_id": f"rel:{j:06d}",
                "source_object_id": f"obj:{source_idx:06d}",
                "target_object_id": f"obj:{target_idx:06d}",
                "predicate": PREDICATES[j % len(PREDICATES)],
                "assertion_metadata": _meta(
                    f"asrt:rel:{j:06d}",
                    evidence=(evidence_id,),
                    visibility=visibility,
                    campaign_scope=source_scope,
                ),
            }
        )

    descriptor = load_builtin_v3_descriptor()
    payload = {
        "world_id": WORLD_ID,
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": descriptor.profile_id,
            "profile_revision": descriptor.profile_revision,
            "descriptor_sha256": descriptor_sha256(descriptor),
        },
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": objects,
        "relationships": relationships,
        "evidence_refs": evidence_rows,
    }
    parameters: dict[str, Any] = {
        "generator": "benchmarks/world_graph_reads.py",
        "generator_seed": seed,
        "graph_schema": GRAPH_SCHEMA_V6,
        "semantic_profile": f"{descriptor.profile_id}@{descriptor.profile_revision}",
        "object_count": object_count,
        "relationship_count": relationship_count,
        "evidence_count": len(evidence_rows),
        "gm_only_object_count": gm_only_objects,
        "gm_only_relationship_count": gm_only_relationships,
        "alias_count": alias_count,
        "property_count": property_count,
        "scope_split": "20% world-owned / 40% campaign-alpha / 40% campaign-beta",
        "anchor_capable_locator_rule": "every 7th object/5th relationship evidence row",
    }
    return payload, parameters


def _seed_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    for artifact_id, revision_id, campaign_id in (
        ("src:world-lore", "srcrev:world-lore-v1", None),
        ("src:alpha-notes", "srcrev:alpha-notes-v1", CAMPAIGN_ALPHA),
        ("src:beta-notes", "srcrev:beta-notes-v1", CAMPAIGN_BETA),
    ):
        sources.put_artifact(
            SourceArtifactV2(
                source_artifact_id=artifact_id,
                source_domain_key="buddy.worldbuilding",
                source_domain=SourceDomain.WORLDBUILDING,
                world_id=WORLD_ID,
                campaign_id=campaign_id,
                session_id=None,
                uri=None,
                current_revision_id=revision_id,
                authority=None,
                visibility=Visibility.PLAYER,
                artifact_kind=None,
                document_class=None,
                review_state=None,
                source_visibility_state=None,
                workspace_document_ref=None,
                lineage={},
                status=SourceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        sources.put_revision(
            SourceRevision(
                source_revision_id=revision_id,
                source_artifact_id=artifact_id,
                content_sha256="dd" * 32,
                body_storage="external",
                locator=f"bench://{artifact_id}",
                created_at=NOW,
            )
        )
    return sources


# ---------------------------------------------------------------------------
# Benchmark environment (built outside the timed functions)
# ---------------------------------------------------------------------------


@dataclass
class BenchEnvironment:
    size: int
    projection: WorldGraphProjectionService
    retrieval: WorldGraphRetrievalService
    cross_gm: WorldGraphProjectionRequestV2
    cross_gm_pinned: WorldGraphProjectionRequestV2
    player_alpha: WorldGraphProjectionRequestV2
    object_target: str
    neighborhood_seed: str
    evidence_target: EvidenceTarget
    anchor_id: str
    fixture_parameters: dict[str, Any]


def build_environment(*, size: int, seed: int) -> BenchEnvironment:
    payload, parameters = generate_payload(object_count=size, seed=seed)
    world_graph = InMemoryWorldGraphRepository()
    published = world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:bench"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=NOW,
        )
    )
    sources = _seed_sources()
    descriptor = load_builtin_v3_descriptor()
    projection = WorldGraphProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([descriptor])
        ),
    )
    retrieval = WorldGraphRetrievalService(projection=projection, sources=sources)

    cross_gm = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
    )
    cross_gm_pinned = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
        revision_pin=published.revision_id,
    )
    player_alpha = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ALPHA,
        admissibility=Admissibility.PLAYER,
        scope_mode=ScopeModeV2.CAMPAIGN,
    )

    # Late, span-bearing object target (index ≡ 3 mod 7 carries a span locator).
    target_idx = size - 1 - ((size - 1 - 3) % 7)
    object_target = f"obj:{target_idx:06d}"
    neighborhood_seed = f"obj:{size // 2:06d}"
    evidence_target = EvidenceTarget(kind="object", target_id=object_target)

    # Deliberately late anchor: the maximum anchor identity of a late object,
    # so revalidation never terminates at the first derived anchor.
    lookup = retrieval.get_object(cross_gm, object_id=object_target)
    if not lookup.anchors:
        raise SystemExit(f"benchmark fixture error: no anchors for {object_target}")
    anchor_id = max(anchor.anchor_id for anchor in lookup.anchors)

    return BenchEnvironment(
        size=size,
        projection=projection,
        retrieval=retrieval,
        cross_gm=cross_gm,
        cross_gm_pinned=cross_gm_pinned,
        player_alpha=player_alpha,
        object_target=object_target,
        neighborhood_seed=neighborhood_seed,
        evidence_target=evidence_target,
        anchor_id=anchor_id,
        fixture_parameters=parameters,
    )


# ---------------------------------------------------------------------------
# Deterministic semantic digest preflight
# ---------------------------------------------------------------------------


def _semantic_normalize(value: Any, key: str | None = None) -> Any:
    if key == "projected_at":
        return "<excluded:projection-identity-clock>"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {k: _semantic_normalize(v, k) for k, v in value.model_dump().items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _semantic_normalize(getattr(value, f.name), f.name) for f in fields(value)
        }
    if isinstance(value, dict):
        return {k: _semantic_normalize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_semantic_normalize(item) for item in value]
    return value


def result_digest(result: Any) -> str:
    """Canonical digest of the semantic result, excluding projection clock stamps."""
    return canonical_sha256(_semantic_normalize(result))


def preflight_digest(name: str, call: Callable[[], Any], repeats: int = 3) -> str:
    digests = {result_digest(call()) for _ in range(repeats)}
    if len(digests) != 1:
        raise SystemExit(
            f"digest preflight failed for {name}: {len(digests)} distinct semantic "
            "outputs across repeated identical calls (correctness failure)"
        )
    return digests.pop()


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchCase:
    """One benchmark case. ``build_call`` binds the case to a built environment."""

    name: str
    build_call: Callable[[BenchEnvironment], Callable[[], Any]]
    metadata: dict[str, str]


def case_specs_for_size(size: int) -> list[BenchCase]:
    base = {
        "dm_graph_size": str(size),
        "dm_scope_mode": "world_cross_campaign",
        "dm_admissibility": "gm",
        "dm_result_bounds": "default",
    }

    def case(
        name: str,
        operation: str,
        build_call: Callable[[BenchEnvironment], Callable[[], Any]],
        **extra: str,
    ) -> BenchCase:
        return BenchCase(
            name=f"{name}@{size}",
            build_call=build_call,
            metadata={**base, "dm_operation": operation, **extra},
        )

    cases = [
        case(
            "project_head",
            "project",
            lambda env: lambda: env.projection.project(env.cross_gm),
            dm_pinned="false",
        ),
        case(
            "project_pinned",
            "project",
            lambda env: lambda: env.projection.project(env.cross_gm_pinned),
            dm_pinned="true",
        ),
        case(
            "get_object",
            "get_object",
            lambda env: lambda: env.retrieval.get_object(
                env.cross_gm, object_id=env.object_target
            ),
        ),
        case(
            "search",
            "search",
            lambda env: lambda: env.retrieval.search(env.cross_gm, query_text=SEARCH_QUERY),
        ),
        case(
            "neighborhood_d1",
            "get_neighborhood",
            lambda env: lambda: env.retrieval.get_neighborhood(
                env.cross_gm, seed_object_ids=[env.neighborhood_seed], depth=1
            ),
            dm_neighborhood_depth="1",
        ),
        case(
            "neighborhood_d2",
            "get_neighborhood",
            lambda env: lambda: env.retrieval.get_neighborhood(
                env.cross_gm, seed_object_ids=[env.neighborhood_seed], depth=2
            ),
            dm_neighborhood_depth="2",
        ),
        case(
            "get_evidence",
            "get_evidence",
            lambda env: lambda: env.retrieval.get_evidence(
                env.cross_gm, target=env.evidence_target
            ),
        ),
        case(
            "resolve_source_anchor",
            "resolve_source_anchor",
            lambda env: lambda: env.retrieval.resolve_source_anchor(
                env.cross_gm, anchor_id=env.anchor_id
            ),
        ),
    ]
    if size == 1_000:
        player_base = {
            **base,
            "dm_scope_mode": "campaign",
            "dm_admissibility": "player",
        }
        cases.extend(
            [
                BenchCase(
                    name=f"project_player_campaign@{size}",
                    build_call=lambda env: lambda: env.projection.project(env.player_alpha),
                    metadata={
                        **player_base,
                        "dm_operation": "project",
                        "dm_pinned": "false",
                    },
                ),
                BenchCase(
                    name=f"search_player_campaign@{size}",
                    build_call=lambda env: lambda: env.retrieval.search(
                        env.player_alpha, query_text=SEARCH_QUERY
                    ),
                    metadata={**player_base, "dm_operation": "search"},
                ),
            ]
        )
    return cases


class _LazyEnvironment:
    """Builds the size environment on first use, inside the running process.

    pyperf spawns one worker process per benchmark; building only the
    environment a worker actually measures keeps setup out of timed functions
    without making every worker rebuild the whole ladder.
    """

    def __init__(self, *, size: int, seed: int) -> None:
        self._size = size
        self._seed = seed
        self._env: BenchEnvironment | None = None

    def get(self) -> BenchEnvironment:
        if self._env is None:
            self._env = build_environment(size=self._size, seed=self._seed)
        return self._env


def _unreached() -> None:
    raise RuntimeError("worker-task alignment placeholder must never run")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _add_cmdline_args(parser: Any) -> None:
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=list(SIZE_LADDER),
        help="graph sizes to benchmark (default: the full reference ladder)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=GENERATOR_SEED,
        help="deterministic generator seed",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="comma-separated case-name substrings to run (default: all)",
    )


def _prepare_worker_cmd(cmd: list[str], args: Any) -> None:
    """Propagate harness arguments into pyperf worker processes.

    pyperf does not forward custom arguments to workers; without this the
    worker would parse defaults and its bench_func call sequence would no
    longer align with the master's worker-task numbering.
    """

    cmd.extend(["--sizes", *[str(size) for size in args.sizes]])
    cmd.extend(["--seed", str(args.seed)])
    if args.cases:
        cmd.extend(["--cases", args.cases])


def main() -> None:
    runner = pyperf.Runner(add_cmdline_args=_prepare_worker_cmd)
    _add_cmdline_args(runner.argparser)
    args = runner.parse_args()

    runner.metadata["dm_commit"] = _git_commit()
    runner.metadata["dm_generator_seed"] = str(args.seed)
    runner.metadata["dm_baseline_lane"] = "r2a"

    case_filter = args.cases.split(",") if args.cases else None
    worker_task = args.worker_task  # None in the master process

    task_index = 0
    for size in args.sizes:
        holder = _LazyEnvironment(size=size, seed=args.seed)
        for spec in case_specs_for_size(size):
            if case_filter and not any(c in spec.name for c in case_filter):
                continue
            if worker_task is None or worker_task == task_index:
                env = holder.get()
                call = spec.build_call(env)
                digest = preflight_digest(spec.name, call)
                metadata = {
                    **spec.metadata,
                    "dm_result_digest": digest,
                    **{
                        f"dm_fixture_{key}": str(value)
                        for key, value in env.fixture_parameters.items()
                    },
                }
                runner.bench_func(spec.name, call, metadata=metadata)
            else:
                # Keep the bench_func call sequence identical in every process
                # so pyperf's worker-task numbering stays aligned.
                runner.bench_func(spec.name, _unreached, metadata=dict(spec.metadata))
            task_index += 1


if __name__ == "__main__":
    sys.exit(main())
