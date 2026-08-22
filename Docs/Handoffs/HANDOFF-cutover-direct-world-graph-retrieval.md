# HANDOFF — CUTOVER direct World Graph retrieval primitives

**Created:** 2026-08-22  
**Status:** ACTIVE  
**Repository / branch:** `Drakosfire/DungeonMind` / `cutover/direct-world-graph-retrieval-primitives`  
**Base:** DungeonMind PR #38 merge `70f2f00ad10981adf0d74850f1c5d3f26e640574`  
**Predecessor:** DungeonMind PR #38 (`CUTOVER: expose direct World Graph projection service`)  
**One-line mission:** Expose DungeonMind-native, deterministic World Graph retrieval primitives over the exact v2 projection seam so DungeonMindBuddy can stop invoking its legacy graph kernel for production graph reads.

---

## §1 Outcome

A caller can construct one transport-neutral `WorldGraphRetrievalService` around the landed `WorldGraphProjectionService` and perform exact object lookup, deterministic graph-only search/referent resolution, bounded depth-1/depth-2 neighborhood expansion, assertion/evidence retrieval, admitted source-anchor derivation, and opaque source-anchor revalidation against one exact `dm_projection_request_v2` context. Every result reports the exact `ProjectionSnapshotV2` that was read and contains only DungeonMind-native graph/evidence/provenance values. No operation reconstructs a Buddy graph, opens source body content, invokes semantic/vector retrieval, calls an LLM, or imports a Buddy DTO.

This slice is complete when DungeonMindBuddy has every **graph-semantic** primitive required to replace these current Buddy-kernel calls in the following product PR: `search_campaign_graph`, `get_campaign_object`, `get_object_neighborhood`, `get_object_evidence`, and the graph-side admitted-anchor resolution step used before `read_source_anchor`.

## §2 Authority and anchors

Read these first, in order. Checked-in code and docs are authority; chat history is not.

1. `Docs/Architecture/ARCHITECTURE.md` and `Docs/Architecture/AUTHORITY.md` — DungeonMind owns retrieval, evidence admission, graph traversal, revision selection, and scope semantics; product surfaces consume them.
2. `Docs/Roadmaps/ROADMAP.md` — R lane. R.2 is the DungeonMind predecessor to the Buddy hydration-removal PR.
3. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-projection.md` — R.1 contract, including the frozen v1 projection vocabulary and the v2 `world_cross_campaign` scope.
4. `src/dungeonmind/contracts/projection_v2.py` — exact request/snapshot context for this service. Do not mutate the frozen v1 projection contracts.
5. `src/dungeonmind/application/world_graph_projection.py` — the only exact revision-resolution + scope-projection seam this slice should compose. Do not duplicate head/pin resolution.
6. `src/dungeonmind/application/graph_snapshot.py` — `ParsedGraphSnapshot`, graph object/relationship views, exact mention resolution, object lookup, relationship listing, and bounded graph helpers.
7. `src/dungeonmind/application/graph_scope.py` — campaign/admissibility/provenance authority, omitted-alias leak prevention, `resolve_evidence_provenance`, and public-safe exclusion diagnostics.
8. `src/dungeonmind/contracts/evidence.py` and `src/dungeonmind/application/repositories.py::SourceRepository` — v1/v2 evidence and source identity needed to derive and revalidate admitted anchors. Source identity is durable even when body bytes live elsewhere.
9. `src/dungeonmind/application/mind_turn.py` — behavior evidence for exact referent resolution, one-hop graph expansion, evidence admission, and explicit coverage. Do **not** refactor Mind Turn in this slice.
10. External cutover behavior evidence only — never import from it: `Drakosfire/DungeonMindBuddy@b850b9f8126a8c8488d17b3bdb6f99a60a162338`:
    - `apps/live_control_server/services/world_graph_retrieval.py`
    - `src/graph_memory/kernel/world_retrieval.py`
    - `src/graph_memory/retrieval/models.py`
    - `src/graph_memory/interaction/expansion_executor.py`

The Buddy code is a **characterization source**, not an ownership source. Preserve the product-observable capabilities needed for cutover; do not reproduce Buddy's DTO names, private revision IDs, internal score numbers, contribution-replay model, or filesystem assumptions.

## §3 Scope

### In scope

- Add `src/dungeonmind/application/world_graph_retrieval.py` with one transport-neutral `WorldGraphRetrievalService`.
- Compose `WorldGraphProjectionService.project(WorldGraphProjectionRequestV2)` exactly once per retrieval operation. All graph work happens over that one returned `ScopedGraphProjection`; no second head lookup, revision lookup, parse, or campaign fan-out.
- Add small **application-owned** immutable result/input helpers as needed (dataclasses are preferred). R.2 does not need a new public wire protocol merely to let the Python consumer adapt results.
- Expose a bounded result vocabulary sufficient for a product adapter to recover:
  - exact `ProjectionSnapshotV2` identity;
  - selected `GraphObjectView` values;
  - selected `GraphRelationshipView` values;
  - admitted property/assertion values needed for the existing Buddy claim ledger (`assertion_id`, subject object, property term/value, assertion metadata, evidence refs);
  - resolved referents / matched object IDs / deterministic match reasons;
  - admitted `EvidenceRef | EvidenceRefV2` values;
  - admitted source-anchor metadata;
  - explicit missing/truncation/provenance coverage without leaking hidden identities.
- **Exact object lookup:** exact stable DungeonMind object ID only. A miss is explicit; do not silently reinterpret an object lookup as label/alias search.
- **Search / referent resolution:** deterministic graph-only search over the already scoped snapshot. At minimum cover exact object IDs, exact admitted labels/aliases, kind/label/alias/summary text, admitted property term/value text, relationship predicate text, and related-object labels. Optional seed object IDs are admitted before ranking and remain bounded.
- Reuse the existing exact mention resolver and omitted/ambiguous-alias leak-prevention policy. Dense/semantic candidates are not part of this service.
- **Neighborhood:** accept 1–8 exact seed object IDs and depth `1 | 2`. Depth 2 is required because the current production Hermes expansion contract exposes it. Implement bounded deterministic breadth-first expansion over the already scoped exact revision; never search to replace a missing seed.
- **Evidence:** support targets by native DungeonMind identity: object, relationship, or admitted assertion ID. Return only evidence referenced by the admitted scoped view and revalidate each chain with `resolve_evidence_provenance` before returning it.
- **Source-anchor admission:** derive a deterministic opaque anchor ID only from admitted provenance and the full exact v2 read context. At minimum bind the anchor identity to:
  - anchor schema/version;
  - world ID;
  - campaign ID / `ScopeModeV2`;
  - focus;
  - admissibility;
  - selected graph revision ID;
  - evidence ref ID;
  - source artifact ID;
  - source revision ID when present;
  - the admitted locator identity (`source_span_ref_id` when present, otherwise the durable evidence/source locator identity).
- Anchor metadata may carry the already-admitted evidence/source records needed by the product-owned opener; it must never accept or invent a caller-supplied path, URI, locator, manifest selector, run ID, or source revision.
- **Opaque anchor revalidation:** expose a method that accepts only the same v2 projection context plus an `anchor_id`, reprojects/rederives against the exact selected revision, and returns the matching admitted anchor metadata or an explicit miss/denial. No cache entry is authority.
- Preserve exact historical revision pins for every operation, including anchor derivation/revalidation.
- Preserve R.1 scope semantics exactly:
  - v2 `campaign` = requested campaign + world-owned;
  - v2 `world` = world-owned only;
  - v2 `world_cross_campaign` = world-owned + every campaign scope in one revision;
  - admissibility is independent and always enforced.
- Add focused unit coverage on synthetic v6 + D&D v3 profile wiring and keep the complete repository quality gates green.
- Update the R-lane roadmap atomically when the PR lands, including exact PR/review truth and the R.3 successor.

### Out of scope (falsification)

- No DungeonMindBuddy imports, DTOs, route handlers, response envelopes, camelCase compatibility models, or product-specific error/status mapping.
- No `graph_memory`, `apps.*`, Hermes, FastAPI, filesystem-root, or corpus-registry dependency under `src/dungeonmind`.
- No source **body** opening or returned prose/content. R.2 owns source admission and opaque-anchor validation; R.3 may keep/move the legitimate product-owned body opener after DungeonMind validates the anchor.
- No semantic search port, embedding provider, semantic-document repository, vector retrieval, LLM, or arbitrary file-search fallback. A graph miss remains a graph miss.
- No Mind Turn refactor or retrieval-session migration. Those consumers may adopt this service later in an independent slice.
- No new durable graph schema, semantic profile revision, vocabulary term, contribution model, identity rule, write path, migration, or publication behavior.
- No Buddy legacy-ID redirect model, private Buddy revision translation, hydration cache, contribution replay, or frozen pre-cutover Buddy-state dependency.
- No neighborhood depth greater than 2 and no unbounded traversal.
- No requirement to preserve Buddy's internal numeric search scores or exact DTO ordering beyond the deterministic observable cutover witnesses defined in tests.
- Do not mutate `dm_projection_request_v1`, `dm_projection_snapshot_v1`, or `dm_retrieval_session_v1`. If a new external wire contract becomes necessary, stop and version it explicitly rather than silently widening an existing contract.

## §4 Invariants that bind this slice

1. **One exact revision per operation.** R.2 starts with one R.1 projection result and never combines revisions or campaign fan-outs.
2. **Projection is the read authority.** Retrieval may narrow/rank/expand the admitted projection; it may not broaden scope or recover an object/assertion/evidence row excluded by R.1.
3. **Search is candidate selection, not truth.** Exact IDs and admitted graph fields may rank candidates; returned facts/evidence still come only from the scoped revision.
4. **No fallback broadening.** A miss never triggers semantic/vector/file/LLM search inside this service.
5. **Hidden identity must stay hidden.** Omitted aliases, scope-unknown provenance, player-hidden assertions, and cross-campaign exclusions must not leak through match reasons, coverage, missing IDs, anchors, or diagnostics.
6. **Anchor identity is context-bound.** The same admitted provenance under the same exact projection context produces the same anchor ID. Changing revision, campaign/scope mode, focus, admissibility, evidence identity, source identity, or locator identity must not resolve the old anchor.
7. **Caller input is not source authority.** Anchor revalidation accepts only opaque `anchor_id` plus the authorized projection context. Source paths/URIs/locators come from admitted DungeonMind records only.
8. **Depth is bounded.** Neighborhood expansion is deterministic BFS with depth 1 or 2, at most eight seeds, and explicit result caps. Missing seeds are reported; they are never replaced by a search result.
9. **Native semantics, adapter later.** The R.2 service speaks DungeonMind object/relationship/assertion/evidence language. Mapping those results into the existing Buddy retrieval DTO/claim/session shape is R.3 product work.
10. **No hidden compatibility museum.** Do not copy Buddy kernel modules into DungeonMind. Port only the retrieval behavior DungeonMind owns, implemented against DungeonMind's current graph/provenance model.

## §5 Work plan

1. **Characterize the exact cutover surface.** Before implementation, confirm the five Buddy graph-semantic calls and current Hermes depth-2 path against the pinned Buddy commit in §2. Record the small operation matrix in the PR description: operation, current production caller, minimum required semantic output, and intentionally rejected legacy behavior.
2. **Define the native application result seam.** Add small immutable result/bounds/target types in `world_graph_retrieval.py` (or one equally narrow application peer). Prefer existing `ProjectionSnapshotV2`, `GraphObjectView`, `GraphRelationshipView`, `ResolvedReferent`, evidence contracts, and assertion metadata over copy-shaped product models.
3. **Implement object + search.** Compose R.1, exact-lookup objects, reuse exact mention resolution, and add deterministic graph-only lexical ranking. Add bounded results, match reasons, explicit misses, and hidden-alias regression coverage.
4. **Implement bounded neighborhood.** Deterministic depth-1/depth-2 BFS over the scoped snapshot; return admitted objects/relationships/property assertions only. Add missing-seed and truncation proof.
5. **Implement evidence + anchors.** Index admitted assertion IDs, revalidate evidence provenance, derive context-bound opaque anchors, and add exact anchor revalidation. Return metadata only; prove no source body is opened.
6. **Add cutover witnesses.** Extend the synthetic v6 authority fixture (world-owned + two campaigns + GM-only content) with relationships, properties/assertions, aliases, and v2 source/evidence locators. Cover campaign, cross-campaign, PLAYER, historical pin, depth 2, anchor stability, anchor context mismatch, broken provenance, and deterministic ordering.
7. **Run full gates and update docs atomically.** Update `Docs/Roadmaps/ROADMAP.md` from R.2 named successor to landed/in-review truth and name the exact R.3 Buddy PR mission. Do not begin R.3 in this repository.

## §6 Acceptance gates

Required commands:

```bash
uv run pytest tests/unit/test_world_graph_retrieval_service.py
uv run pytest
uv run ruff check .
uv run pyright
```

Repository-boundary proofs:

```bash
rg 'DungeonMindBuddy|graph_memory|apps\.|hermes' src/dungeonmind/application/world_graph_retrieval.py
rg 'SemanticSearchPort|QueryEmbeddingProvider|SemanticDocumentRepository|embedding' src/dungeonmind/application/world_graph_retrieval.py
```

Expected: no matches other than explanatory comments explicitly approved in review; prefer no matches at all.

CI must finish green end-to-end (`core` + existing PostgreSQL `integration`). A new PostgreSQL retrieval integration test is not required unless implementation changes repository semantics or unit/in-memory behavior cannot prove an owning boundary.

Behavioral gates:

- Unpinned retrieval reports the exact current DungeonMind head; a historical pin remains exact after a newer head exists.
- `campaign` excludes other campaigns; `world_cross_campaign` includes multiple campaigns from the same exact revision; PLAYER admissibility still hides GM-only fields in either mode.
- Exact object lookup returns only the requested admitted object and explicitly misses an absent/out-of-scope ID without search fallback.
- Search resolves exact IDs/labels/aliases, produces deterministic lexical matches from admitted graph fields, honors seeds, and never recovers an object through an omitted/ambiguous hidden alias.
- Search result ordering and truncation are deterministic across repeated calls on the same revision.
- Neighborhood depth 1 and depth 2 are both proven; missing seeds stay missing; traversal never crosses excluded objects/relationships.
- Returned property/assertion rows retain exact assertion IDs, subject object IDs, values, assertion metadata, and admitted evidence refs sufficient for the Buddy adapter to reconstruct its existing claim ledger without consulting `graph_memory`.
- Evidence retrieval for object, relationship, and assertion targets returns only revalidated admitted evidence; broken in-scope provenance produces explicit safe coverage while scope-unknown/hidden provenance does not echo hidden identifiers.
- The same admitted source under the same exact v2 context yields the same opaque anchor ID.
- Reusing an anchor ID under a different revision, campaign/scope mode, focus, admissibility, evidence/source identity, or locator identity does not resolve.
- Anchor metadata is sufficient for a later product-owned source opener to identify the admitted source/revision/locator, but R.2 returns no source body content.
- A v6 graph using the bundled D&D v3 semantic profile exercises the complete service path.
- Static inspection proves the service has no Buddy, filesystem-source-reader, semantic/vector, or agent dependency.

## §7 Stop conditions

Stop and report rather than widening the slice if:

- Implementation is not based on PR #38 merge `70f2f00ad10981adf0d74850f1c5d3f26e640574` (or a later `main` containing it).
- A direct retrieval operation would need to bypass `WorldGraphProjectionService` and independently resolve/rebuild graph authority.
- Matching current production behavior requires importing a Buddy DTO/kernel module instead of implementing DungeonMind-owned semantics.
- A current cutover-critical caller demonstrably needs neighborhood depth >2, unbounded traversal, semantic/vector fallback, or source-body search. Name that dependency as a separate successor rather than smuggling it into R.2.
- The current v6 graph/provenance view cannot identify the admitted property/assertion/evidence/source information needed for cutover without a new durable graph schema or semantic-profile revision.
- Anchor validation would require the frozen pre-cutover Buddy store, Buddy contribution replay, a private Buddy revision ID, or a product filesystem path. That is a cutover blocker, not permission to reintroduce the old engine.
- A new externally serialized wire contract is required. Stop, document why application-layer Python types are insufficient, and version the new contract explicitly; never widen an existing v1 schema in place.
- A requested coverage/diagnostic field would reveal an excluded object, hidden alias, source artifact, source revision, or evidence identity.
- Source body opening appears necessary inside DungeonMind to make R.2 tests pass. R.2 ends at admitted anchor metadata/revalidation; body opening belongs to a separately owned boundary.
- The slice starts refactoring `MindTurnService`, retrieval sessions, agent orchestration, write/review/publication, or product routes.

## §8 Handback requirements

- **Review cycles:** count every implementation/review/repair cycle explicitly.
- **Repositories and revisions:** DungeonMind branch / base = exact PR #38 merge SHA / head SHA / PR / status.
- **Cutover operation matrix:** for `search`, `object`, `neighborhood`, `evidence`, and `resolve_source_anchor`, name the current Buddy caller and the DungeonMind-native replacement seam actually delivered.
- **Decisions:** especially search semantics, depth-2 behavior, result bounds, assertion exposure, anchor identity inputs, and why source-body opening remains outside DungeonMind.
- **Verification:** exact commands and results, including CI run IDs for core + integration.
- **Boundary proof:** zero Buddy/`graph_memory` imports; zero semantic/vector/agent dependencies; zero source-body read.
- **What remains false:**
  - DungeonMindBuddy has not switched production reads yet.
  - Buddy still hydrates a `UnionSupergraphStore` until R.3 lands.
  - Buddy still owns/adapts its product retrieval DTOs, retrieval-session claim ledger, Hermes tool response shape, and legitimate source-body opener.
  - `MindTurnService` has not been refactored onto R.2.
  - Candidate/review/write preparation still has Buddy-shaped graph semantics until later retirement slices.
- **Named next slice:** `CUTOVER: remove Buddy graph hydration from production reads` in `Drakosfire/DungeonMindBuddy` — pin the landed DungeonMind R.2 dependency; adapt Buddy `campaign` → v2 `campaign` and Buddy `world` → v2 `world_cross_campaign`; replace `world_graph_projection.py` / `world_graph_retrieval.py` kernel calls with DungeonMind native reads; move/retain source-body opening outside `graph_memory`; delete private Buddy revision translation and the frozen-store dependency from production read paths. Do not broaden that PR into write-path retirement.
