# HANDOFF — D.2C1: reviewed first-world initialization authority

**Created:** 2026-08-25  
**Status:** HANDED BACK (draft PR #46)  
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

## §8 Handback

### Repositories and revisions

- **Repo / branch:** `Drakosfire/DungeonMind` / `cutover/reviewed-first-world-initialization`
- **Base SHA (dispatch-only):** `a20d88f7ee469e0e8d2eb71e2de1c0293d2672a4`
- **Implementation HEAD:** `cd8a3d898dddea600e9be3aa604e08f07d29c4e1`
- **PR:** [Drakosfire/DungeonMind#46](https://github.com/Drakosfire/DungeonMind/pull/46) — **still draft**; not merged
- **Alembic head:** `0007_reviewed_world_init` (revises `0006_existing_world_adoptions`)

### Review cycles

Implementation cycle 1. Formal Review Cycle 1 (`5024424372`) was REQUEST-CHANGES-equivalent against `6b51c6476f9843f199d653fc4ac1356eafe7e8cc`. That repair closed invented `artifact:<contribution>` evidence and stopped silently dropping accepted non-mutating identity.

Cycle 2 PASS (`5024590474`) against `d5f3a4c22fc6d31e0e8584b0526fd9c26828e817` is **not operative**. Cycle 2 correction (`5024696192`) on that same SHA is REQUEST-CHANGES-equivalent. This head (`cd8a3d898dddea600e9be3aa604e08f07d29c4e1`) repairs:

1. accepted **nodes** still require `created_new`; accepted **edges** accept Buddy-neutral `None` or `created_new`. Existing-identity outcomes still fail closed. Other non-mutating edge outcomes fail as `accepted_edge_identity_unsupported` instead of silent drop;
2. a referenced artifact's command-owned `current_revision_id` counts as a referenced revision, so artifact-only fallback evidence is reachable; extra unused non-current revisions still fail `unreferenced_source_revision`;
3. those cases now have whole-operation proofs through `initialize_reviewed_world` (in-memory and PostgreSQL): success persists the edge on `D_0`, and integrity failures leave zero rows/receipts.

Awaiting Review Cycle 3 (SHA changed). PR #46 remains draft until accepted.

### Decisions

| Question | Evidence | Decision | Rejected alternatives | Consequences | Reversal |
|---|---|---|---|---|---|
| Share v6 helpers with review publication? | `review_materialization_v6.py` already owns create-new node/edge + evidence lift; existing v6 publication tests must stay green | Dedicated `materialize_reviewed_world_initialization_v6` copies those conventions; do not refactor the existing materializer | Extract shared helpers from `review_materialization_v6.py` | Small duplication; first-world never observes repositories/head/adoption/caller graph bytes | Delete the dedicated materializer if a later slice proves a shared helper independently useful |
| Where does `command_sha256` live? | Frozen algebra keys replay on `initialization_id` **and** digest; receipt-first is fingerprint-equal command, not “a receipt exists” | Compute in application bind via `canonical_sha256(model_dump(mode="json"))`; command model omits the field; store digest on the receipt | Put digest on the command contract; treat any receipt as success | `requested_initialized_at` is inside the digest; exact retry must reuse the same timestamp | Add an explicit digest field only by versioned supersession |
| Alembic revision id length? | `alembic_version.version_num` is `varchar(32)`; `0007_reviewed_world_initializations` is 35 chars and failed to stamp | Use `0007_reviewed_world_init` (24 chars); keep table name `reviewed_world_initializations` | Widen `version_num` | Filename/revision id shorter than the table name | Rename only if a later migration policy requires it |
| How to prove receipt vs later head? | Need `D_0 → D_1` without inventing a second capability | Publish a legitimate child with `PostgresWorldGraphRepository.publish_revision` on a slightly mutated v6 payload, `parent=D_0` | Import full review-publication fixtures into this slice | Receipt readback still returns `D_0` and does not reset head | D.2C2 may replace this child with a real governed publication if useful |
| Reciprocal pristine? | Adoption must not treat a reviewed-init world as empty | One extra SELECT on `reviewed_world_initializations` (`family=reviewed_world_initialization`); in-memory optional lookup defaults empty so existing adoption unit tests stay green | Redesign adoption contracts/replay | Init writes zero `existing_world_adoptions` rows; both directions fail closed | Remove the SELECT only if the two authorities are later unified |
| Accepted edge identity? | Buddy first-world producer marks accepted edges `accepted_by_operator`; the existing Buddy→DungeonMind mapping normalizes that to `None` | Nodes require `CREATED_NEW`; edges accept `None` or `CREATED_NEW`; existing-identity and other non-mutating outcomes fail closed | Require `CREATED_NEW` for edges | D.2C2 can pass Buddy-true edge identity without falsifying the mapping | Re-tighten only if Buddy starts emitting `created_new` for edges |
| Artifact-only current revision? | Fallback evidence already uses a referenced artifact's `current_revision_id`, but unreferenced-source checks never counted it | After collecting referenced artifacts, add each command-owned `current_revision_id` to `referenced_revisions` | Invent a revision pointer on the assertion | Artifact-only provenance is reachable; unused non-current revisions still fail | Keep failing closed if `current_revision_id` is missing from the command |

No stop condition from §7 was hit. Read behavior is unchanged. `SourceRevisionV2` was not invented. Caller `graph_payload`, `ExistingWorldAdoption` provenance, and fake `EMPTY` parents are absent.

### Verification

Required unit/lint gates (worktree `/home/drakosfire/Projects/DungeonOverMind/DungeonMind-reviewed-first-world-init`):

```text
uv run pytest tests/unit/test_reviewed_world_initialization.py \
  tests/unit/test_reviewed_world_initialization_materialization_v6.py \
  tests/unit/test_import_boundaries.py \
  tests/unit/test_existing_world_adoption.py
  → 120 passed in 3.53s

uv run ruff check .
  → All checks passed!

uv run pyright
  → 0 errors, 0 warnings, 0 informations
```

`DUNGEONMIND_DATABASE_URL` was unset in the process environment. Local compose Postgres was already healthy (`dungeonmind-postgres-dev`, `127.0.0.1:54329`). After `uv sync --locked --extra postgres`:

```text
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run pytest tests/integration/test_postgres_reviewed_world_initialization.py \
  tests/integration/test_postgres_existing_world_adoption.py \
  tests/integration/test_postgres_review_publication.py \
  tests/integration/test_postgres_review_publication_v6.py -m integration
  → 76 passed in 56.62s
```

First integration attempt failed closed: Alembic could not stamp `0007_reviewed_world_initializations` into `varchar(32)`. After shortening the revision id, the live DB remained at `0006_existing_world_adoptions` with no leftover `reviewed_world_initializations` table. Cycle 2 correction re-ran the same suite at 76 passed.

### Atomicity / recovery witness

PostgreSQL `failure_hook` stages `source_records`, `contributions`, `graph`, and `receipt` each raise before commit. Application maps the abort to `ReviewedWorldInitializationOutcomeUnknownError`. Row counts after each abort:

```text
heads=0 revisions=0 head_events=0 contributions=0 identity=0
artifacts=0 init_receipts=0 adoption_receipts=0 revisions_source=0
```

Lost-response: adapter commits, then raises `PersistenceUnavailableError`. Application recovery `get_for_world` returns the stored receipt. Exact retry returns the same receipt with `init_receipts=1` and `revisions=1`.

Happy path: `∅ → D_0`, `parent_revision_id is None`, head is `D_0`, one init receipt, required sources + one contribution, **zero** `existing_world_adoptions`. Same id + different `command_sha256` raises `IdempotencyConflictError` and must not return the stored receipt. Different `initialization_id` and cross-world reuse of the same id are conflicts with zero mutation. After a legitimate `D_0 → D_1` child, init receipt still names `D_0` and does not move head.

### What remains false

- DungeonMindBuddy is **not** repinned to this provider.
- Mounted Buddy first-world still uses the legacy graph runtime until **D.2C2**.
- **D.3** graph-engine deletion remains blocked.
- No public HTTP/CLI/agent transport for reviewed initialization.
- No `SourceRevisionV2`. DungeonMind read behavior is unchanged.

### Named successor

**DungeonMindBuddy D.2C2** — mounted first-world authority migration onto this provider. After D.2C2 acceptance, **D.3** graph-engine deletion.
