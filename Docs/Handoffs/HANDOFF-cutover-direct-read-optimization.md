# HANDOFF — R.3a: native World Graph read-context optimization

**Created:** 2026-08-23
**Status:** IN REVIEW (PR #45 Cycle 3; production gate unchanged)
**Repository / branch:** `Drakosfire/DungeonMind` /
`cutover/direct-read-optimization`
**PR:** https://github.com/Drakosfire/DungeonMind/pull/45
**Base:** DungeonMind `main` `1b03bfc5f277fc1971461340d6d567a7cfef3d0f`
(merged #44)
**Predecessor:** R.2a observability baseline; Buddy R.3 merged supported-contract
witness (`DungeonMindBuddy` `ffc39ab394ea55b00dc8b2a0fd41be0448635600`, PR #631)
**One-line mission:** Make native DungeonMind World Graph reads fast via one
reusable read context, immutable revision parse reuse, and one coherent batched
provenance snapshot, without changing R.1/R.2 semantics or flipping the
production direct-read gate.

---

## §1 Outcome

A caller of `WorldGraphProjectionService` / `WorldGraphRetrievalService` still
receives the same public R.1/R.2 result contracts. Internally, every public
read establishes one `WorldGraphReadContext`: exact revision, parsed immutable
graph (service-local LRU reuse keyed by
`(parse_compatibility_id, world_id, revision_id)`), one coherent
`SourceProvenanceSnapshot`, scoped projection, and a per-context evidence memo.
Live Eldyrwild direct projection falls from ~20.7s to ~115ms warm (180×) by
removing per-evidence PostgreSQL source gets. Isolation copies make cache-hit
`parse` phase ~18ms; `parse_calls` stay 0. R.2a synthetic semantic digests
match exactly (34/34). The production gate stays default-off.

Disposition recorded by the live harness:

```text
R3A_OPTIMIZED
SWITCH_NOT_READY
```

Switch-ready is a successor Buddy pin + rerun of the merged R.3 witness
against this DungeonMind version. Optimization existing is not permission to
flip `DUNGEONMIND_WORLD_GRAPH_DIRECT_READ`.

## §2 Authority and anchors

1. `Docs/Architecture/ARCHITECTURE.md` and `Docs/Architecture/AUTHORITY.md`
2. `Docs/Roadmaps/ROADMAP.md` — R.3a is this lane
3. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-projection.md` (R.1)
4. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-retrieval.md` (R.2)
5. `Docs/Handoffs/HANDOFF-cutover-world-graph-read-observability-benchmark.md` (R.2a)
6. Buddy R.3 baseline
   `Docs/Benchmarks/BASELINE-r3-direct-dungeonmind-current-reads.md`
   (characterization of the ~20.7s direct path; regression oracle is
   `R.3 direct result == R.3a optimized direct result`)
7. This implementation:
   `src/dungeonmind/application/world_graph_read_context.py`,
   `source_provenance_snapshot.py`, `parsed_revision_cache.py`,
   `world_graph_projection.py`, `world_graph_retrieval.py`,
   `graph_scope.py`, `repositories.py`,
   `infrastructure/memory/repositories.py`,
   `infrastructure/postgres/records.py`

## §3 Scope

**In scope:**

- `WorldGraphReadContext` as the real projection seam;
  `project()` is a compatibility wrapper and emits the same `project`
  observation.
- `SourceProvenanceSnapshot` + `SourceRepository.get_provenance_snapshot`
  (in-memory lock-coherent copy; Postgres `REPEATABLE_READ` batch).
- Service-local `ParsedImmutableRevisionCache` (default 8, keyed by
  `(parse_compatibility_id, world_id, revision_id)`, parse outside the lock,
  failures not cached, returned snapshots isolated from cache storage).
  Incompatible reader/profile registries cannot reuse each other's parses.
- Per-context evidence memo; retrieval reuses the same context (no live
  source re-hit after snapshot).
- Observability: new phase `source_snapshot_load`; optional
  `parsed_revision_cache_hit`, `source_artifact_count`,
  `source_revision_count`. Counts and booleans only.
- Tests proving parse reuse, head-move isolation, parse-failure non-poison,
  bounded LRU, **mandatory source freshness** (graph revision stable, source
  visibility change visible on the next context), N+1 removal, scope and
  admissibility axes, unknown admissibility fail-closed, in-memory snapshot
  coherence, **PostgreSQL REPEATABLE_READ snapshot non-tear**, returned-result
  mutation isolation, public provenance-mapping value-mutation isolation,
  incompatible-profile cache miss, retrieval
  hit/miss/search/neighborhood/evidence/anchor.
- Synthetic R.2a ladder digest compare + live Eldyrwild witness.
- This handoff, ROADMAP pointer, and
  `Docs/Benchmarks/BASELINE-world-graph-reads-r3a.md`.

**Out of scope (falsification):**

- Enabling `DUNGEONMIND_WORLD_GRAPH_DIRECT_READ` or any Buddy production
  gate.
- Scoped/authorized projection cache keyed only by
  `revision_id + scope + campaign + admissibility`.
- Redis, distributed cache, process-global parse singleton, search/anchor
  indexes, vector/semantic search, graph schema or write-path changes.
- Buddy concepts, Buddy kernel equality, or changing public R.1/R.2
  contracts / `WorldGraphProjectionResult` fields (R.2a digests walk
  dataclass fields).

## §4 Invariants that bind this slice

- Optimized R.3a result must be semantically indistinguishable from the
  merged R.3 *direct* result, not the old Buddy kernel.
- Parsed immutable graph snapshots are safe to reuse for one
  `(parse_compatibility_id, world_id, revision_id)`. A parse produced under
  one reader/profile registry must not be served to an incompatible reader.
- Source/provenance state is live. A V4 source-classification repair can
  change visibility while the graph revision stays put. The next
  `open_read_context` must observe current source state.
- One coherent snapshot per read: in-memory under the repository lock;
  Postgres under `REPEATABLE_READ` so artifact and revision rows cannot
  tear.
- Missing source IDs stay missing (fail closed).
- Observation never carries graph/user/source identity or text.
- Services communicate only through existing ports; no Buddy import.

## §5 Work plan (executed)

1. Add `SourceProvenanceSnapshot` and `SourceRepository.get_provenance_snapshot`.
2. Add `ParsedImmutableRevisionCache` and `WorldGraphReadContext`.
3. Make `open_read_context` the real seam; wrap `project()`; thread the
   snapshot + memo through `graph_scope` and retrieval.
4. Extend R.2a phases/fields without adding identity-bearing attributes.
5. Prove reuse, freshness, N+1 removal, and retrieval coherence in unit tests.
6. Remeasure: synthetic ladder (digests vs R.2a) then live Eldyrwild
   (latency vs R.3 direct). Stop short of indexes if the 5× live bar misses.
7. Record disposition. Do not flip the gate.

## §6 Acceptance gates

```bash
uv run pytest tests/unit/test_world_graph_read_context.py \
  tests/unit/test_world_graph_read_observability.py \
  tests/unit/test_world_graph_projection_service.py \
  tests/unit/test_world_graph_retrieval_service.py \
  tests/unit/test_graph_scope_provenance.py \
  tests/unit/test_graph_scope_v6.py \
  tests/unit/test_source_evidence_v2.py
uv run pytest tests/integration/test_postgres_provenance_snapshot_coherence.py -m integration
uv run ruff check .
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/r3a-100.json
# Live (postgres extra + cutover DSN):
uv run python benchmarks/world_graph_live_postgres.py --runs 3
```

Expected: tests green; R.2a digests match; live warm campaign-GM projection
median ≥5× faster than 20,739 ms; `get_artifact`/`get_revision` stay 0 after
snapshot; gate untouched.

## §7 Stop conditions

- Semantic digest drift vs R.2a synthetic cases, or live admission counts
  that differ from R.3 direct for the same request.
- Freshness failure: source visibility change hidden behind a revision-keyed
  scoped cache.
- Live 5× miss after batch snapshot + parse reuse. Record the remaining
  phase and stop. Do not add indexes or a scoped cross-request cache in
  this PR.
- Any change that would require flipping the production gate to “prove”
  the optimization.

## §8 Handback

### Repositories and revisions

- Repo: `Drakosfire/DungeonMind`
- Branch: `cutover/direct-read-optimization`
- PR: https://github.com/Drakosfire/DungeonMind/pull/45
- Base SHA: `1b03bfc5f277fc1971461340d6d567a7cfef3d0f` (current `main` after #44)
- Cycle 1 review: GitHub issue comment `5395883255` on exact head
  `920474db1f224935417b6d8832688d04d270ddc0`
- Cycle 2: GitHub review `5008678443` on exact head
  `e3d7cdd3afde29b1ba95c99ef0aaf9145841b040`
- Cycle 3: this branch tip after public provenance-mapping isolation
  (commit SHA is the PR head that lands these changes)
- Downstream consumer to pin later: `DungeonMindBuddy` `main`
  `ffc39ab394ea55b00dc8b2a0fd41be0448635600`

### Architecture fitness

| Axis | Before (R.3 direct / R.2a) | After (R.3a Cycle 2) |
|---|---|---|
| Live Eldyrwild campaign-GM projection | 20,739 ms median; `scope_projection` 20.1s | 115.0 ms warm / 140.1 ms cold (180×) |
| Live source calls per read | N+1 `get_artifact`/`get_revision` | `get_provenance_snapshot` = 1; per-get = 0 |
| Live parse | 12 ms every read | 47.9 ms cold; cache hit `parse_calls` = 0 (isolation copy ~18ms in parse phase) |
| Synthetic 10k `project_head` | 6.74 s | Cycle 1: 2.32 s; Cycle 2: **34/34 R.2a digests MATCH** |
| Peak traced memory @100 | ~3.2 MiB | Cycle 1: ~1.19 MiB (not re-laddered in Cycle 2) |
| Public R.1/R.2 contracts | unchanged | unchanged |
| New types | — | `WorldGraphReadContext`, `SourceProvenanceSnapshot`, `ParsedImmutableRevisionCache` |
| New port method | — | `SourceRepository.get_provenance_snapshot` |
| Cache identity | — | `(parse_compatibility_id, world_id, revision_id)` |
| Scoped cross-request cache | none | **none** (forbidden) |
| Search/anchor indexes | none | **none** (forbidden) |

### Decisions

- **Reusable parsed revision, not reusable scoped projection.** Parsed bytes
  are a pure function of `(parse_compatibility_id, world_id, revision_id)`.
  Scoped admission consults live source state, so it is rebuilt per context
  from a fresh snapshot.
- **Cache identity includes reader/profile compatibility.** Sharing one cache
  object across incompatible `GraphSnapshotReader` / profile registries cannot
  bypass parse-time profile verification.
- **Returned snapshots are isolated copies.** Mutating a caller's object,
  relationship, evidence, or provenance record cannot poison the cached
  revision or a later read. Provenance backing maps are private; public
  `artifacts` / `revisions` mappings and accessors return copies. Mutating a
  model obtained through the public mapping cannot change `fingerprint` or
  later `get_artifact` / `get_revision` / evidence resolution.
- **Retrieval must consume the same context.** Re-hitting live sources after
  projection would break source-coherence and the N+1 proof.
- **`WorldGraphProjectionResult` gained no fields.** R.2a digests walk
  dataclass fields; extra fields would look like semantic drift.
- **Optimization ≠ switch.** `R3A_OPTIMIZED` is recorded. `SWITCH_NOT_READY`
  stays until a Buddy pin+witness PR says otherwise. This PR does not
  flip the gate.

Rejected alternatives: Redis / process-global singleton; scoped cache keyed
by revision+scope+campaign+admissibility; jumping to indexes before measuring
the batch+reuse win.

### Verification

- Unit tests listed in §6: green (`uv run pytest`; full `-m "not integration"`
  1350 passed, including public provenance-mapping value-mutation isolation).
- PostgreSQL coherence:
  `tests/integration/test_postgres_provenance_snapshot_coherence.py` green.
- `uv run ruff check .`: clean (full repo, including
  `benchmarks/world_graph_live_postgres.py`).
- `uv run pyright`: 0 errors.
- Synthetic R.2a ladder: **all 34 case digests MATCH** at 100 / 1k / 5k / 10k.
- Live Eldyrwild Cycle 2: identity preflight ok; warm projection **115.0 ms vs
  20,739 ms (180×)**; N+1 removed; parse reuse isolated across D_B / D_A /
  return-to-head; admission counts unchanged (390 / 176 / 130).
- Durable numbers:
  `Docs/Benchmarks/BASELINE-world-graph-reads-r3a.md`.

### What remains false

- The production direct-read gate is still default-off.
- Buddy has not pinned this DungeonMind version.
- The merged R.3 witness has not been re-run against the optimized native
  services as a long-lived process.
- Switch-ready is not claimed.
- No scoped projection cache, search index, or write-path change landed.
- SLOs are still not defined.

### Named next slice

A **small Buddy PR** (not this one): pin the optimized DungeonMind version,
reuse long-lived native read services across requests, rerun the merged R.3
witness, and record `SWITCH_READY` or `SWITCH_NOT_READY`. Do not flip the
gate merely because this optimization exists.
