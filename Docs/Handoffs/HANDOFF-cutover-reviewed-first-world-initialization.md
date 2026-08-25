# HANDOFF — D.2C1: reviewed first-world initialization authority

**Created:** 2026-08-25  
**Status:** ACTIVE  
**Repository / branch:** `Drakosfire/DungeonMind` / `cutover/reviewed-first-world-initialization`  
**Base:** `c5d3688587b0f5d506e0f7d64f33eb0628bac896` — DungeonMind PR #45 merge  
**Design authority:** DungeonMindBuddy PR #642, merged as `d80c8688774602972e07593b83e3d8d09d4b0a7b`; accepted design head `0f9e07686dfd157bb35acbd10765bfe3de68166f`; Cycle 2 PASS-equivalent review `5023757627`  
**Predecessor:** DungeonMindBuddy D.2B / PR #640, merged `6ef7aefa741a82f512f5918b460cbee1a427cae4`  
**Successor:** DungeonMindBuddy D.2C2 mounted first-world authority migration, then D.3 graph-engine deletion  
**One-line mission:** Add a DungeonMind-owned, zero-parent reviewed first-world initialization unit of work that atomically authors a pristine world from reviewed facts, with exact durable replay/recovery and no adoption semantics.

---

## §1 Outcome

Against a pristine PostgreSQL world, one exact reviewed initialization command persists the required source lineage, one reviewed `GraphContributionV2`, one internally materialized `dm_union_graph_v6` initial revision `D_0` whose `parent_revision_id is None`, the world head at `D_0`, and one immutable reviewed-initialization receipt in a single atomic unit of work.

Exact retry/recovery returns the same receipt and `D_0` with zero second initialization. Conflicting operation bytes fail closed. Later legitimate descendants may advance head without invalidating the historical genesis receipt.

This slice is the provider prerequisite for Buddy D.2C2. It does not change Buddy product code.

## §2 Authority and anchors

Read these in order before implementation:

1. `CONTRIBUTING.md` — repository layering, versioned-contract, durable-write, test, and PR discipline.
2. `Docs/Architecture/AUTHORITY.md` and `Docs/Architecture/ARCHITECTURE.md`, especially governing invariants: one World Graph per world, immutable revisions, explicit head CAS, evidence validity, governed writes, profile ownership, replaceable clients.
3. DungeonMindBuddy merged design handoff at Buddy merge `d80c8688774602972e07593b83e3d8d09d4b0a7b`: `Docs/Plans/HANDOFF-CUTOVER-reviewed-first-world-initialization.md`.
4. `src/dungeonmind/application/existing_world_adoption.py` and `src/dungeonmind/infrastructure/postgres/existing_world_adoption.py` — precedent for pristine-target atomicity and durable receipt-first replay. Reuse patterns, not adoption semantics.
5. `src/dungeonmind/infrastructure/postgres/graph.py` — the proven parent-null publication primitive and atomic head CAS.
6. `src/dungeonmind/application/review_materialization_v6.py` and `src/dungeonmind/application/graph_snapshot_v6.py` — current v6 materialization/evidence conventions and strict reparse boundary.
7. `src/dungeonmind/contracts/contribution.py`, `src/dungeonmind/contracts/evidence.py`, and application repository protocols — repository-true contract names and layering.
8. Existing governed review/publication tests and existing-world adoption tests — regression authority.

Repository truth at dispatch:

- DungeonMind `main` is exactly `c5d3688587b0f5d506e0f7d64f33eb0628bac896`.
- Root `AGENTS.md` is absent at this base; `CONTRIBUTING.md` is the active repository operating contract.
- Current Alembic head observed at design is `0006_existing_world_adoptions.py`; re-check before adding a migration.

## §3 Scope

### In scope

- A versioned reviewed-first-world command/receipt contract family, preferred semantic names:
  - `dm_reviewed_world_initialization_command_v1`
  - `dm_reviewed_world_initialization_receipt_v1`
- Repository-true source types only:
  - `SourceArtifactV2`
  - `SourceRevision`
- A pure v6 first-world materializer that:
  - starts from an in-memory empty `UnionGraphV6Payload` value;
  - accepts only the bounded assertion semantics proven necessary for Buddy first-world authoring;
  - materializes from reviewed facts, never caller graph bytes;
  - reparses the final payload under the pinned semantic profile before persistence.
- A repository protocol/application service for reviewed first-world initialization.
- In-memory adapter coverage sufficient for unit semantics.
- A PostgreSQL atomic unit of work that writes source lineage, reviewed contribution, `D_0`, head, and reviewed-init receipt in one transaction.
- One dedicated reviewed-init receipt table/migration.
- Exact replay, conflict, outcome-unknown recovery, integrity validation, and historical receipt readback after head advance.
- One bounded reciprocal pristine check in existing-world adoption so a reviewed-init receipt makes adoption non-pristine.
- Unit/integration/regression tests and this handoff handback.

### Out of scope / falsification

- Do not repurpose `ExistingWorldAdoption` or write `existing_world_adoptions` rows for reviewed initialization.
- Do not call normal existing-parent governed publication with `"EMPTY"`, a synthetic revision, or any fabricated parent.
- Do not persist an empty-baseline revision solely to preserve Buddy's legacy `baseline_revision_id` shape.
- Do not accept caller-supplied `graph_payload` bytes as reviewed first-world authority.
- Do not add `SourceRevisionV2`; the source revision type is `SourceRevision` at the dispatch pin.
- Do not modify DungeonMind read behavior.
- Do not change Buddy product code, pin Buddy, perform CUTOVER state-sync, or implement D.2C2/D.3.
- Do not generalize first-world semantics beyond what the current reviewed contribution shape proves necessary.
- Do not refactor the whole v6 materializer merely to deduplicate helpers.

If implementation requires a second independently useful capability, stop and split it.

## §4 Invariants that bind this slice

### Architecture invariants

- One World Graph per world; campaign is scope, not a second graph.
- Published revisions are immutable; the explicit head advances atomically.
- Evidence/source closure is part of knowledge validity.
- Durable writes are governed; candidate/review state is not publication by itself.
- Profiles own domain meaning; generic DungeonMind must not import `dungeonmind_dnd`.
- DungeonMindBuddy is a replaceable client, not the definition of this API.

### First-world invariants

```text
pristine world
  + exact reviewed initialization command
  → exactly one authoritative D_0

D_0.parent_revision_id == None
head == D_0
```

The authoritative graph is materialized by DungeonMind from reviewed facts over an in-memory empty v6 value. There is no persisted fake parent.

### Frozen replay algebra from Buddy #642

The following is non-negotiable:

```text
same world + same initialization_id + same command_sha256
  → exact replay
  → same receipt / same D_0
  → zero new rows

same world + same initialization_id + different command_sha256
  → typed conflict
  → MUST NOT return stored receipt as success
  → zero mutation

same world + different initialization_id
  → conflict / already initialized
  → zero mutation

same initialization_id reused for another world
  → idempotency conflict
  → zero mutation
```

Receipt-first means fingerprint-equal command, not merely “a receipt exists.”

### Source contract freeze from Buddy #642

Use exactly `SourceArtifactV2` + `SourceRevision`. No `SourceRevisionV2` lands in this slice.

### Reciprocal pristine freeze from Buddy #642

The new reviewed-init UoW must reject any existing-world adoption receipt as non-pristine. Existing-world adoption may receive one bounded reciprocal check so a reviewed-init receipt is likewise non-pristine. Do not redesign adoption.

### Historical receipt invariant

A later governed child `D_1` may advance head. The reviewed-init receipt must still reconstruct, fingerprint-check, and verify its own `D_0` world/schema/payload/`parent=None` facts without requiring `D_0 == current_head`.

## §5 Work plan

1. **Re-anchor repository truth.**
   - Confirm `main`, migration head, existing public contract names, and repository interfaces.
   - If any pin-truth assumption changed, record it before coding; preserve the frozen semantic rules above.

2. **Add versioned command/receipt contracts.**
   - Bind `initialization_id`, world/campaign/plan provenance, semantic profile, complete source records, reviewed `GraphContributionV2`, actor, and requested timestamp.
   - Compute a canonical `command_sha256` over all semantic command fields.
   - Receipt records command digest, contribution identity/digest, published revision/schema/payload digest, accepted assertion ids, actor, and initialized time.
   - No graph payload field on the command.

3. **Add pure first-world v6 materialization.**
   - Build strict empty v6 value internally.
   - Validate create-new-only first-world identity semantics.
   - Apply the minimal accepted assertion vocabulary needed by current first-world reviewed contributions; expected baseline is `node` + `edge`.
   - Preserve evidence/source conventions and reparse the final payload with the pinned v6 reader.
   - No repository access from the pure materializer.

4. **Add application/repository boundary.**
   - Define the protocol under `application/`.
   - Implement receipt-first exact replay/conflict semantics in application logic or one clearly owned UoW boundary.
   - Map uncertain persistence outcomes to a typed recoverable/unknown-result error; retry probes durable receipt before any second mutation attempt.

5. **Add PostgreSQL atomic UoW and migration.**
   - Lock world.
   - Probe reviewed-init receipt by world; compare both `initialization_id` and `command_sha256`.
   - Reject same initialization id on another world.
   - Assert pristine across head, graph revisions, contributions, identity decisions, world-owned source history, reviewed-init receipt, and existing-world adoption receipt.
   - Persist source records and reviewed contribution.
   - Publish `D_0` with `parent_revision_id=None` and `expected_parent_revision_id=None` inside the same transaction.
   - Persist immutable reviewed-init receipt.
   - Commit.

6. **Add reciprocal adoption pristine guard.**
   - Existing-world adoption must treat a reviewed-init receipt as evidence that the world is not pristine.
   - No other adoption behavior changes.

7. **Prove exact behavior.**
   - Unit tests for contracts/materializer/replay/conflict/integrity.
   - Real PostgreSQL integration for atomicity, rollback, lost-response recovery, concurrent initialization, reciprocal pristine exclusion, and receipt readback after later head advance.
   - Existing adoption and governed publication regressions remain green.

8. **Hand back exact evidence.**
   - Update this handoff to record final head, PR, review cycles, exact commands/results, design decisions, and what remains false.

## §6 Acceptance gates

At minimum run:

```bash
uv run pytest tests/unit/test_reviewed_world_initialization.py
uv run pytest tests/unit/test_reviewed_world_initialization_materialization_v6.py
uv run pytest tests/unit/test_import_boundaries.py
uv run pytest tests/integration/test_postgres_reviewed_world_initialization.py -m integration
uv run pytest tests/integration/test_postgres_existing_world_adoption.py -m integration
uv run pytest tests/integration/test_postgres_review_publication.py -m integration
uv run ruff check .
uv run pyright
```

If repository test names differ at implementation time, use the exact owning equivalents and record them in handback.

Required behavioral evidence:

- pristine PostgreSQL `∅ → D_0` and `D_0.parent_revision_id is None`;
- payload created internally from reviewed contribution and reparses as strict `dm_union_graph_v6`;
- source lineage + contribution + graph revision/head + receipt are atomic;
- failure injection before commit leaves zero partial state;
- exact retry yields same receipt/revision and zero extra rows;
- lost-response retry/recovery yields same receipt/revision and zero second initialization;
- same world + same id + changed `command_sha256` is conflict, never replay;
- same world + different id is conflict with zero mutation;
- initialization id reused across worlds is conflict;
- later legitimate `D_0 → D_1` does not invalidate historical initialization receipt;
- reviewed initialization writes zero `existing_world_adoptions` rows;
- adoption rejects a world possessing a reviewed-init receipt;
- reviewed initialization rejects a world possessing an adoption receipt;
- existing-world adoption and normal governed existing-parent publication semantics remain unchanged.

## §7 Stop conditions

Stop and report rather than broadening scope if any of these occur:

- Current DungeonMind repository truth makes `SourceArtifactV2` + `SourceRevision` impossible without a separate migration/contract slice.
- First-world materialization requires identity matching against existing graph state; that contradicts pristine-world semantics.
- The current Buddy first-world reviewed contribution requires materially more assertion semantics than bounded `node`/`edge` plus narrowly proven evidence handling.
- Atomicity would require Buddy to coordinate multiple repositories/transactions.
- A solution requires caller-supplied graph bytes, a persisted fake empty parent, or adoption provenance.
- Exact replay cannot distinguish same `initialization_id`/different `command_sha256` without changing the frozen contract.
- Existing-world adoption cannot reciprocally see the reviewed-init receipt without a broad adoption redesign; split the bounded compatibility prerequisite rather than smuggling it in.
- Any change is needed to DungeonMind read behavior, Buddy product code, or D.2C2/D.3 to make the provider tests pass.

## §8 Handback requirements

Record all of the following before review completion:

- **Repositories and revisions:** repo / branch / base SHA / final head SHA / PR / merge status.
- **Review cycles:** count every formal review cycle and link the accepting review.
- **Decisions:** question / evidence / decision / rejected alternatives / consequences / reversal path.
- **Verification:** exact commands and exact results, including real PostgreSQL evidence.
- **Atomicity/recovery witness:** exact failure injection and row/head/receipt results.
- **What remains false:** explicitly state that Buddy is not yet repinned; mounted Buddy first-world still uses the legacy graph runtime until D.2C2; D.3 remains blocked.
- **Named successor:** DungeonMindBuddy D.2C2 first-world authority migration; after D.2C2 acceptance, D.3 graph-engine deletion.
