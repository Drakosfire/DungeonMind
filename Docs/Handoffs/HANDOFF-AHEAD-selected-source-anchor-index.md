# HANDOFF — AHEAD selected source-anchor index

**Created:** 2026-10-08  
**Status:** BLOCKED — proposed ACTIVE contract; no implementation authority before the activation gates below  
**Repository / proposal branch:** `Drakosfire/DungeonMind` / `codex/ahead-selected-source-index-contract`  
**Core base:** `a501784f21aaafb46d7561f46397a3afdc42f125`  
**Proposed Buddy consumer base:** `f687ecef54dd508e3fdff0c85cba21792bfa3b7f`  
**Coordinator:** PRIME  
**Contract reviewer:** ARCHITECTURE  
**Owners:** Core owns admitted targets, provenance, native index semantics and coverage; Buddy owns its immutable receipt, product source-read authorization and body opening.  
**Topology:** serial — one capability, Core contract/source PR first; Buddy adoption follows the reviewed Core publication and explicit consumer lease.  
**One-line mission:** Permit a small authorized retrieval selection to obtain a complete bounded metadata index without requiring an unrelated whole-world source index to fit 512 entries.

## §1 Outcome

Core exposes a separate revision-pinned selected-target source-anchor index. Buddy can perform an admitted search, commit the selected native targets and source pins, and use its existing bounded source opener. A world containing 513 unrelated eligible source anchors no longer blocks a small selected index. Selected-scope overflow, unavailable targets and unresolved provenance remain explicit. A selected result never claims whole-world coverage.

This proposal is independently useful without admitting or replaying any corpus. It does not implement search pagination, increase budgets, change source classification, or widen scope. Existing global-index calls and stored policy/receipt replay preserve their current semantics.

## §2 Authority and anchors

Read these in order before activation:

1. `Docs/Architecture/ARCHITECTURE.md` §§2–3 and `Docs/Architecture/AUTHORITY.md`: Core owns knowledge admission and explicit revision/scope semantics; source bodies and product presentation remain consumer concerns.
2. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-retrieval.md`: exact native read contexts, evidence targets, public-safe gaps and context-bound anchors.
3. Core at the base above: `src/dungeonmind/application/world_graph_retrieval.py`, `world_graph_projection.py`, `world_graph_read_context.py`, `graph_scope.py`, and `contracts/projection_v2.py`.
4. Buddy at its proposed base: `apps/live_control_server/integrations/dungeonmind/world_graph_reads.py`, `routes/agent.py`, `services/agent_turn_service.py`, and `src/graph_memory/retrieval/models.py`.
5. Local characterization packet: `/tmp/rake-retrieval-limit-qualification/architecture-packet.json`, SHA-256 `edc2a6ead9e5ea93c2db2fef1861b56399ceab2f7b91cf823a68ccc228b5d72e`; lease proposal `/tmp/rake-retrieval-limit-qualification/proposed-lease.json`; input proof `input-qualification.json`; synthetic proof `benchmark-proof.json` in the same directory. These are evidence, not implementation authority or Graph admission.

The characterization measured deployed Buddy `d165f637af7532b3c404f7f6aa4a472e2ca33835` / tree `f211e0e96c25ad748e58e21edad6c0c435a3fbae` and installed Core `5d4e98963991995bdc280e57df52b8d0fe8de79e`. Core's index request/result, index method and search method match the current Core base. The original packet characterized Buddy `0e934cba8041e40e55112c01412f03f26bd83063`; the proposed implementation base above is a later explicit pin, not a claim that runtime was updated.

### Evidence that motivates this slice

- Search returns eight objects by default, at most twelve; attributes and anchors cap at thirty-two. The receipt's `result_limit: 32` is not a thirty-two-object or whole-world coverage promise.
- One turn permits eight graph expansions, eight source-read calls and eight source-read anchors, with 12,000 characters per read and 96,000 total. These budgets remain unchanged.
- Actual synthetic Core reads returned complete indexes for 451, 480 and 512 eligible anchors. At 513 the result was `overflow`, with zero entries. Buddy's default bootstrap requires a complete global index and refuses that result before provider dispatch.
- Eight identical synthetic searches returned the same eight objects. Repeating a deterministic bounded search is not pagination.
- The retained forty-four recap inputs passed 132 component hash checks. They contain 560 indexed spans, 480 distinct raw node/edge artifact-span bindings, 451 bindings matching the paired pinned index and 29 unresolved or cross-source raw bindings. Native evidence IDs deduplicate by artifact/span. These numbers are not an admitted index count; actual admitted unique anchors and additional genesis/source anchors remain unknown. No forty-four-source overflow is proven.
- Session 28 is outside that cohort. Lysandra appears in twenty retained sessions. A separate Fleshborn Hybrid statblock is available outside it, but identity linkage to a particular encounter is not established. Meat Mind HP/spawn mechanics are not grounded by those frozen recaps. Index selection cannot manufacture missing source admission or resolve identities.

## §3 Scope and proposed ACTIVE write lease

This section is a proposal. PRIME activates it only after §6's contract gates resolve, with exact implementation refs and the owner path leases recorded.

### Core predecessor: one selected-index capability

Expected paths:

- `src/dungeonmind/application/world_graph_retrieval.py`
- `tests/unit/test_world_graph_retrieval_service.py`
- This handoff, for truthful authority/activation/handback updates.

Add separate immutable selected-index request/result types and a separate service method. Reuse native evidence-target kinds and the existing exact read context. Do not change the legacy global request/result or reinterpret `list_source_anchor_index` completeness.

Proposed selector: one to eight distinct explicit targets, each with native kind `object`, `relationship` or `assertion` and a bounded nonblank native ID. ARCHITECTURE and the Core owner must ratify these cardinalities/kinds before implementation. The authenticated consumer constructs the selector from an admitted exact-revision retrieval result; Core independently checks admission. Selector membership is not authorization.

### Buddy successor: consume the same contract

Expected paths:

- `apps/live_control_server/integrations/dungeonmind/world_graph_reads.py`
- `apps/live_control_server/routes/agent.py`
- `apps/live_control_server/services/agent_turn_service.py`
- `tests/test_agent_turn_route.py`
- `tests/test_world_graph_retrieval_contract.py`
- `pyproject.toml` and `uv.lock`, only for the reviewed Core dependency publication/pin.

Use a new named selection-policy/commitment version. Bind the native selector and selector digest, world, exact Graph revision, kind/access/scope context, selected eligible count, explicit selected-target coverage and admitted anchor/evidence/artifact/revision tuples. Keep source pins inside the existing immutable per-turn source-read scope. A later graph expansion finding an anchor outside that frozen selection produces an explicit source-scope gap or a separately authorized turn; it does not mutate the scope.

No APP-STATE type or migration path is implicitly leased. If the new commitment cannot fit the existing receipt/constraint surfaces, stop and obtain the concrete owner/path extension before source edits.

### Excluded work

No corpus replay/admission, extraction, identity/alias repair, statblock synthesis, database writes, provider/model calls, live source/body probes, runtime deployment, World rebinding or cleanup. No search pagination, whole-world context/body dump, budget increase, general authorization hardening or second capability.

## §4 Invariants and response contract to ratify

1. Every read binds one authorized native world, exact revision, scope/focus and admissibility. Preserve Core's distinctions between world-owned, campaign and world-cross-campaign scope; reuse the existing Buddy mapping.
2. Core may narrow already admitted knowledge; it may not broaden scope, recover excluded targets, invent source revisions or accept caller paths/raw locators/body JSON.
3. Index only provenance reachable from admitted selected targets. Validate source artifact/revision/locator identity through existing Core provenance rules. The operation returns metadata only and opens no body.
4. Keep a hard selected-result cap of 512. A complete selected index reports its selected eligible count; an overflowing selected index reports explicit overflow and no authoritative partial entries. Neither outcome describes whole-world completeness.
5. Response coverage accounts for caller-requested targets, admitted targets, safe missing/unavailable outcomes, generic unauthorized access, unresolved source provenance and capacity/overflow. A target absent from the authorized view is not proof of global nonexistence. Do not make unauthorized-versus-nonexistent classification an existence oracle or echo hidden IDs, locators or source identities. Caller-provided ID echoes must follow existing public-safe coverage rules.
6. Selected source eligibility, validated source revision, product-local body availability and permission to open that body are separate facts. Source admission alone does not imply body availability; index selection alone does not authorize a source read.
7. Output ordering and selector digest are deterministic. Reject duplicate/malformed targets. Revalidate all pins through the exact snapshot/context rather than cache membership.
8. Old global index calls, old selection-policy receipts, their canonical bytes/hashes and replay meanings stay unchanged. Newly selected coverage receives a distinct policy/commitment identity.
9. Parent-authorized source opening still enforces eight calls/eight anchors/character budgets. Neither a provider-supplied target nor a source URI can enlarge the immutable scope.

The exact response vocabulary and a safe per-target distinction between missing and unavailable are unresolved contract questions. They must be decided explicitly in review; this proposal does not claim an accepted wire/API shape.

## §5 Work plan after activation

1. Re-anchor both owner default branches, dependency refs, open PRs and active leases. Record exact implementation lanes and ownership of shared receipt/schema/config paths. If bases changed, review the concrete delta before edits.
2. Core implements the separate selected-index primitive with existing projection/provenance helpers. One operation uses one exact read context; no second head selection or body reads.
3. Core proves selector admission, public-safe target/provenance gaps, deterministic selected coverage and explicit capacity overflow with synthetic fixtures. The legacy 513-anchor global-overflow witness remains unchanged.
4. After independent Core review/publication, Buddy adopts the exact dependency and adds its selected-index policy/commitment adapter without changing body-open or graph-operation budgets.
5. Buddy proves the actual offline consumer chain: admitted search → selected native index → immutable receipt/scope → bounded source open. No live operator World, provider, database or runtime is used.
6. Review the cumulative owner diffs and the combined contract against exact heads. PRIME coordinates source publication and a truthful handback. Runtime adoption is a separate authority.

## §6 Acceptance and activation gates

### Before BLOCKED can become ACTIVE

- ARCHITECTURE accepts the separate selected-target coverage/authority contract, selector cardinalities/kinds and no-leak response semantics.
- Core and Buddy owners critique their boundary, including immutable source-scope behavior after graph expansion and legacy receipt replay.
- PRIME records the adopted/landed durable handoff, exact source/dependency refs, implementation branches, serial PR order, exclusive path leases, synthetic output directories and applicable runtime/data prohibitions.
- Any shared APP-STATE/schema requirement is resolved with an explicit lease. No permission is inferred from this draft.

### Required owning proofs

- A synthetic world with 513 or more unrelated eligible anchors permits a one-target selected metadata index within its bound; no bodies open. Legacy global index still reports empty overflow.
- A selected scope itself exceeding 512 returns explicit selected overflow and no complete partial result.
- Wrong revision, access/admissibility, scope, target kind, malformed or duplicate targets fail closed. Excluded targets reveal no hidden Graph/source identity. Requested/admitted/safe-missing/unavailable/provenance-gap coverage is truthful.
- Unknown source revision, unsupported locator, stale source state and unresolved evidence are explicit coverage gaps; no invented source pin survives.
- Selector, index, revision or anchor tampering fails Buddy receipt freeze/replay/open checks. An outside-selection anchor remains denied. Old policies retain exact canonical hashes and replay meanings.
- Actual offline Buddy consumer search → selected index → existing source opener succeeds for admitted pins; eight graph operations, eight calls/eight anchors, 12,000-per-read and 96,000-total bounds remain enforced.
- Acceptance cases explicitly distinguish missing admission/source coverage from retrieval misses. Pre-S29 Lysandra evidence must cite an exact accepted source passage and state unopened history. Session 28/Hybrid and Meat Mind mechanics need real admitted source/identity evidence; no inferred statblock equivalence or invented HP/spawn values.

Proposed owning commands, to run only after implementation authorization:

- Core: `uv run pytest tests/unit/test_world_graph_retrieval_service.py`; affected-file Ruff and cumulative diff inspection.
- Buddy: targeted `tests/test_agent_turn_route.py` and `tests/test_world_graph_retrieval_contract.py`; affected-file Ruff and cumulative diff inspection.

Any additional required gate follows the owner policy and a concrete risk. No database-backed or provider smoke run is authorized by this handoff.

## §7 Stop conditions

Stop if the contract is not accepted, a named owner/path lease is absent, a selector requires scope widening or body authority, public-safe missing/access semantics cannot be maintained, legacy receipt meaning changes, shared migration/config paths exceed the lease, or a live/state operation is needed. Return the exact reproduction/decision to the owner and PRIME. No repeated readiness loop or watching another agent substitutes for this slice.

## §8 Handback requirements

Return each owner repo/base/head/branch/PR; contract decisions and rationale; exact selector/index/receipt identities; synthetic proof commands/results; legacy compatibility evidence; cumulative diff review; measured limitations; and the precise next owner action. Separate selected-target completeness from world coverage, source availability from admission, and code publication from runtime adoption. Do not claim the retained corpus is recovered, complete or semantically accepted by this capability.
