# HANDOFF — K0.2: golden semantic witness

**Created:** 2026-08-31  
**Status:** ACTIVE  
**Repository:** `Drakosfire/DungeonMind`  
**Handoff branch:** `kernel/k0-golden-semantic-witness-handoff`  
**Intended implementation branch:** `kernel/k0-golden-semantic-witness`  
**Stacked preparation anchor:** approved PR #48 head `3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1`  
**Approved K0.1 review:** `5070822476` — PASS / merge-ready  
**External consumer anchor:** DungeonMindBuddy `a9d4c61d04f2a4a5f92cb6947442d8173079454c`, pinned to DungeonMind `5ca5d688612349034f8ca490d465af166d883e6e`  
**Predecessor:** PR #48 / `Docs/Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md` / `Docs/Reports/K0-surface-inventory.json`  
**One-line mission:** Freeze the current surviving World authority semantics into a deterministic, adapter-checkable golden witness so K1 demolition and later K2/K6 work can prove semantic parity instead of relying on test-suite familiarity.

---

## §1 Outcome

K0.2 lands **no DungeonMind runtime behavior change**. It lands one deterministic semantic oracle for the World authority contract that is small enough to understand, broad enough to catch dangerous drift, and reusable unchanged after demolition and refactor.

The witness must answer one question:

> For the same exact governed world state and request, did DungeonMind preserve the same authority meaning?

It must therefore capture three things separately:

```text
semantic identity / normalized result
observation-only metadata
wall-clock / performance data
```

Only the first category participates in the golden equality contract. Values such as `projected_at`, generated timestamps, local paths, wall-clock durations, database connection details, and other observation-only fields must never make the semantic witness change.

The canonical checked-in artifact should be generated from the in-memory reference adapters for deterministic, fast reproduction. A PostgreSQL integration lane must execute the same scenario and prove the same aggregate semantic digest. PostgreSQL is parity evidence, not a second competing golden file.

Expected artifacts:

```text
scripts/k0_semantic_witness.py
Docs/Reports/K0-golden-semantic-witness-v1.json
Docs/Reports/REPORT-2026-08-31-k0-golden-semantic-witness.md
tests/witness/k0_semantic_fixture.py              # or equivalent small fixture module
tests/unit/test_k0_semantic_witness.py
tests/integration/test_k0_semantic_witness_postgres.py  # or equivalent marked integration lane
```

Historical schema/adoption fixtures may live under a clearly named `tests/fixtures/k0_semantic_witness/` directory if existing checked-in fixtures are not already reusable. Do not duplicate large fixtures merely to satisfy naming symmetry.

The machine artifact schema should be explicitly versioned, for example:

```text
dm_k0_semantic_witness_v1
```

This PR is complete only when the checked-in witness can later serve as the K2.5 equality oracle without reinterpretation.

### Implementation-base rule

PR #48 must land before K0.2 implementation begins.

This handoff branch was prepared from the approved PR #48 head because K0.1 was not yet merged when the handoff was written. Before the first implementation commit:

1. resolve the actual landed K0.1 commit on `steward/post-cutover-library-critique`;
2. move/rebase/reset `kernel/k0-golden-semantic-witness` so its implementation base is that landed K0.1 state;
3. record the actual base SHA in the PR and final report;
4. if PR #48 changes after review `5070822476`, re-read the K0.1 report/ledger and treat the changed head as a new predecessor state.

Do not implement K0.2 against the pre-K0.1 stewardship base `84a4479494a37d8b5bd550465d17ff29f0e359ec`.

---

## §2 Authority and anchors

Read these in order before changing anything:

1. `Docs/Architecture/AUTHORITY.md`
   - checked-in contracts/code/accepted ADRs/architecture outrank historical reports;
   - durable exact-world state is authority;
   - Buddy is current-consumer evidence, not semantic authority;
   - mutable source/evidence state may affect a read even when graph revision identity is unchanged.
2. `Docs/Architecture/ARCHITECTURE.md`
   - §3 governing invariants;
   - §4 current public read/write capability boundary;
   - §5 persistence/authority;
   - §7 read architecture and cache-safety rule;
   - §8 ownership map.
3. `Docs/Roadmaps/ROADMAP.md`
   - K0.2 minimum read/write/historical witness matrix;
   - K1 is downstream demolition;
   - K2.5 later requires post-demolition witness equality.
4. K0.1 evidence at the landed PR #48 state:
   - `Docs/Inventory/K0-dispositions.toml`
   - `Docs/Reports/K0-surface-inventory.json`
   - `Docs/Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md`
   K0.2 covers the **surviving World authority contract**, not founding runtime already classified for later demolition.
5. Publication/source/history ADRs that bind the witness:
   - `Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md`
   - `Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md`
   - `Docs/Decisions/ADR-0014-assertion-scoped-world-graph-v4.md`
   - `Docs/Decisions/ADR-0015-lossless-source-provenance-v2.md`
   - `Docs/Decisions/ADR-0018-relationship-endpoint-aspects-v6.md`
   - `Docs/Decisions/ADR-0019-atomic-existing-world-adoption-boundary.md`
   - `Docs/Decisions/ADR-0020-v6-governed-review-publication.md`
   - `Docs/Decisions/ADR-0021-existing-world-adoption-repair.md`
   - `Docs/Decisions/ADR-0023-reviewed-first-world-provenance-compatibility.md`
6. `Docs/Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md`
   - MindTurn/agent/context behavior is not part of this golden equality set unless a surviving World operation itself depends on it, in which case stop and reconcile with K0.1 rather than silently blessing it.
7. Current application services/contracts and their existing tests for:
   - World graph projection/retrieval/read context;
   - source/evidence/anchor behavior;
   - reviewed first-world initialization;
   - contribution review/materialization/publication;
   - publication recovery/idempotency;
   - existing-world adoption/correspondence/repair;
   - `VersionedUnionGraphSnapshotReader` and every still-required stored graph version.

### Exact-anchor rule

The golden file freezes semantics of one exact K0.2 implementation base. The generated artifact and report must record:

```text
dungeonmind_base_sha
k0_inventory_schema = dm_k0_surface_inventory_v1
k0_inventory_digest
witness_schema = dm_k0_semantic_witness_v1
fixture_digest
normalization_policy_digest
```

Use digests over checked-in fixture/policy inputs, not the mutable commit that contains the generated output. Do not recreate K0.1's self-referential artifact problem.

---

## §3 Scope

### In scope

#### A. One deliberately small governed synthetic world

Build one canonical synthetic scenario through current DungeonMind contracts/services. It is not a product demo and does not need fantasy prose. Prefer obvious stable IDs and explicit values over random UUIDs.

The minimum shape should include:

```text
one world
campaign A
campaign B
world-owned knowledge
campaign-A knowledge visible to PLAYER
campaign-A knowledge visible only to GM
campaign-B knowledge
at least one relationship chain long enough for depth-1 and depth-2 traversal
aliases / searchable labels
object, relationship, and assertion evidence
at least one source anchor with exact source revision / locator identity
```

The fixture must be rich enough that a PLAYER depth-2 traversal/search cannot accidentally recover GM-only material, and that cross-campaign/world-owned scope actually returns a meaningfully different result from campaign-only scope.

Use deterministic IDs, deterministic ordering, and explicit source/evidence identities. Do not depend on random factories whose seed or implementation could become part of the oracle accidentally.

#### B. Canonical read witness

The checked-in witness must include normalized results for all roadmap-required read behaviors:

```text
read.head_projection
read.exact_historical_revision
read.exact_object
read.deterministic_search
read.neighborhood.depth_1
read.neighborhood.depth_2
read.evidence
read.source_anchor.emit
read.source_anchor.revalidate
scope.gm_campaign
scope.player_campaign
scope.world_owned
scope.cross_campaign
failure.missing_object
failure.missing_revision
failure.missing_head
failure.provenance_invalid_fail_closed
```

Add a separate operation only where current contracts expose a materially distinct authority rule that would otherwise be lost.

For successful reads, preserve normalized semantic content and deterministic ordering, not just a hash. The fixture is intentionally small so a reviewer can understand what changed when a digest changes.

For failures, normalize to stable public semantics such as exception/error type/code and bound identity fields. Do not snapshot full prose exception messages unless message text is itself an accepted contract.

#### C. Canonical write/governance witness

Exercise the current governed write path, not direct graph mutation, for:

```text
write.reviewed_first_world_initialization
write.exact_parent_publication
write.stale_parent_rejection
write.exact_replay_idempotency
write.outcome_unknown_recovery
write.correction_or_retraction
write.source_evidence_binding_integrity
```

The witness must record the semantic outcome of each operation, including the relevant immutable revision/head identity relationships.

Do not require every write case to occur in one linear scenario if current recovery/failure-injection seams are cleaner as isolated sub-scenarios. They must still share one normalization/output format.

For `outcome_unknown_recovery`, reuse the existing accepted failure/recovery seam from publication tests. Do not add production-only fault injection just to make the witness convenient.

For correction/retraction, freeze **whatever is actually supported at the K0.2 base**. Do not invent a cleaner future operation model.

#### D. Source/provenance freshness witness

At least one case must prove the current rule that graph revision identity alone does not guarantee admissibility when live source/provenance state makes the evidence chain invalid.

It is acceptable for fixture setup to seed a deliberately invalid source/evidence state through test repositories where no public mutation API exists. The operation under witness must still use the normal public read path and fail closed.

The golden result must prove that excluded knowledge stays excluded; it must not merely record an internal validation warning.

#### E. Historical graph-schema compatibility lane

Freeze semantic decode/read results for every stored graph schema version still classified by K0.1 as required historical compatibility.

At the current roadmap state this means proving the still-required v1-v6 reader/dispatch family. Prefer existing checked-in payload fixtures. If new fixtures are necessary, make each one the smallest valid artifact that exercises the actual reader and record its exact source/derivation in the report.

Each historical case should capture:

```text
stored_schema_version
reader/dispatch path
normalized semantic result
semantic_sha256
```

Do not rewrite old payloads into current schema and then claim the old reader was tested.

#### F. Existing-world adoption / repair / reviewed-first-world compatibility

K0.2 must preserve the living historical obligations called out by the roadmap and K0.1:

- existing-world adoption receipt/genesis reconstruction;
- accepted adoption repair lineage;
- reviewed-first-world provenance compatibility.

Use checked-in exact fixtures/evidence already present in the repository where available.

**Do not connect to or mutate the live Eldyrwild authority database.**

If the repository does not currently contain enough checked-in material to prove the required Eldyrwild adoption/repair/reviewed-init lineage, stop. Do not create an "Eldyrwild-like" synthetic fixture and mark the roadmap requirement satisfied. Hand back the exact missing artifact/evidence and propose a separate sanitized disposable-fixture extraction slice under steward approval.

#### G. Semantic normalization policy

Define one explicit normalization function/policy shared by all witness cases.

It must classify fields into at least:

```text
SEMANTIC
OBSERVATION_ONLY
FORBIDDEN_NONDETERMINISM
```

Examples that should normally be `OBSERVATION_ONLY` or omitted from the golden semantic payload:

- `projected_at` / generated timestamps;
- wall-clock duration;
- tracing/span IDs;
- local paths;
- connection strings / ports;
- process IDs;
- machine-specific metadata.

Examples that are semantic and must remain:

- world/campaign/scope/admissibility identity;
- exact graph revision / parent relationship where exposed by contract;
- object/assertion/relationship identities;
- visible semantic values;
- source/evidence identity and validity outcome;
- deterministic result ordering where ordering is contractual;
- truncation/coverage/fail-closed state;
- publication/recovery disposition.

Do not solve nondeterminism by stripping a field until the test passes. Every excluded field requires a reason in the normalization policy/report.

#### H. Machine artifact

The canonical JSON should be generated-only and deterministically sorted. A recommended shape is:

```text
schema
inputs
normalization_policy
fixture
operations[]
  id
  family
  request_identity
  status
  semantic_result
  semantic_sha256
historical_compatibility[]
aggregate_semantic_sha256
```

The aggregate digest must be calculated only from normalized semantic records in stable operation-ID order.

The artifact must contain no wall-clock timestamp and no absolute local path.

#### I. In-memory canonical + PostgreSQL semantic parity

The checked-in artifact is generated from the in-memory reference adapters.

A disposable PostgreSQL test lane must:

1. migrate a fresh database;
2. execute the same forward witness scenario through PostgreSQL repositories;
3. normalize the results with the exact same policy;
4. assert the aggregate semantic digest equals the checked-in canonical digest for the operations that are adapter-neutral.

If a PostgreSQL-only observation is useful, report it separately. Do not add it to semantic equality merely because it is observable.

Historical compatibility cases that are pure reader/codec fixtures do not need to be duplicated through PostgreSQL unless the durable-store path itself is part of the semantic obligation.

#### J. Review telemetry

Record formal review cycles in the report.

Required adversarial review lenses:

1. **Coverage / false-negative review** — map every K0.2 roadmap bullet to a witness operation or a documented stop/blocker; inspect whether PLAYER/search/traversal/provenance failure cases can leak excluded material.
2. **Normalization / drift review** — prove a semantic mutation changes the witness while an observation-only mutation does not; inspect every stripped field for accidental semantic loss.
3. **History / adapter review** — challenge historical fixture authenticity and verify in-memory/PostgreSQL semantic parity where required.

The number of cycles is telemetry, not a target. Record actual cycles completed.

### Out of scope (falsification)

This PR must **not**:

- change any production/runtime behavior in `src/`;
- repair the known `benchmark-smoke` constructor defect;
- optimize reads/writes;
- add caches/indexes;
- redesign storage;
- delete or deprecate MindTurn/agents/semantic runtime;
- start K1 demolition;
- change graph/source/review/profile contracts to make the witness prettier;
- change error semantics because an existing failure is awkward to normalize;
- replace current publication/recovery behavior with a new abstraction;
- redesign `SemanticProfile`;
- introduce Authority/Graph/World/Rules package boundaries;
- create `KnowledgeSpace` or a generic knowledge root;
- query or mutate live Eldyrwild;
- copy live private campaign content into fixtures;
- make Buddy part of semantic authority;
- repin or modify DungeonMindBuddy;
- turn performance timing into a golden semantic assertion.

If capturing the witness requires a runtime behavior change, stop and report the missing proof seam or baseline defect instead of silently fixing production code inside K0.2.

---

## §4 Invariants that bind this slice

Carry forward the architecture invariants exactly as semantic obligations where applicable:

1. **One World Graph per world.** Campaign is scope, never a second graph.
2. **Published revisions are immutable.** Head advances explicitly by CAS; rollback/recovery never rewrites history.
3. **Evidence is part of knowledge validity.** Invalid evidence chains fail admission.
4. **Reads are explicit.** World, selected revision, scope, and admissibility are part of request meaning.
5. **PLAYER fails closed.** Search, traversal, anchors, and diagnostics may not recover excluded or scope-unknown material.
6. **Retrieval never becomes authority.** Ranking/search narrows admitted knowledge only.
7. **Durable writes are governed.** Candidate generation is not publication; exact content and expected parent remain bound.
8. **Profiles own domain meaning.** The witness must not make generic DungeonMind import `dungeonmind_dnd` as a new dependency.
9. **Clients are replaceable.** Buddy may be cited as current-consumer evidence but is not the golden semantic oracle.
10. **Performance may not change meaning.** K0.2 records meaning; K0.3 records cost.

Slice-local invariants:

- **Freeze, do not improve:** surprising current behavior is evidence to inspect, not permission to silently redefine semantics.
- **Human-readable before clever:** the fixture should be small enough that a reviewer can understand a changed semantic record.
- **One normalization policy:** no operation-specific ad hoc field stripping to force parity.
- **Error semantics are semantics:** normalize stable error identity, do not collapse every failure to `ERROR`.
- **Deterministic inputs:** IDs, source revisions, ordering, and fixture payloads are explicit and checked in.
- **Canonical artifact is generated:** never hand-edit the JSON golden.
- **Adapter equality is semantic equality:** Postgres may differ in internal rows/IDs only where those values are not part of public semantic identity.
- **Historical evidence must be authentic:** a synthetic modern payload cannot stand in for a required historical reader/adoption obligation.
- **No runtime diff:** `src/`, Alembic/migrations, dependency manifests, and lockfile remain unchanged from the K0.2 implementation base.

---

## §5 Work plan

### 1. Re-anchor after PR #48 lands

Before implementation:

- resolve landed PR #48 commit and stewardship head;
- re-anchor `kernel/k0-golden-semantic-witness` to that exact state;
- record base SHA;
- run K0.1 generator/validator once and confirm the landed ledger/report are internally reproducible.

Stop if K0.1 changed materially after review `5070822476`.

### 2. Inventory existing semantic proof before writing new fixtures

Map current tests/fixtures to every required K0.2 operation.

Create a small coverage ledger in the report or test data:

```text
operation_id
existing proof source
new witness case required? yes/no
fixture source
```

Reuse accepted test fixtures where they are already deterministic and semantically legible. Do not create parallel fixture universes without need.

Specially inspect:

- World projection/retrieval tests;
- source provenance/anchor tests;
- publication/CAS/recovery tests;
- reviewed-first-world initialization tests;
- versioned snapshot reader tests;
- adoption/correspondence/repair tests.

### 3. Define the witness schema and normalization policy first

Implement the smallest reusable normalization layer before building the large operation matrix.

Unit tests must prove at least:

- deterministic canonical JSON ordering;
- observation-only timestamp differences do not change semantic digest;
- a semantic value change does change the operation and aggregate digests;
- full error prose is not accidentally the equality key unless deliberately declared semantic;
- duplicate operation IDs are rejected;
- missing required operation IDs are rejected;
- absolute paths / DSNs / wall-clock fields are rejected from checked-in semantic payload.

Do not add a general-purpose snapshot-testing framework.

### 4. Build the forward governed synthetic fixture

Create the smallest world/campaign/source/evidence/revision scenario that covers §3A-D.

Prefer one fixture builder parameterized by repository bundle/adapter rather than two independently authored memory/Postgres scenarios.

Fixture construction should use current governed APIs for initialization/publication wherever the operation itself is under witness. Test-only direct seeding is acceptable only for preconditions that cannot be reached publicly, such as deliberately corrupt/invalid provenance used to prove fail-closed reads.

### 5. Capture read operations

Run the exact read matrix and serialize normalized semantic records.

For PLAYER cases, explicitly assert that known GM-only IDs/labels/evidence are absent from:

- projection;
- search;
- depth-1 neighborhood;
- depth-2 neighborhood;
- source anchors/diagnostics where applicable.

Do not rely solely on aggregate counts for secrecy proof.

### 6. Capture write/governance operations

Exercise reviewed initialization, exact-parent publication, stale-parent rejection, replay/idempotency, recovery, correction/retraction, and source/evidence binding.

The golden should make parent/head lineage visible enough that later mutation/rewrite bugs are obvious.

Reuse existing recovery failure injection. If the current recovery proof requires changing production code to expose a seam, stop.

### 7. Capture historical compatibility

Run every required stored graph version through the real current dispatch/reader path and record normalized results.

Then prove the checked-in adoption/repair/reviewed-first-world obligations.

If exact Eldyrwild historical fixture evidence is absent, trigger the stop condition from §3F rather than weakening the roadmap requirement.

### 8. Generate and lock the canonical artifact

Example command shape:

```bash
uv run python scripts/k0_semantic_witness.py \
  --adapter memory \
  --output Docs/Reports/K0-golden-semantic-witness-v1.json
```

A second run to a temporary path must be byte-identical:

```bash
uv run python scripts/k0_semantic_witness.py \
  --adapter memory \
  --output /tmp/k0-golden-semantic-witness-v1.json
cmp Docs/Reports/K0-golden-semantic-witness-v1.json \
    /tmp/k0-golden-semantic-witness-v1.json
```

The generator should fail closed on wrong base/schema/fixture inputs rather than silently regenerating a different golden from arbitrary code state.

### 9. Prove PostgreSQL semantic parity

Use a disposable database and the project's normal integration setup.

The integration test must compare normalized semantic digest against the checked-in canonical witness, not against a second hand-maintained expected payload.

Where PostgreSQL behavior is intentionally adapter-specific, document why it is excluded from semantic parity rather than weakening the shared scenario silently.

### 10. Write the report

The report must include:

1. exact implementation base SHA and K0.1 predecessor identity;
2. witness schema and fixture/normalization digests;
3. operation coverage matrix;
4. short description of the synthetic world shape;
5. read semantic digest table;
6. write/governance semantic digest table;
7. historical schema/adoption/reviewed-init evidence table;
8. in-memory vs PostgreSQL parity result;
9. normalization exclusions with rationale;
10. formal review-cycle telemetry;
11. baseline defects/unknowns discovered but not repaired;
12. explicit statement that this witness becomes the inherited K2.5 oracle.

### 11. Atomic roadmap update only after proof exists

After every acceptance gate is satisfied:

- update only the K0.2 roadmap disposition to `DONE` / equivalent landed wording;
- link the witness JSON/report;
- leave K0.3 as next;
- do not mark K0 complete until K0.3 is also complete;
- do not advance K1 merely because K0.2 passed.

---

## §6 Acceptance gates

### A. No runtime/schema/dependency change

Against the actual landed K0.1 implementation base:

```bash
git diff --exit-code <K0_2_BASE_SHA> -- \
  src migrations alembic alembic.ini pyproject.toml uv.lock
```

Expected: no diff.

### B. Deterministic golden generation

```bash
uv run python scripts/k0_semantic_witness.py \
  --adapter memory \
  --output /tmp/k0-golden-semantic-witness-v1.json
cmp Docs/Reports/K0-golden-semantic-witness-v1.json \
    /tmp/k0-golden-semantic-witness-v1.json
```

Expected: byte-identical.

Run from a second clean checkout/worktree if practical. The digest must not contain absolute checkout paths or environment-specific values.

### C. Focused witness tests

```bash
uv run pytest \
  tests/unit/test_k0_semantic_witness.py \
  tests/unit/test_import_boundaries.py
```

Expected: green.

The focused suite must include tests proving:

- required operation coverage;
- deterministic normalization;
- semantic mutation changes digest;
- observation-only mutation does not change digest;
- PLAYER hidden material remains absent;
- generated artifact matches checked-in golden.

### D. Core quality gates

```bash
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
```

Expected: green except only already-recorded baseline failures that demonstrably predate K0.2. Do not normalize a new failure as baseline.

### E. Disposable PostgreSQL witness parity

Use the repository's normal disposable integration environment:

```bash
uv sync --locked --extra postgres --extra api
alembic upgrade head
uv run pytest tests/integration/test_k0_semantic_witness_postgres.py -m integration
uv run pytest -m integration
```

Expected:

- migrations green;
- focused PostgreSQL witness green;
- aggregate adapter-neutral semantic digest equals the checked-in in-memory canonical digest;
- normal integration suite green.

Equivalent existing integration-file placement is acceptable if the command is updated exactly in the report.

### F. Historical compatibility gate

The report/test output must name each required stored graph schema and prove its real reader path executed.

Acceptance also requires checked-in proof for:

- existing-world adoption reconstruction;
- accepted repair lineage;
- reviewed-first-world provenance compatibility.

If the required Eldyrwild historical fixture is not available without live-data access, this gate is **BLOCKED**, not waived.

### G. Golden self-check

The generator/validator must reject at least:

- wrong witness schema;
- wrong K0.2 base/input digest;
- duplicate operation IDs;
- missing required operation ID;
- mismatched per-operation digest;
- mismatched aggregate digest;
- forbidden nondeterministic field/path;
- malformed historical compatibility entry.

### H. Known CI baseline handling

K0.1 recorded the pre-existing `benchmark-smoke` failure caused by `WorldGraphProjectionService` constructor drift in `benchmarks/world_graph_reads.py`.

K0.2 must:

- re-confirm that failure is unchanged if CI still runs it;
- continue recording it as the same pre-existing baseline defect;
- not repair it in this PR;
- treat any new/factually different CI failure as a blocker.

### I. Formal review

Minimum review lenses from §3J must be completed and the actual cycle count recorded.

The final handback must include the final PASS review identifier.

---

## §7 Stop conditions

Stop and hand back evidence instead of proceeding if any of the following occurs:

1. PR #48 lands in a state materially different from approved head `3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1` without re-reviewing K0.1 evidence.
2. Capturing the witness requires a production/runtime behavior change in `src/`.
3. A roadmap-required behavior has no stable current semantic meaning and existing contracts/tests disagree about the expected result.
4. A semantic result cannot be made deterministic without stripping a field that appears to carry authority meaning.
5. The only way to prove a historical schema is to rewrite it into current schema before invoking the reader.
6. Existing-world adoption/repair/reviewed-init compatibility cannot be proven from checked-in/disposable evidence without connecting to live Eldyrwild.
7. Any PLAYER search/traversal/anchor case exposes known GM-only material.
8. The in-memory and PostgreSQL adapters disagree on adapter-neutral semantic meaning.
9. Publication replay/recovery/stale-parent behavior differs from accepted ADRs or existing conformance tests.
10. A new baseline test/CI failure appears that is not the already-recorded benchmark-smoke defect.
11. The witness starts becoming a general snapshot framework, full campaign fixture, benchmark suite, or product integration harness.
12. K0.2 work drifts into K0.3 performance measurement, K1 demolition, K3 optimization, or K6 architecture refactor.
13. The implementation would need Buddy code/pin changes.
14. Live Eldyrwild mutation or unsanitized private campaign fixture extraction appears necessary.

A stop is a successful outcome if it exposes that the current architecture lacks a reproducible semantic contract. Record the exact missing proof seam rather than filling the gap with assumptions.

---

## §8 Handback requirements

The handback must include:

### Repositories and revisions

- DungeonMind repository;
- implementation branch;
- actual K0.2 base SHA (landed K0.1 state);
- head SHA;
- PR number/status;
- K0.1 predecessor artifact/schema/digest;
- confirmation Buddy remained unchanged and pinned.

### Decisions

For every non-obvious witness-design choice record:

```text
question
evidence
decision
rejected alternatives
consequences
reversal path
```

At minimum cover:

- why the canonical artifact uses the in-memory adapter;
- normalization policy boundaries;
- fixture reuse vs new fixtures;
- historical fixture provenance;
- any operation intentionally split into an isolated sub-scenario;
- any adapter-specific field excluded from parity.

### Verification

Record exact commands + results for:

- deterministic generator/cmp;
- focused witness tests;
- Ruff;
- Pyright;
- non-integration suite;
- PostgreSQL migration + witness parity + full integration;
- no-runtime-diff gate;
- historical compatibility matrix;
- CI status including the known benchmark-smoke baseline;
- formal review cycles and final PASS review ID.

### Semantic witness summary

Provide:

```text
witness_schema
fixture_digest
normalization_policy_digest
operation_count
historical_case_count
aggregate_semantic_sha256
postgres_parity = PASS | FAIL | BLOCKED
```

### What remains false

Explicitly state that K0.2 does **not** prove:

- K0 is complete (K0.3 remains);
- any K1 target has been safely deleted;
- post-demolition parity has passed;
- K2 `POST_DEMOLITION_PROVED` has passed;
- performance is acceptable;
- the architecture is domain-neutral;
- RulesKnowledge is supported;
- the current public API is the desired future API;
- Buddy may be repinned.

### Named next slices

1. **K0.3 — performance baseline expansion** using this witness's semantic digest as correctness guard where practical.
2. **Historical fixture extraction gap** only if K0.2 stopped because exact adoption/repair/reviewed-init evidence was unavailable without live access.
3. **Known benchmark-smoke corrective slice** remains separately named; do not silently absorb it into K0.2 or K0.3.

K1 begins only after all of K0 is complete and the roadmap's sequencing rule is satisfied.
