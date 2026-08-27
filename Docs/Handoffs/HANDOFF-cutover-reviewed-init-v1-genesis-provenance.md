# HANDOFF — CUTOVER: reviewed-init-v1 genesis provenance compatibility

**Created:** 2026-08-26  
**Status:** ACTIVE — CODE DISPATCH  
**Repository / branch:** `Drakosfire/DungeonMind` / `cutover/reviewed-init-v1-genesis-provenance`  
**Exact dispatch base:** `bf40e933bdedf3cf08bb23a07a135958bdb7cc6b`  
**Predecessor:** DungeonMindBuddy #653, merge `5ad992090c2e85d38784c888e4b870f5672bce8e`; accepted head `289201c9c60ec75c3acca998722be1a7d0600c43`; Review Cycle 4 PASS-equivalent `5036593867`  
**Parked consumer:** DungeonMindBuddy #651 at reviewed head `cf453078a5c1950ec5f23a5d5b99001ee9e456db`; Review Cycle 3 `5035980646`  
**Suggested PR title:** `CUTOVER: interpret reviewed-init-v1 genesis OTHER evidence`  
**ADR:** use `ADR-0023-reviewed-first-world-provenance-compatibility.md` if 0023 remains free after re-anchor  
**One-line mission:** Make the known #645 reviewed-first-world `D_0` provenance defect natively readable and exactly replayable inside DungeonMind without mutating immutable graph history, broadening normal provenance admission, or relying on Buddy-side semantic rewriting.

> Re-anchor before branching. If DungeonMind `main` moved from
> `bf40e933bdedf3cf08bb23a07a135958bdb7cc6b`, inspect every intervening
> commit and active PR lease. Disjoint docs are a normal re-anchor; overlap
> with the production/test lease below is a STOP and re-brief.
>
> This PR changes DungeonMind only. The Buddy producer correction and
> DungeonMind dependency pin are a separate successor PR.

---

## §1 Outcome

After this PR, DungeonMind recognizes one closed historical producer defect:

```text
#645 reviewed first-world initialization
        ↓
immutable zero-parent D_0
        ↓
historical graph evidence says OTHER
while the authoritative SourceArtifact is WORLDBUILDING
        ↓
DungeonMind recognizes only that named historical case
        ↓
normal WorldGraphProjectionService projection admits the legitimate facts
```

The stored `D_0` remains byte-for-byte immutable. Raw revision reads still expose
the historical `OTHER` evidence. Compatibility lives in DungeonMind above
`graph_scope`; Buddy never rewrites graph payloads.

The same PR makes a corrected reconstruction of the #645 command an exact replay
of the historical initialization using one shared replay identity:

```text
current command hash
+
optional #645-family OTHER-normalized historical hash
```

That same identity must govern application preflight, application lost-response
recovery, PostgreSQL under-lock replay, and in-memory under-lock replay. The
stored receipt and `command_sha256` are never rewritten.

This PR is independently successful when:

1. a #645-family historical `D_0` projects through `WorldGraphProjectionService`;
2. canonically identical inherited genesis evidence remains admissible on descendants;
3. arbitrary provenance mismatches still fail closed;
4. exact/correction replay is identical at all four replay seams, including a race;
5. existing adopted-world behavior is unchanged;
6. no Buddy code, graph mutation, durable schema migration, or generic source-repair API lands.

### What remains false after merge

- Buddy still produces the historical `OTHER` stamp for new first-world commands.
- Buddy still pins DungeonMind `bf40e933...`.
- Buddy #651 remains parked.
- D.2C4 remains blocked.
- D.3A/D.3B remain blocked.

---

## §2 Authority and anchors

Read these from the checked-out repositories before editing. Chat is not authority.

### DungeonMind — highest precedence

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `CONTRIBUTING.md`
4. Current implementation seams:
   - `src/dungeonmind/application/world_graph_projection.py`
   - `src/dungeonmind/application/graph_scope.py`
   - `src/dungeonmind/application/reviewed_world_initialization.py`
   - `src/dungeonmind/application/repositories.py`
   - `src/dungeonmind/infrastructure/postgres/reviewed_world_initialization.py`
   - `src/dungeonmind/infrastructure/memory/repositories.py`
   - `src/dungeonmind/contracts/reviewed_world_initialization.py`
   - `src/dungeonmind/contracts/evidence.py`
5. Accepted decisions:
   - `Docs/Decisions/ADR-0015-lossless-source-provenance-v2.md`
   - `Docs/Decisions/ADR-0019-atomic-existing-world-adoption-boundary.md`
   - `Docs/Decisions/ADR-0021-existing-world-adoption-repair.md`
   - `Docs/Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md`
6. Predecessor provider handoff:
   - `Docs/Handoffs/HANDOFF-cutover-reviewed-first-world-initialization.md`

### External accepted consumer-design evidence

DungeonMindBuddy `main` at predecessor merge:
`5ad992090c2e85d38784c888e4b870f5672bce8e`

Read:
`Docs/Plans/HANDOFF-CUTOVER-first-world-provenance-compatibility.md`

Accepted on Buddy #653 at head
`289201c9c60ec75c3acca998722be1a7d0600c43`,
Review Cycle 4 PASS-equivalent `5036593867`.

If the merged Buddy design conflicts with current checked-in DungeonMind
authority, DungeonMind authority wins and this slice STOPS for re-brief.

---

## §3 Scope

### In scope — production lease

Primary:

- `src/dungeonmind/application/world_graph_projection.py`
- `src/dungeonmind/application/graph_scope.py`
- `src/dungeonmind/application/reviewed_world_initialization.py`
- `src/dungeonmind/infrastructure/postgres/reviewed_world_initialization.py`
- `src/dungeonmind/infrastructure/memory/repositories.py`

Minimal wiring/export lease only when required:

- `src/dungeonmind/application/__init__.py`
- `src/dungeonmind/service/bootstrap.py`
- direct `WorldGraphProjectionService(...)` construction sites found by repository search

Documentation:

- `Docs/Decisions/ADR-0023-reviewed-first-world-provenance-compatibility.md`
- this CODE handoff if checked into the implementation branch
- `Docs/Roadmaps/ROADMAP.md` only if current DungeonMind process requires same-PR state sync

Focused tests:

- `tests/unit/test_world_graph_projection_service.py`
- `tests/unit/test_graph_scope_provenance.py`
- `tests/unit/test_graph_scope_v6.py`
- `tests/unit/test_reviewed_world_initialization.py`
- `tests/unit/test_reviewed_world_initialization_materialization_v6.py`
- `tests/integration/test_postgres_reviewed_world_initialization.py`
- `tests/integration/test_postgres_concurrency.py`
- adopted-world regression tests needed to prove no semantic drift

Narrowly named new test files are allowed when they make the proof clearer.

### Explicitly out of scope

Do not:

- modify DungeonMindBuddy;
- update Buddy's DungeonMind pin;
- fix Buddy's future producer here;
- resume/modify Buddy #651;
- mutate any published graph revision;
- add an in-place graph rewrite API;
- add generic `SourceRepository.update` / classification-repair APIs;
- reinterpret arbitrary `OTHER` as artifact domain;
- change adopted-world/Eldyrwild semantics;
- put repository I/O in `graph_scope`;
- accept a Buddy compatibility flag/hint;
- change public transport/API schemas;
- change durable reviewed-init contract versions;
- add a PostgreSQL migration;
- alter D&D profile/domain meaning;
- touch agent-harness behavior;
- optimize unrelated read paths.

Any such need is a STOP and re-brief.

---

## §4 Invariants that bind this slice

### 4.1 Historical producer-family predicate

A receipt `R` for projection, or command `C` for replay, belongs to the #645
producer family only when:

```text
source_plan_schema == "dmb_first_world_graph_plan_v1"

initialization_id matches:
^dmb:first-world:[0-9a-f]{64}$

actor == "live_control:graph_review_confirm"
```

Projection additionally requires:

```text
D_0.parent_revision_id is None
```

Eligible historical evidence additionally requires its authoritative SourceArtifact:

```text
source_domain == SourceDomain.WORLDBUILDING
source_domain_key == "worldbuilding"
```

Do not generalize this into any-reviewed-init compatibility.

### 4.2 Projection authority context belongs above `graph_scope`

Frozen shape:

```text
WorldGraphProjectionService
  + WorldGraphRepository
  + SourceRepository
  + ReviewedWorldInitializationRepository
  + GraphSnapshotReader
        ↓
normal exact revision resolution
        ↓
R = reviewed-init receipt for request.world_id
        ↓
if no R:
    no compatibility
else:
    D_0 = R.published_revision_id
    load + verify exact immutable D_0
    parse D_0 with the same GraphSnapshotReader semantics
    if R is #645 family:
        build immutable GenesisEvidenceCompatibility
    else:
        no compatibility
        ↓
project_scoped_snapshot(..., genesis_compatibility=context)
```

`graph_scope` remains pure: no repository reads, no Buddy hints, no mutation.

### 4.3 Receipt ↔ D0 integrity is provider integrity

When a reviewed-init receipt exists, verify at least:

- requested world == receipt world;
- `receipt.published_revision_id` exists in that world;
- returned revision identity is exact;
- graph schema matches receipt;
- graph payload SHA matches receipt;
- parent is `None`.

Missing/cross-world/wrong-schema/hash-mismatched/wrong-id/non-null-parent state is
`PersistenceIntegrityError`, not “no compatibility”, availability, or ordinary
provenance exclusion.

### 4.4 Historical evidence compatibility is content-bound

Only #645-family `D_0` evidence where:

```text
record.source_domain == OTHER
record.source_domain_key == "other"
matching SourceArtifact exists
artifact domain == WORLDBUILDING
artifact key == "worldbuilding"
```

enters compatibility.

Bind the entire canonical `D_0` evidence record, not just `evidence_ref_id`.

On descendant `D_n`:

```text
compatibility applies only if
canonical(E_current) == canonical(E_D0_eligible)
```

Same ID with any changed field gets no exception. A new descendant `OTHER` ID gets
no exception.

### 4.5 Compatibility never changes stored truth

Do not alter:

- `StoredGraphRevision.graph_payload`;
- parsed revision identity;
- revision ID;
- source records;
- persisted graph bytes.

Raw `get_revision(...D_0...)` must still expose historical `OTHER`.

### 4.6 One shared replay identity

Introduce an application-owned immutable value, conceptually:

```text
ReviewedWorldInitializationReplayIdentity
    current_command_sha256: str
    historical_other_normalized_sha256: str | None
```

`current_command_sha256` is the existing canonical hash.

Compute the optional historical digest only when the new command satisfies
#645-family clauses 1–3 and reverse-normalization is valid.

Reverse-normalization changes ONLY eligible v1 `EvidenceRef.source_domain` values
from the corrected SourceArtifact domain back to `SourceDomain.OTHER`.

Important: command-side `EvidenceRef` has `source_domain`; it does NOT have
`source_domain_key`.

Eligibility requires:

- unambiguous command-owned `SourceArtifactV2`;
- corrected evidence domain equals the artifact's non-OTHER domain;
- this historical family is worldbuilding;
- complete source closure.

If ambiguous/ineligible, no historical digest is produced.

Do not persist the historical digest. First insert stores the current hash.

A receipt matches only when initialization ID matches and its stored
`command_sha256` equals the current hash, OR the optional historical hash and
the receipt is also #645-family.

Any other command delta remains `IdempotencyConflictError`.

### 4.7 All four replay seams use the same identity

No single-hash reviewed-init replay path may remain:

1. application preflight;
2. application exception/lost-response recovery;
3. PostgreSQL under-lock replay after `lock_world`;
4. in-memory under-lock replay.

A corrected retry racing/arriving against a historical commit must converge on
the stored receipt under serialization, not conflict.

Do not duplicate the normalization algorithm across adapters.

### 4.8 Existing semantics remain the default

Without valid #645 compatibility:

- session-recap vs worldbuilding mismatch still rejects;
- non-family reviewed-init OTHER rejects;
- family + non-worldbuilding rejects;
- adopted Eldyrwild behavior is unchanged;
- PLAYER remains fail-closed;
- source/provenance freshness semantics are unchanged.

---

## §5 Work plan

### Step 0 — Re-anchor and lease check

```bash
git fetch origin
git switch main
git pull --ff-only
git rev-parse HEAD
git status --short
```

Record exact base SHA. Inspect open PRs/changed paths and confirm ADR-0023 is free.

At dispatch the only observed open DungeonMind PR was #42, docs-only `AGENTS.md`,
and disjoint. Recheck.

```bash
git switch -c cutover/reviewed-init-v1-genesis-provenance
```

Overlapping current-main work is a STOP.

### Step 1 — Add focused failing characterization/acceptance tests

Lock:

- #645-family D0 currently excluded due to OTHER-vs-worldbuilding;
- raw D0 remains OTHER;
- non-family rejection;
- family + non-worldbuilding rejection;
- identical descendant compatibility;
- same-ID changed-record descendant rejection;
- receipt/D0 integrity failures;
- ordinary exact replay;
- historical correction replay;
- any-other-delta replay conflict.

Use synthetic fixtures/builders only.

### Step 2 — Implement shared replay identity

In `application/reviewed_world_initialization.py`:

- add pure replay identity builder;
- centralize current + optional historical hashes;
- centralize receipt matching;
- update application preflight and recovery.

Then update in-memory and PostgreSQL under-lock replay to consume the same identity.

No durable contract field.

### Step 3 — Prove replay under both adapters

Unit/in-memory:

- exact replay;
- historical normalized replay;
- changed bytes conflict;
- non-family cannot use historical digest.

PostgreSQL:

- same cases against real rows;
- receipt hash unchanged;
- corrected retry race converges under lock.

Required PG evidence may not skip.

### Step 4 — Add immutable `GenesisEvidenceCompatibility`

Application-layer, storage-neutral, content-bound.

Extend `project_scoped_snapshot` / evidence resolution only enough to accept this
optional pure policy input. Ordinary no-context semantics remain unchanged.

### Step 5 — Resolve compatibility in `WorldGraphProjectionService`

Add `ReviewedWorldInitializationRepository` as authority dependency.

Resolve/verify receipt + exact immutable D0, construct compatibility only for the
named family, then scope normally.

Do not mutate parsed-revision cache entries. Compatibility is request/source
authority context, not replacement graph bytes.

Update constructor call sites minimally.

### Step 6 — Prove projection through the service boundary

Required:

- `WorldGraphProjectionService.project(D_0)` admits historical fact;
- raw D0 still OTHER;
- identical descendant admits;
- changed descendant record rejects;
- non-family and non-worldbuilding cases reject;
- broken receipt/D0 correspondence raises `PersistenceIntegrityError`;
- session-recap/worldbuilding mismatch still rejects.

Direct `graph_scope` helper tests alone are not owning proof.

### Step 7 — Run adopted-world regressions

Existing Eldyrwild/adoption provenance behavior must remain unchanged.

### Step 8 — Write ADR-0023

Create:

`Docs/Decisions/ADR-0023-reviewed-first-world-provenance-compatibility.md`

Record:

- #645 historical defect;
- closed DungeonMind interpretation;
- exact producer-family predicate;
- service-owned context above pure `graph_scope`;
- full-record descendant binding;
- dual-hash replay at all four seams;
- immutable D0 and receipt hash;
- future Buddy producer successor;
- rejected Buddy rewrite / D0 mutation / global trust-artifact / any-reviewed-init
  waiver / single-layer replay normalization;
- eventual removal requires explicit historical-support evidence.

### Step 9 — Full gates and handback

Run §6 exactly. Record base/head, changed paths, test results, PG proof, ADR, any
deviation, what remains false, and the Buddy producer successor.

Do not start Buddy work from this branch.

---

## §6 Acceptance gates

### Focused unit gate

```bash
uv run pytest   tests/unit/test_reviewed_world_initialization.py   tests/unit/test_reviewed_world_initialization_materialization_v6.py   tests/unit/test_world_graph_projection_service.py   tests/unit/test_graph_scope_provenance.py   tests/unit/test_graph_scope_v6.py
```

Expected: PASS, zero required skips.

### Required real-PostgreSQL witness

With `DUNGEONMIND_DATABASE_URL` configured:

```bash
uv run pytest -m integration   tests/integration/test_postgres_reviewed_world_initialization.py   tests/integration/test_postgres_concurrency.py
```

Run the adopted-world cohort touched by the implementation:

```bash
uv run pytest -m integration   tests/integration/test_postgres_existing_world_adoption.py   tests/integration/test_postgres_existing_world_adoption_repair.py   tests/integration/test_postgres_eldyrwild_existing_world_adoption.py
```

Expected: PASS; required compatibility/replay tests execute; zero required skips.

If PostgreSQL is unavailable, the PR is not merge-ready.

### Full repository gates

```bash
uv run ruff check .
uv run pyright
uv run pytest
uv run pytest -m conformance
uv run pytest -m integration
```

All must pass. Required compatibility witnesses may not skip.

### Proof ledger

#### Projection

- [ ] #645-family D0 + historical OTHER + WORLDBUILDING artifact admits through `WorldGraphProjectionService.project`.
- [ ] Raw D0 still exposes OTHER.
- [ ] Wrong producer schema rejects.
- [ ] Wrong actor rejects.
- [ ] Wrong initialization-id form rejects.
- [ ] Family + non-worldbuilding rejects.
- [ ] Canonically identical descendant admits.
- [ ] New descendant OTHER ID rejects.
- [ ] Same genesis ID + changed canonical field rejects.
- [ ] Missing D0 → `PersistenceIntegrityError`.
- [ ] Cross-world/wrong identity → `PersistenceIntegrityError`.
- [ ] Wrong graph schema → `PersistenceIntegrityError`.
- [ ] Payload SHA mismatch → `PersistenceIntegrityError`.
- [ ] Non-null genesis parent → `PersistenceIntegrityError`.
- [ ] session_recap/worldbuilding mismatch still rejects.
- [ ] adopted-world/Eldyrwild behavior unchanged.

#### Replay

- [ ] Current-hash replay succeeds at application preflight.
- [ ] Current-hash replay succeeds at application recovery.
- [ ] Current-hash replay succeeds PostgreSQL under lock.
- [ ] Current-hash replay succeeds in-memory under lock.
- [ ] Historical OTHER-normalized replay succeeds at all four seams.
- [ ] Stored `command_sha256` remains unchanged.
- [ ] Historical digest is not persisted.
- [ ] First insert stores only current hash.
- [ ] Corrected retry against committed historical receipt converges under lock.
- [ ] Any other semantic delta conflicts.
- [ ] Ambiguous/ineligible source closure cannot create historical digest.
- [ ] Non-family command cannot use historical replay identity.

---

## §7 Stop conditions

STOP and report if:

1. current DungeonMind main overlaps leased production/test paths materially;
2. ADR-0023 is occupied — re-anchor and allocate next free, do not overwrite;
3. compatibility requires recovering the original historical command;
4. compatibility requires a Buddy request hint;
5. `graph_scope` needs repository/database I/O;
6. published D0 bytes or revision identity would need mutation;
7. durable reviewed-init contract versions must change;
8. a DB migration is needed;
9. a generic source-update/repair API is needed;
10. adopted-world/Eldyrwild semantics must change;
11. arbitrary reviewed-init OTHER would become admissible;
12. replay identity cannot be shared at all four seams;
13. PG concurrency still permits corrected retry → idempotency conflict;
14. tests only pass by weakening existing fail-closed provenance;
15. `src/dungeonmind` would need a Buddy/sibling-repo import;
16. public transport/API changes are required;
17. checked-in DungeonMind authority contradicts the accepted #653 design.

A STOP is a valid handback. Do not solve a new architecture problem inside this PR.

---

## §8 Handback requirements

### Repository identity

```text
repo:
branch:
base SHA:
head SHA:
PR number:
PR status:
ADR:
```

Do not invent merge SHA. Do not merge unless explicitly instructed.

### Cumulative diff

List every changed path as:

```text
PRODUCTION
TEST
ADR/DOC
WIRING
```

Justify any path outside §3.

### Nano-commit story

Suggested:

```text
1. CUTOVER: add reviewed-init dual replay identity + unit proofs
2. CUTOVER: interpret content-bound #645 genesis provenance in projection
3. CUTOVER: prove postgres replay/concurrency + adopted regressions
4. DOCS: record ADR-0023 and handback evidence
```

Equivalent smaller commits are fine; avoid one opaque commit.

### Decisions ledger

For any choice not mechanically dictated here:

```text
question:
evidence:
decision:
rejected alternatives:
consequences:
reversal path:
```

### Verification ledger

Record exact commands/results for:

- focused unit tests;
- focused PostgreSQL tests;
- adopted regressions;
- `uv run ruff check .`;
- `uv run pyright`;
- `uv run pytest`;
- `uv run pytest -m conformance`;
- `uv run pytest -m integration`.

Required skips are blockers.

### What remains false

```text
Buddy new first-world producer is NOT corrected by this PR.
Buddy DungeonMind pin is NOT updated by this PR.
Buddy #651 is NOT resumed by this PR.
D.2C4 is NOT dispatched.
D.3A/D.3B are NOT dispatched.
No historical D0 bytes were rewritten.
No generic provenance waiver was created.
```

### Named next slice

Only after this DungeonMind PR merges and its exact merge SHA is known:

```text
DungeonMindBuddy CODE
branch: cutover/first-world-provenance-producer

mission:
- stamp future first-world v1 EvidenceRef.source_domain from the mapped
  SourceArtifact domain instead of OTHER;
- pin DungeonMind to the accepted compatibility merge;
- prove a new D0 is born natively projectable;
- prove exact retry of an old #645 world remains already_initialized.
```

After that Buddy producer/pin PR merges, re-anchor parked Buddy #651 and submit
its next distinct head as **Review Cycle 4**, restoring the original admitted
D0 projection/search/get-object witness.

---

## PR body seed

```markdown
## Handoff pointer

- Workstream: CUTOVER / D.2C2 provenance compatibility — CODE
- Flow: CUTOVER
- Direction: CODE → REVIEW
- Handoff: `Docs/Handoffs/HANDOFF-cutover-reviewed-init-v1-genesis-provenance.md`
- Exact base: `<sha>`
- Predecessor design: DungeonMindBuddy #653 merge `5ad992090c2e85d38784c888e4b870f5672bce8e`
- Accepted design head: `289201c9c60ec75c3acca998722be1a7d0600c43`
- Design review: Cycle 4 PASS-equivalent `5036593867`
- Parked consumer: DungeonMindBuddy #651 at `cf453078a5c1950ec5f23a5d5b99001ee9e456db`
- ADR: `ADR-0023-reviewed-first-world-provenance-compatibility.md`

## Outcome

Interpret only the named #645 reviewed-first-world historical genesis OTHER
provenance inside DungeonMind native projection, preserving immutable D0 bytes
and ordinary fail-closed provenance. Add one shared dual-hash replay identity so
corrected retries converge on the original receipt at application and under-lock
repository seams.

## Evidence required to merge

- [ ] #645-family D0 projects through WorldGraphProjectionService
- [ ] raw D0 remains OTHER
- [ ] non-family and non-worldbuilding mismatches still reject
- [ ] descendant compatibility is full-record content-bound
- [ ] broken receipt/D0 correspondence is PersistenceIntegrityError
- [ ] exact + historical correction replay pass at all four seams
- [ ] corrected retry concurrency converges under PostgreSQL lock
- [ ] adopted-world/Eldyrwild behavior unchanged
- [ ] ruff / pyright / unit / conformance / integration pass
- [ ] required PostgreSQL witness executed with zero required skips

## What remains false

- Buddy producer correction is not in this PR.
- Buddy DungeonMind pin is not updated in this PR.
- Buddy #651 remains parked.
- D.2C4/D.3 remain blocked.
```
