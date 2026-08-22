# HANDOFF — CUTOVER direct World Graph projection

**Created:** 2026-08-22  
**Status:** ACTIVE  
**Repository / branch:** `Drakosfire/DungeonMind` / `cutover/direct-world-graph-projection-service`  
**Base:** `2edc07ff27a21b1c83aed847edf95b77d297910e`  
**Predecessor:** DungeonMind PR #37 (`CUTOVER: v6 governed review publication`) and DungeonMindBuddy PR #620 (`CUTOVER: complete DungeonMind World Graph authority`)  
**One-line mission:** Expose one transport-neutral DungeonMind application service that resolves an exact World Graph revision and returns the existing campaign/admissibility/provenance-scoped graph directly, so external consumers no longer need a Buddy-shaped graph merely to read DungeonMind authority.

---

## §1 Outcome

A caller with a `WorldGraphRepository`, `SourceRepository`, and correctly configured `GraphSnapshotReader` can submit the new v2 `WorldGraphProjectionRequestV2` and receive a `ProjectionSnapshotV2` plus `ScopedGraphProjection` for one exact DungeonMind revision. Unpinned reads resolve the current head; historical pins remain exact and report the current head separately. Missing, mismatched, or cross-world state fails closed using the existing DungeonMind error vocabulary. The service performs no writes, no semantic search, no agent turn, and constructs no DungeonMindBuddy graph type.

## §2 Authority and anchors

Read these first, in order:

1. `README.md` — DungeonMind owns durable knowledge, revision-aware graph projections, semantic retrieval, and evidence admission; DungeonMindBuddy is the workshop/consumer, not the graph authority.
2. `Docs/Architecture/ARCHITECTURE.md` and `Docs/Architecture/AUTHORITY.md` — core ownership and transport-neutral application-layer rules.
3. `CONTRIBUTING.md` — layering, fail-closed contracts, profile boundary, test/toolchain rules, and cross-repository PR discipline.
4. `src/dungeonmind/contracts/projection.py` — the frozen v1 projection request/snapshot wire shape; do not modify its vocabulary. `src/dungeonmind/contracts/projection_v2.py` — the v2 pair this seam speaks; v2 adds only the cross-campaign scope vocabulary.
5. `src/dungeonmind/application/repositories.py` — exact head/revision and source repository ports.
6. `src/dungeonmind/application/graph_snapshot.py` — versioned v1-v6 parsing and graph view types.
7. `src/dungeonmind/application/graph_scope.py` — existing campaign/admissibility/provenance admission authority.
8. `src/dungeonmind/application/mind_turn.py` — existing private composition of exact revision resolution → parse → scope, used as behavior evidence rather than copied product semantics.

## §3 Scope

**In scope:**

- Add a public application-layer `WorldGraphProjectionService`.
- Resolve one exact revision from `revision_pin` or the current head.
- Preserve exact selected revision and current head identity in `ProjectionSnapshot`.
- Parse through an injected `GraphSnapshotReader`; do not silently choose a semantic-profile registry.
- Apply the existing `project_scoped_snapshot` campaign/admissibility/provenance policy.
- Honor `scope_mode` in that policy through the new v2 projection contracts
  (`dm_projection_request_v2` / `dm_projection_snapshot_v2`), whose
  `ScopeModeV2` adds the additive `WORLD_CROSS_CAMPAIGN` lens (world-owned
  plus every campaign scope in one exact revision). The v1 contracts are
  frozen: their two-value scope vocabulary is unchanged and never accepts
  `world_cross_campaign`.
- Return the scoped graph plus projection identity without introducing a second graph representation.
- Fail closed on missing head, missing revision, repository identity mismatch, or payload world mismatch.
- Export the new application seam from `dungeonmind.application`.
- Unit-test the orchestration boundary with the in-memory repositories.

**Out of scope (falsification):**

- No DungeonMindBuddy code or imports.
- No product DTO compatibility layer.
- No semantic/lexical search, neighborhood ranking, source opening, or anchor admission.
- No new interpretation of `query_text`; successor retrieval work owns query behavior.
- No new focus-filtering semantics; `focus` is preserved in projection identity and existing graph-scope admission remains unchanged.
- No Mind Turn refactor in this slice.
- No PostgreSQL schema/migration change.
- No durable write, review, materialization, or publication change.
- No semantic-profile artifact change.

## §4 Invariants that bind this slice

1. DungeonMind durable state is the graph authority; this service is a read projection only.
2. One read is coherent against one exact immutable revision.
3. Absence of an explicit revision pin resolves to the head observed for this request and that resolved revision is reported.
4. Campaign/admissibility/provenance filtering uses the existing `graph_scope` authority; this slice must not fork policy. `scope_mode` is part of that policy and is versioned: the v1 projection contracts are frozen with the original two-value vocabulary (`campaign`, `world`), while the v2 contracts (`dm_projection_request_v2` / `dm_projection_snapshot_v2`) add the additive `world_cross_campaign` mode — the cross-campaign lens over one exact revision. Scope mode and admissibility are independent axes: the mode widens campaign scope only, encodes no upstream authorization decision, and a PLAYER read under it still fails closed on GM-only content. An explicit mode that contradicts `campaign_id` fails closed.
5. Profile-pinned v3+ graph parsing remains fail-closed. The service requires an injected reader instead of inventing a default profile registry.
6. Application code imports only contracts/domain/application-layer peers; no infrastructure, FastAPI, database driver, Hermes, or Buddy import.
7. No graph or source mutation is permitted.
8. Request `focus` and `query_text` must not silently acquire new semantics in this foundational slice.

## §5 Work plan

1. Add `src/dungeonmind/application/world_graph_projection.py` with a small orchestration service and result type.
2. Reuse `WorldGraphProjectionRequest`, `ProjectionSnapshot`, `WorldGraphRepository`, `SourceRepository`, `GraphSnapshotReader`, and `project_scoped_snapshot` directly.
3. Add exact identity guards around returned head/revision/payload world state.
4. Export the seam from `src/dungeonmind/application/__init__.py`.
5. Add unit tests proving head resolution, exact historical pins, authorized scope identity, and fail-closed missing/mismatched state.
6. Run the repository quality gates and repair only findings within this slice.

## §6 Acceptance gates

Required commands:

```bash
uv run pytest tests/unit/test_world_graph_projection_service.py
uv run pytest
uv run ruff check .
uv run pyright
```

Expected result: all commands pass.

Repository-boundary proof:

```bash
rg 'DungeonMindBuddy|graph_memory|apps\.' src/dungeonmind/application/world_graph_projection.py
```

Expected result: no matches.

Behavioral gates:

- An unpinned request returns the exact current DungeonMind revision as both selected revision and head.
- A historical pin returns that exact immutable revision while separately reporting the newer head and `is_head=false`.
- Missing head/revision and cross-world repository/payload corruption fail closed.
- The result exposes `ScopedGraphProjection`; no Buddy store, contribution replay, or local graph publication occurs.
- Campaign scope admits the requested campaign plus world-owned knowledge and excludes other campaigns.
- `world` scope remains world-owned only (unchanged v1 semantics).
- `world_cross_campaign` admits world-owned plus multiple campaign scopes in one exact revision, with admissibility still fail-closed.
- The v6 authority path is proven through the versioned union snapshot reader configured with the bundled D&D v3 semantic profile.

Merge-contract note: `uv run pyright` on the original base failed on six inherited
contribution-review union errors, and the core job also stopped at a latent SIM300
and at integration-collection imports without the `postgres` extra. Those inherited
failures are repaired by the baseline-hygiene PR #39; this branch is rebased onto it
so every required gate above runs for real rather than carrying a red-gate exception.

## §7 Stop conditions

Stop and report rather than widening the slice if:

- a direct projection requires a new durable graph schema or wire contract;
- existing `graph_scope` cannot safely project the currently supported graph schema;
- supporting a product consumer requires implementing Buddy-specific DTOs or UI behavior in DungeonMind;
- semantic retrieval/query behavior becomes necessary to prove this foundational read seam;
- a profile-specific behavior would require importing `dungeonmind_dnd` into `src/dungeonmind`;
- a write, migration, or persistence-schema change becomes necessary.

## §8 Handback requirements

- **Repositories and revisions:** DungeonMind branch/base/head/PR/status; name the exact tested head.
- **Decisions:** record why this is a native scoped-read seam rather than a Buddy compatibility model; preserve `focus`/`query_text` without inventing semantics.
- **Verification:** exact commands and pass/fail results.
- **What remains false:** DungeonMind does not yet expose the full Buddy-equivalent query/retrieval surface; DungeonMindBuddy still hydrates and reads through its legacy kernel until successor PRs land.
- **Named next slices:**
  1. `CUTOVER: expose direct World Graph retrieval primitives` in DungeonMind — object lookup, search/referent resolution, one-hop neighborhood, evidence/source-anchor admission over this exact scoped projection.
  2. `CUTOVER: remove Buddy graph hydration from production reads` in DungeonMindBuddy — replace `world_graph_projection` / `world_graph_retrieval` kernel calls with DungeonMind native reads; remove private Buddy revision translation and frozen-store read dependency.
