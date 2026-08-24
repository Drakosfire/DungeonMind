# Baseline: native World Graph read-context optimization (R.3a)

**Status:** characterization record for the R.3a native read-context path.
**This baseline is not an SLO, a performance budget, a production-switch
threshold, or permission to flip `DUNGEONMIND_WORLD_GRAPH_DIRECT_READ`.**

It is the successor to
[`BASELINE-world-graph-reads-r2a.md`](BASELINE-world-graph-reads-r2a.md).
R.2a is unchanged. R.3a compares optimized native reads against the landed
R.2a semantic digests and against the R.3 live Eldyrwild *direct* witness,
not against Buddy's hydrated kernel.

- **Implementation branch:** `cutover/direct-read-optimization` (PR #45)
- **Base:** DungeonMind `main` `1b03bfc5f277fc1971461340d6d567a7cfef3d0f`
  (merged #44)
- **Lane:** `r3a` (handoff:
  `Docs/Handoffs/HANDOFF-cutover-direct-read-optimization.md`)
- **Synthetic harness:** `benchmarks/world_graph_reads.py` (same case names
  as R.2a)
- **Live harness:** `benchmarks/world_graph_live_postgres.py` (DSN/world via
  CLI; private graph/source identity never written)
- **Cycle 2 review:** cache/profile identity, snapshot isolation, PostgreSQL
  coherence proof, full-repo Ruff, exact handoff metadata. Semantic digests
  and the live V4 witness were re-run on that head.
- **Cycle 3 review:** public `SourceProvenanceSnapshot.artifacts` /
  `.revisions` mappings expose isolated copies so value mutation cannot
  change fingerprint or later read behavior. Live 180× witness stays frozen.

**Disposition recorded here:** `R3A_OPTIMIZED`. Switch disposition:
`SWITCH_NOT_READY`. The production direct-read gate remains default-off.

## What changed (cost, not contract)

R.3a does not add indexes, a scoped cross-request cache, Redis, or a global
parse singleton. Each public read now establishes one
`WorldGraphReadContext`:

1. exact head/revision load (unchanged);
2. parse of the immutable revision, reused in-process by
   `(parse_compatibility_id, world_id, revision_id)` through a service-local
   LRU (`ParsedImmutableRevisionCache`, default 8 entries). Returned snapshots
   are isolated copies; incompatible reader/profile registries cannot hit
   each other's cached parses;
3. one coherent `SourceProvenanceSnapshot` via
   `SourceRepository.get_provenance_snapshot` (Postgres:
   `REPEATABLE_READ` + `ANY(%s)` batch selects);
4. scoped projection + per-context evidence memo over that snapshot.

Public R.1/R.2 result types are unchanged. `project()` remains a
compatibility wrapper over `open_read_context()`.

## Synthetic ladder vs R.2a

Same generator seed `20260822`, same semantic profile
`dungeonmind.dnd5e@dnd5e-profile-v3`, same machine class as R.2a
(`drakosfire-code-laptop`, 12th Gen Intel Core i3-1215U). Every case below
**matched the R.2a semantic digest exactly**.

Sampling notes:

- Cycle 2 re-verified **all 34 R.2a semantic digests MATCH** at 100 / 1k /
  5k / 10k against `benchmarks/baselines/world_graph_reads-r2a-latency.json`.
  That is the semantic-parity proof. The latency/memory table below remains
  the Cycle 1 characterization (isolation copies were not re-laddered).
- Size 100 used pyperf `--fast` (multiple samples; median reported).
- Sizes 1k / 5k / 10k used `--debug-single-value` (one sample after digest
  preflight). Treat those as order-of-magnitude comparisons, not as
  calibrated medians.
- Timed synthetic cases are **warm-parse**: `build_environment` calls
  `get_object` before timing. That is the same harness shape as R.2a.
- Do not compare tracemalloc-run timings to the latency numbers.

| Case | 100 | 1k | 5k | 10k |
|---|---|---|---|---|
| project_head | 12.9ms (3.6×) | 129ms (4.0×) | 967ms (3.3×) | 2.32s (2.9×) |
| project_pinned | 13.3ms (4.1×) | 195ms (2.7×) | 970ms (3.3×) | 2.71s (2.5×) |
| get_object | 14.1ms (3.7×) | 140ms (3.7×) | 1.49s (2.1×) | 2.18s (3.2×) |
| search | 18.0ms (3.0×) | 460ms (1.7×) | 2.41s (1.9×) | 5.24s (1.9×) |
| neighborhood_d1 | 14.3ms (3.4×) | 148ms (3.7×) | 1.50s (2.2×) | 2.27s (3.1×) |
| neighborhood_d2 | 15.5ms (3.2×) | 148ms (3.7×) | 1.39s (2.3×) | 2.20s (3.3×) |
| get_evidence | 13.5ms (3.5×) | 192ms (2.7×) | 1.03s (3.1×) | 2.06s (3.4×) |
| resolve_source_anchor | 20.9ms (3.2×) | 199ms (3.5×) | 1.67s (2.7×) | 4.00s (2.4×) |
| project_player_campaign | — | 201ms (1.7×) | — | — |
| search_player_campaign | — | 294ms (1.6×) | — | — |

Parenthetical factors are vs the R.2a latency baseline medians. The synthetic
win is mostly: one snapshot instead of per-evidence `model_copy`, plus parse
reuse on already-warm timed calls. Search still pays graph-size lexical work
on top of projection, so it scales less than pure projection.

Peak traced memory at size 100 (do **not** compare these timings to the
latency column): ~1.19 MiB for projection/lookup/neighborhood/evidence vs
R.2a's ~3.2 MiB; anchor resolution ~1.31 MiB vs R.2a's ~3.6 MiB. The drop
is consistent with copying source records once at snapshot build instead of
per evidence row. A full 5k/10k memory ladder was not re-run; R.2a remains
the checked-in memory artifact.

Cold vs warm parse at synthetic 1k (cache cleared after `build_environment`):
cold project 341ms, subsequent project 360ms, pinned 147ms, identical
digests. In-memory parse is not the synthetic bottleneck; live PostgreSQL
N+1 was.

## Live Eldyrwild witness vs R.3 direct

Same repaired V4 identity as the R.3 Buddy witness. Private object/source IDs
are not recorded here.

```text
world:                 eldyrwild
receipt:               dm_existing_world_adoption_receipt_v4
M0 / M1:               match the public R.3 V4 digests
D_A / head D_B:        match the public R.3 revision pins
store:                 PostgreSQL dungeonmind_cutover_live @ 127.0.0.1:54329
host:                  same Linux dev machine as R.2a / R.3
runs:                  3 (median reported)
admitted (campaign GM): 390 objects / 176 relationships / 130 evidence
source snapshot:       26 artifacts / 26 revisions, one batch load
Cycle 2 witness:       isolation copies + profile-bound cache (this PR head)
```

R.3 direct campaign-GM projection median was **20,739 ms**, with
`scope_projection` ≈ 20.1s (99.6%) from per-evidence PostgreSQL source
gets. Cycle 1 R.3a (before isolation copies) was 89.2 ms warm. Cycle 2:

| operation | R.3 direct (ms) | R.3a Cycle 2 median (ms) | factor |
|---|---|---|---|
| projection (warm campaign GM) | 20,739 | **115.0** | **180×** |
| projection (cold, first parse) | 20,256 | 140.1 | 145× |
| exact object | 19,968 | 129.0 | 155× |
| search | 20,212 | 186.8 | 108× |
| neighborhood depth-1 | 20,937 | 130.7 | 160× |
| neighborhood depth-2 | 20,598 | 119.5 | 172× |
| evidence (object) | 20,547 | 120.9 | 170× |
| resolve_source_anchor | — | 156.3 | — |

Warm campaign-GM phase split (median): `head_lookup` 7.4ms,
`revision_load` 48.2ms, `parse` 18.4ms (cache hit; `parse_calls` = 0 — this
is defensive snapshot isolation, not a re-parse),
`source_snapshot_load` 15.9ms, `scope_projection` 17.6ms. Head/revision load
remain the dominant remaining wall; N+1 source admission is gone.

Repository-call proof on every measured operation, including retrieval:

```text
get_artifact = 0
get_revision = 0
get_provenance_snapshot = 1
parse (warm) = 0
parse (cold / first historical pin) = 1
```

Parse-reuse isolation on the live head: after caching D_B, pinning D_A
misses once then hits; returning to head stays a hit. Cold and warm
campaign-GM projections share one semantic digest; the historical pin has
a different digest, as required.

PLAYER campaign lens admitted 0 objects / 0 evidence on this world
(fail-closed GM visibility, not a leak). World-owned GM lens admitted 1
object. Those counts are DungeonMind admission facts, unchanged by R.3a.

**≥5× bar:** met. Warm direct projection is 180× vs the R.3 direct median.
The remaining wall time is revision payload load (~50ms), a ~16ms source
snapshot, and defensive parsed-snapshot isolation on cache hit (~18ms),
not evidence-chain round-trips.

## Reproduce

```bash
# Synthetic (same commands as R.2a; digests must match the r2a lane)
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/r3a-100.json
uv run python benchmarks/world_graph_reads.py --sizes 1000 --debug-single-value -o /tmp/r3a-1000.json

# Live Eldyrwild (requires the cutover Postgres and postgres extra)
uv sync --extra postgres --locked
DUNGEONMIND_DATABASE_URL='postgresql://dungeonmind:dungeonmind-dev@127.0.0.1:54329/dungeonmind_cutover_live' \
  uv run python benchmarks/world_graph_live_postgres.py --runs 3 -o /tmp/r3a-live.json
```

## What this baseline does not authorize

- Flipping `DUNGEONMIND_WORLD_GRAPH_DIRECT_READ` or any Buddy production
  gate. Switch-ready is a **separate disposition**, owned by a successor
  Buddy pin + rerun of the merged R.3 witness against this DungeonMind
  version.
- Treating synthetic 2–4× as the success bar. The named bar was live
  Eldyrwild direct projection.
- Caching scoped/authorized projections by revision + scope + campaign +
  admissibility. Source state is live; V4 source-classification repair
  proved the graph revision can stay put while source authority changes.
- Adding search/anchor indexes, Redis, or a process-global parse singleton.
