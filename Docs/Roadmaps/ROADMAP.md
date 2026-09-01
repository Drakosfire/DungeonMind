# DungeonMind — Post-Cutover Kernel Reconstruction Roadmap

**Status:** proposed forward authority on the isolated critique branch  
**Updated:** 2026-08-30  
**Audit / Buddy pin:** `5ca5d688612349034f8ca490d465af166d883e6e`  
**Steward branch:** `steward/post-cutover-library-critique`  
**Critique:** [`REPORT-2026-08-30-bottom-up-top-down-library-critique.md`](../Reports/REPORT-2026-08-30-bottom-up-top-down-library-critique.md)

This roadmap turns the post-cutover critique into small, falsifiable pieces. It deliberately separates **demolition**, **proof**, **optimization**, and **architectural refactor** so we never confuse “the code got smaller” with “the surviving authority still works,” or “the architecture looks cleaner” with “the new architecture is better.”

The Buddy pin remains frozen while this work proceeds. Candidate DungeonMind revisions may be exercised through local/test dependency overrides, but Buddy's committed lock/pin does not move until a later deliberate adoption decision.

## North star

> **DungeonMind is a small, deterministic, provenance-first authority and graph library for versioned knowledge. It owns knowledge identity, evidence, revision, publication, and graph integrity. Knowledge domains own what those facts mean and how they are admitted. Clients own how users and agents act on them.**

The roadmap should make the surviving system:

- easier to understand;
- easier to consume as a library;
- materially faster at point reads and bounded traversal;
- capable of scaling toward rules-sized corpora;
- reproducible enough to support deterministic RulesEngine compilation;
- less contaminated by completed migration history and founding agent-runtime experiments;
- no less strict about provenance, immutable history, CAS publication, and fail-closed integrity.

---

# Governing rules

## Rule 1 — demolition and refactor are separate proof obligations

Deleting historical/residual subsystems is not the architectural refactor.

After demolition, DungeonMind enters a named **proof plateau**. No Authority/Graph/World/Rules boundary refactor starts until the surviving system is re-proven against the complete acceptance matrix in K2.

## Rule 2 — no refactor gets credit for tests it changed to make itself pass

The K0 golden witness is captured before demolition. Its semantic expectations survive across demolition and refactor unless an explicit architecture decision changes a contract.

Tests whose only purpose is a deliberately removed subsystem may be deleted with that subsystem. Tests proving surviving authority semantics become inherited obligations.

## Rule 3 — optimization is a first-class workstream

Optimization is not folded into cleanup or refactor PRs.

Performance work gets:

- its own baseline;
- its own benchmark corpus ladder;
- semantic parity checks;
- query/work-count instrumentation;
- latency and memory reporting;
- explicit escalation criteria before storage-model complexity is added.

## Rule 4 — historical readability is not the same as historical centrality

Old graph schemas, receipts, and migration history may need to remain readable. That does not require new clients or normal hot paths to understand migration chronology.

## Rule 5 — RulesKnowledge is an adversarial canary, not a mandate to generalize

Do not invent `KnowledgeSpace`, a generic plugin system, a universal ontology, or a Rules domain from taste. Use real RulesIngestion evidence and RulesEngine determinism to discover which World assumptions are actually non-generic.

## Rule 6 — each PR has one primary question

Every implementation PR should be answerable as one sentence:

> What did this PR prove that was not proven before?

Review-cycle count remains recorded, but fewer cycles is not itself a success criterion.

---

# Phase map

```text
K0  Freeze current truth + golden witness
 ↓
K1  Demolish proven founding/runtime residue
 ↓
K2  PROOF PLATEAU — prove surviving DungeonMind before refactor
 ↓
K3  OPTIMIZATION LAB — discover current architecture's speed envelope
 ↓
K4  Performance + semantic reproof checkpoint
 ↓
K5  RulesKnowledge adversarial canary
 ↓
K6  Evidence-backed Authority / Graph / World refactor
 ↓
K7  Full post-refactor reproof
 ↓
K8  Compatibility / physical-schema cleanup only when newly safe
 ↓
K9  RulesKnowledge + RulesEngine integration ladder
```

K2 is a hard gate. K6 does not begin before K2 passes.

K3 and K5 intentionally happen before K6 so the refactor is informed by measured cost and a materially different knowledge domain rather than aesthetics.

---

# K0 — Freeze current truth and build the golden witness

**Purpose:** make demolition safe and make future semantic drift obvious.

No behavior changes.

## K0.1 — Current consumer and public-surface inventory

**Disposition:** IMPLEMENTATION COMPLETE — audit fixes landed; await second review merge

Landed artifacts:

- [`Docs/Inventory/K0-dispositions.toml`](../Inventory/K0-dispositions.toml) (human-authored judgments)
- [`Docs/Reports/K0-surface-inventory.json`](../Reports/K0-surface-inventory.json) (generated machine evidence)
- [`Docs/Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md`](../Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md)
- `scripts/k0_surface_inventory.py` (regenerator)
- `tests/unit/test_k0_surface_inventory.py`

Every named demolition target has an explicit `USED | UNUSED | HISTORICAL-COMPAT | UNKNOWN` disposition. `UNUSED` is K1 eligibility, not a deletion.

Known baseline: `benchmark-smoke` is red at the runtime anchor (benchmark harness vs `WorldGraphProjectionService` constructor drift). Recorded in ledger `known_red_baselines`; corrective slice is out of K0.1 scope.

Next: K0.2 landed; see K0.2 section.

## K0.2 — Golden semantic witness

**Status:** DONE  
**Landed evidence:** [`Docs/Reports/K0-golden-semantic-witness-v1.json`](../Reports/K0-golden-semantic-witness-v1.json), [`Docs/Reports/REPORT-2026-08-31-k0-golden-semantic-witness.md`](../Reports/REPORT-2026-08-31-k0-golden-semantic-witness.md)  
**Base:** `e5fb104708f979b0ebb481ee925db4beb22e2bfe` (landed PR #49 base; first parent `3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1`, identical tree, pins the diff gates)  
**Aggregate digest:** `sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa`

Freeze expected outputs/digests for the surviving World authority contract.

Minimum witness:

### Reads

- head read;
- exact historical revision read;
- exact object;
- deterministic search;
- depth-1 neighborhood;
- depth-2 neighborhood;
- evidence retrieval;
- source-anchor emit/revalidate;
- GM campaign scope;
- PLAYER campaign scope;
- world-owned scope;
- cross-campaign scope;
- known missing object / revision / head failures;
- provenance-invalid fail-closed cases.

### Writes

- first-world reviewed initialization;
- exact-parent child publication;
- stale-parent rejection;
- exact replay/idempotency;
- outcome-unknown recovery;
- correction/retraction behavior currently supported;
- source/evidence binding integrity.

### Historical compatibility

- every still-required graph schema reader;
- Eldyrwild adoption/repair reconstruction;
- reviewed-first-world compatibility required by the living data.

The witness should distinguish:

```text
semantic digest / identity
observation metadata
wall-clock timing
```

Wall-clock `projected_at` is not a semantic equality key.

Next: K0.3 performance baseline expansion. Do not advance K1 solely because K0.2 passed.

## K0.3 — Performance baseline expansion

Preserve R.3a, then add a larger, repeatable baseline before optimization begins.

Corpus ladder:

```text
100
1k
10k
50k
100k objects/assertion-equivalent scale where machine capacity permits
```

Use at least two synthetic shapes:

1. **World-like** — moderate degree, aliases/properties/evidence resembling Eldyrwild.
2. **Rules-like** — many small rule/assertion objects, definition/exception/supersession edges, dense evidence identity, repeated bounded point reads.

Measure separately:

- cold parse/load;
- warm point reads;
- exact object;
- depth-1/depth-2 neighborhood;
- evidence;
- anchor resolution;
- lexical search;
- full projection;
- source snapshot load;
- publication of a tiny delta onto a large parent;
- canonical serialization/hash cost;
- peak memory / allocation pressure;
- PostgreSQL query count and bytes loaded where measurable;
- in-memory reference adapter.

**Exit:** checked-in baseline artifact plus reproducible commands.

---

# K1 — Demolition wave: remove proven founding/runtime residue

**Purpose:** delete responsibilities that current architecture and current consumers no longer assign to DungeonMind.

This phase must not redesign World authority or invent the future Kernel.

## K1.1 — Runtime/public excision

Remove from current public/composition surfaces, where K0 proves no current consumer:

- MindTurn as a supported library interaction model;
- `agents/` runtime ownership;
- CapabilityPolicy as agent-visible tool authority;
- MindTurn-owned context assembly;
- MindThread / retrieval-session runtime composition;
- fixture-agent/demo runtime composition tied only to MindTurn.

Keep any historical persisted records/tables untouched in this PR.

**Proof:** core imports, current World reads/writes/init/publication, and Buddy external-consumer witness remain green.

## K1.2 — Physical code demolition

Delete code/tests/fixtures whose only remaining purpose was the excised runtime.

Do **not** delete migrations merely because their runtime owner disappeared. Old databases must remain upgradeable/reconstructable until a later physical-schema cleanup proves otherwise.

**Proof:** no dead import paths, no hidden agent dependency in application/core, no optional model/provider dependency pulled into core.

## K1.3 — Derived semantic-runtime disposition

Use K0 evidence to classify semantic documents / embedding runs / pgvector-derived runtime as one of:

```text
KEEP OPTIONAL
MOVE TO OPTIONAL PACKAGE/ADAPTER
QUARANTINE AS HISTORICAL
DELETE UNUSED RUNTIME
```

This is a disposition PR first. Do not bundle a vector/search redesign into demolition.

---

# K2 — THE PROOF PLATEAU

**Purpose:** establish a trusted post-demolition DungeonMind before any architectural refactor.

This is deliberately a pause in architecture work. The only allowed changes are test-harness fixes, missing observability needed to prove behavior, and defects exposed by the proof itself.

A post-demolition commit is not considered a valid refactor base until all required cohorts pass.

## K2.1 — Static and package proof

Required:

- Ruff;
- Pyright for core and optional adapters;
- import-boundary tests;
- `import dungeonmind` with no heavy extras;
- `import dungeonmind_dnd` with no unintended optional runtime dependencies;
- no application ↔ agent exception remains merely to support deleted runtime;
- wheel/package-data build smoke.

## K2.2 — Full surviving unit/conformance proof

Required:

- every surviving unit test;
- in-memory repository conformance;
- PostgreSQL repository conformance;
- graph reader/schema locks;
- source/evidence contracts;
- publication/recovery tests;
- World projection/retrieval tests;
- D&D profile/mechanics tests still in current ownership.

Any deleted test must be named in the demolition handback with the deleted capability that justified its removal.

## K2.3 — Fresh-database proof

On a fresh PostgreSQL instance:

```text
alembic upgrade head
→ initialize fresh authority state
→ register source/evidence
→ publish first revision
→ read it
→ publish child
→ historical read parent
→ replay publication
→ exercise stale-parent rejection
```

No manual repair steps.

## K2.4 — Existing-history reconstruction proof

Against a disposable copy/fixture of the living historical shape:

- migrations upgrade cleanly;
- required v1-v6 stored revisions still decode;
- Eldyrwild adoption / repair lineage reconstructs;
- exact historical revisions still read;
- head semantics remain unchanged;
- source/evidence integrity remains fail-closed.

Never mutate the live Eldyrwild authority database for this proof.

## K2.5 — Golden semantic parity proof

Re-run K0.2.

Acceptance rule:

```text
post-demolition semantic witness == pre-demolition semantic witness
```

for every surviving operation.

Deleted agent/harness features are outside the equality set because deletion is the intended behavior.

## K2.6 — Buddy pinned-consumer proof

Exercise current DungeonMindBuddy against the candidate DungeonMind branch through a temporary local/test override only.

Buddy's committed pin/lockfile remains unchanged.

Prove the owning consumer cohorts for:

- current World Graph reads;
- current governed writes;
- Graph Review/publication paths;
- Threat/worldbuilding consumers;
- first-world/recovery paths still relevant;
- Hermes/Agent Surface graph-tool consumption where it calls Buddy's DungeonMind integration.

## K2.7 — Performance non-regression proof

Demolition is not allowed to make surviving reads materially slower.

Compare against K0.3 / R.3a with semantic digests matched first.

**K2 exit disposition:** `POST_DEMOLITION_PROVED`.

Only after this disposition may K6 architecture refactor begin. K3/K5 evidence work may proceed first as described below.

---

# K3 — OPTIMIZATION LAB

**Purpose:** discover how fast the surviving design can become before paying for a storage-model rewrite.

This is a dedicated workstream, not opportunistic micro-optimization.

All optimization experiments inherit K0/K2 semantic oracles. A faster wrong answer fails.

## Optimization priorities

In order:

1. avoid doing unnecessary work;
2. avoid loading unnecessary data;
3. avoid unnecessary copies/allocations;
4. index derived serving paths;
5. optimize serialization/hashing;
6. change physical authority storage only if the previous steps cannot meet the workload.

## K3.1 — Profiling and work-accounting harness

For every benchmarked operation capture as practical:

- wall time p50/p95;
- CPU time;
- peak memory;
- allocations/copies;
- parsed objects/assertions/evidence touched;
- admitted objects/assertions/evidence touched;
- PostgreSQL query count;
- rows/bytes loaded;
- cache/index hits;
- canonical serialization/hash time.

Structural work counts matter more than one laptop's absolute timing.

## K3.2 — Lazy-admission point reads

Change the current work shape from:

```text
full revision
→ full source snapshot
→ full domain admission
→ one object
```

toward:

```text
exact candidate
→ candidate evidence/provenance
→ domain admission for candidate
→ result
```

Targets:

- exact object;
- evidence lookup;
- anchor resolution;
- bounded neighborhood.

Full projection remains an explicit O(N) operation.

**Hard semantic gate:** output digests/coverage behavior match the K2 authority result for the same request.

## K3.3 — Revision-local immutable indexes

If K3.2 needs them, build rebuildable per-revision indexes for:

- object ID;
- relationship adjacency;
- assertion/evidence support;
- alias/label exact lookup;
- anchor supporter lookup.

Indexes are derived state and never authority.

Prefer immutable index construction/reuse over cross-request authorization-result caching.

## K3.4 — Search optimization

Search should generate a small candidate set before expensive domain admission.

Test in increasing complexity:

1. in-memory exact/lexical index;
2. deterministic FTS/BM25-style candidate index;
3. optional vector candidates only if a real workload proves they add value.

Search ranking never becomes factual authority.

## K3.5 — Provenance/admission optimization

Profile:

- source snapshot construction;
- evidence resolution;
- repeated domain-policy checks;
- defensive copies;
- canonical model conversion.

Explore narrower provenance loads for bounded point reads while retaining coherent fail-closed semantics.

## K3.6 — Serialization / model overhead experiment

Measure before changing libraries or contracts.

Potential experiments include:

- Pydantic deep/model-copy cost;
- immutable internal records;
- canonical serialization implementation;
- payload hashing strategy;
- JSON encode/decode cost;
- avoiding JSON-string structured contribution values in future current contracts.

Do not weaken canonical identity to win a benchmark.

## K3.7 — Publication/write-path benchmark and optimization

The current v6 materializer reconstructs and validates a full child payload from the full parent.

Characterize:

```text
large parent + tiny accepted change
```

at 1k / 10k / 50k / 100k-scale fixtures.

Measure:

- parent load;
- copy/materialization;
- validation;
- canonical serialization;
- hash;
- PostgreSQL bytes written;
- total publication latency;
- peak memory.

First optimize within the current immutable-snapshot model.

Only if measurements justify escalation consider:

```text
content-addressed immutable records
+ revision membership / structural sharing
+ immutable delta lineage
+ periodic canonical full checkpoints
```

A storage redesign must preserve a deterministic canonical revision artifact/export and exact historical reconstruction.

## K3.8 — Scale and concurrency characterization

Test at least:

- repeated warm reads;
- mixed exact-object/neighborhood/search workload;
- concurrent independent readers;
- head + historical pin mix;
- publication while readers continue to pin an old immutable revision.

This is characterization, not a distributed-systems project.

## Experimental performance bars

These are **targets to attack**, not promises to fake by weakening semantics.

Warm local/in-process target envelope:

```text
10k exact object p95              < 25 ms
10k evidence p95                  < 25 ms
10k depth-1 neighborhood p95      < 50 ms
10k deterministic search p95      < 100 ms

100k exact object p95             < 50 ms
100k depth-1 neighborhood p95     < 100 ms
100k deterministic search p95     < 250 ms
```

For PostgreSQL-backed reads, record a separate envelope so DB/network cost is visible rather than hidden inside the same number.

No hard full-projection target is set initially: it is legitimately O(N). Its cost is measured and optimized, but point reads must stop depending on it.

Publication targets remain characterization-first until K3.7 establishes the current curve.

## Optimization exit questions

K3 ends with an explicit performance report answering:

1. What is the fastest correct point-read architecture we achieved without changing authority storage?
2. Where is the new dominant cost?
3. At what scale does the current full-snapshot publication model become unacceptable?
4. Which proposed index/storage mechanisms have measured benefit?
5. What complexity can now be rejected because simpler changes were enough?

---

# K4 — Post-optimization proof checkpoint

Re-run the entire K2 proof plateau plus K0.3 performance ladder.

Required:

```text
semantic parity: PASS
historical reconstruction: PASS
fresh init/publication/recovery: PASS
Buddy local override witness: PASS
performance report: checked in
```

Record the best known performance envelope as the new optimization baseline.

This checkpoint prevents the later architecture refactor from receiving credit for speedups already earned by simpler work-shape changes.

---

# K5 — RulesKnowledge adversarial canary

**Purpose:** make a materially different domain expose false genericity before K6 designs the new boundaries.

## K5.1 — First real rule slice

Use the existing RulesIngestion D&D 2024 occupancy slice:

- default end-movement occupied-space prohibition;
- ally-prone exception;
- exact EvidenceUnit grounding;
- deterministic RulesEngine-facing rule artifact.

Attempt to represent, retrieve, version, cite, and bind it through the surviving DungeonMind **without adding a generic refactor first**.

Record every forced mismatch:

- fake world identity;
- fake campaign/session;
- fake GM/PLAYER visibility;
- fake canon semantics;
- inappropriate entity merge semantics;
- JSON-string structured values;
- Graph Review assumptions;
- inability to pin a reproducible source-authority view;
- awkward public API composition.

Success is not “we made it fit.” Success is a precise list of what current architecture makes unnatural.

## K5.2 — RulesEngine replay requirement

Bind the canary to a deterministic executable rule build and capture:

```text
EvidenceUnit identity
→ DungeonMind rule-knowledge identity/revision
→ formalization/resource identity
→ RulesEngine executable rule/ruleset digest
→ deterministic fixture result
```

Then change source authority state in a controlled fixture and test whether the old build can be reproduced exactly.

This is the concrete test for whether a durable `AuthorityView`-like identity is actually needed.

## K5.3 — Second-system profile probe

When a small non-D&D packet is available, repeat only enough of the canary to answer whether the profile/domain split requires Kernel changes.

Do not block the first refactor indefinitely waiting for a full second corpus; the D&D Rules domain is already materially different from WorldKnowledge.

---

# K6 — Evidence-backed Kernel / World refactor

**Hard prerequisite:** K2 `POST_DEMOLITION_PROVED` and K5 mismatch ledger exist.

This phase changes architecture. It does not receive permission to rewrite the system wholesale.

## K6.1 — Define the irreducible Authority Kernel contracts

Create the smallest current contract set for concepts proven across World + Rules canary:

- canonical identity;
- source artifact/revision identity;
- evidence/anchor identity;
- immutable knowledge revision;
- explicit head;
- expected-parent CAS;
- governed publication result/recovery;
- fail-closed integrity;
- observation hooks.

Do not put campaign/session/GM/player/fictional-time/rule-priority semantics here.

Prefer additive current contracts plus adapters from historical formats over editing old durable schemas.

## K6.2 — Make Graph Kernel domain-neutral

Prove reusable graph operations over domain-neutral records:

- object/assertion/relationship identity;
- JSON-valued properties;
- qualified terms;
- exact object;
- adjacency;
- bounded traversal;
- assertion/evidence association.

Domain admission remains injected/owned above this layer.

## K6.3 — Move World semantics into WorldKnowledge

Relocate/re-express:

- world/campaign scope;
- GM/PLAYER visibility;
- world epistemic/canon policy;
- session association;
- fictional time;
- world identity reconciliation where still useful;
- World projection/admission.

The current Buddy consumer must continue to observe identical World semantics through compatibility/current facades.

## K6.4 — Separate publication invariant from World Graph Review policy

Kernel owns exact-parent governed publication and atomic recovery.

WorldKnowledge/Buddy policy owns human review/confirmation semantics.

RulesKnowledge may later authorize publication through deterministic validation/compiler/conformance gates.

## K6.5 — Compatibility quarantine

Move old durable/history concerns behind explicit compatibility seams:

```text
compat graph-schema readers
compat existing-world adoption
compat repair/correspondence
compat reviewed-first-world lineage
```

Current-domain logic consumes one normalized current model rather than branching on migration history everywhere.

## K6.6 — Intentional public facade

Build the smallest supported library surface proven by Buddy + tiny-client use:

```text
configure/open authority
read head or exact revision
get object
search
neighborhood
evidence/anchor
prepare/publish governed change
initialize a new domain authority
```

Do not create a god object. The facade may compose a few explicit read/write/init services.

## K6.7 — Introduce only the RulesKnowledge concepts K5 earned

Possible concepts may include:

- ruleset/edition scope;
- normative status;
- supersession/errata;
- exception/precedence relationships;
- formalization resource binding;
- domain publication policy.

If K5 did not need a concept, do not add it yet.

---

# K7 — Full post-refactor reproof

Run K2 again, unchanged wherever possible.

Then add K5 canary expectations.

Acceptance requires:

```text
World golden witness                PASS
historical reconstruction           PASS
fresh initialization                PASS
governed publication/recovery       PASS
Buddy local override witness        PASS
Rules canary                         PASS
optimization envelope                no unacceptable regression
```

If the refactor makes point reads meaningfully slower than K4, the refactor must explain why or fix it before adoption.

A clean architecture is not allowed to spend the performance gains silently.

---

# K8 — Physical compatibility/schema cleanup

Only after K7 proves the new current paths.

Candidate work:

- drop dead MindTurn/thread/retrieval-session tables through a forward migration if old-db upgrade proof remains safe;
- remove dead repository implementations;
- reduce giant `__init__` re-export surfaces;
- move old schema readers/contracts under explicit compatibility namespaces where Python import compatibility allows;
- retire migration-only service wiring;
- separate optional embedding/index packages if retained.

Old immutable migrations remain history. Do not rewrite migration files in place.

Every destructive cleanup gets its own explicit reconstruction/upgrade proof.

---

# K9 — RulesKnowledge integration ladder

After K7 establishes the new architecture:

## K9.1 — Evidence registration adapter

RulesIngestion EvidenceUnits remain source-evidence authority. DungeonMind stores exact source/revision/evidence identity and locators, not a competing OCR/chunking truth.

## K9.2 — Governed rule-knowledge ingestion

Publish typed rule objects/relationships/assertions under RulesKnowledge policy.

## K9.3 — Exact formalization/resource binding

Use the statblock/external-mechanics precedent:

- graph owns semantic rule identity and relationships;
- dense typed executable rule packet remains an exact immutable resource;
- binding is content/revision-addressed.

## K9.4 — Deterministic RulesEngine build

```text
pinned RulesKnowledge authority view
→ deterministic compiler/mapper
→ executable ruleset artifact
→ RulesEngine fixtures
```

RulesEngine does not query DungeonMind during the hot evaluation loop.

## K9.5 — Ingestion learning loop

Trace failures:

```text
RulesEngine failure
→ executable rule id
→ formalization binding
→ DungeonMind rule/assertion
→ EvidenceUnit
→ exact source span
```

Use the failure as evaluation evidence for RulesIngestion. It never silently changes knowledge authority.

---

# Required proof artifacts per PR

Every non-doc implementation PR in this roadmap should leave enough evidence to audit it later:

```text
Base commit
Head commit
Primary question proved
Changed authority/runtime surface
Tests run
Owning integration cohort
Semantic digest result where applicable
Performance before/after where applicable
PostgreSQL query/work-count delta where applicable
Review cycle count
Final PASS review / unresolved findings
Follow-up explicitly deferred
```

Optimization PRs additionally record benchmark commands and machine/environment identity.

Demolition PRs additionally list removed tests/files and the evidence that no surviving capability owned them.

Refactor PRs additionally list which K0/K2/K5 obligations they re-ran.

---

# Explicit anti-goals

This roadmap does **not** authorize:

- a rewrite from scratch;
- `KnowledgeSpace` implementation before K5 evidence;
- a universal TTRPG ontology;
- fake World records for rules corpora;
- arbitrary executable plugin hooks;
- Neo4j or another graph database by fashion;
- Redis/distributed caching before local/indexed work is exhausted;
- vector retrieval as knowledge authority;
- weakening provenance, immutable revisions, CAS, or fail-closed behavior for speed;
- rewriting old migrations in place;
- mutating the live Eldyrwild DB for experiments;
- moving the Buddy pin during critique/experimentation;
- making RulesEngine call DungeonMind inside deterministic rule evaluation.

---

# Immediate sequence

The first implementable series should be:

```text
K0.1  consumer/public-surface inventory
K0.2  golden semantic witness
K0.3  expanded performance/write baseline

K1.1  runtime/public agent-harness excision
K1.2  physical code demolition
K1.3  semantic-runtime disposition

K2     full proof plateau

K3.1  profiling/work-accounting harness
K3.2  lazy-admission point reads
K3.3  revision-local indexes as required
K3.4  search optimization
K3.5  provenance/admission optimization
K3.6  serialization/model overhead experiment
K3.7  write-path optimization
K3.8  scale/concurrency characterization

K4     optimization + semantic reproof

K5     RulesKnowledge canary

K6     architecture refactor in small slices
K7     full reproof
```

That ordering gives us three unusually valuable baselines:

1. **pre-demolition DungeonMind** — what the cutover produced;
2. **post-demolition DungeonMind** — what the system actually needs;
3. **post-optimization DungeonMind** — how fast the existing authority model can become before architectural refactor.

Only then do we ask the new architecture to beat all three.