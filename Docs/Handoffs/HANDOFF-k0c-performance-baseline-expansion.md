# HANDOFF — K0.3: performance baseline expansion

**Created:** 2026-08-31  
**Status:** ACTIVE  
**Repository:** `Drakosfire/DungeonMind`  
**Handoff branch:** `kernel/k0-performance-baseline-expansion-handoff`  
**Intended implementation branch:** `kernel/k0-performance-baseline-expansion`  
**Implementation base:** `778a3f0f96251dad5dfde39e4eb778f9840a2687` — merged PR #49 / K0.2  
**Predecessors:** PR #48 K0.1 inventory; PR #49 K0.2 golden semantic witness  
**K0.2 steward PASS:** review `5072928209`  
**One-line mission:** Measure the current surviving DungeonMind architecture honestly across a repeatable scale/workload ladder, repair only the known benchmark-harness drift required to observe it, and check in a pre-demolition performance baseline without changing production behavior or optimizing anything.

---

## §1 Outcome

K0.3 lands the third and final pre-demolition truth set:

```text
K0.1  what exists / who owns it
K0.2  what surviving authority semantics mean
K0.3  what the current implementation costs
```

The PR produces a checked-in, machine-readable performance observation artifact and human report for the exact K0.2 codebase. It characterizes the current cost curve over deterministic World-like and Rules-like workload shapes at increasing scale, including point reads, bounded traversal, search, evidence/anchors, full projection, cold parse/load, canonical serialization/hash, source/provenance loading where separable, and a tiny governed publication onto a large parent.

The primary question is:

> **Before demolition or optimization, how much work does the current surviving architecture perform for each important operation as the governed knowledge corpus grows?**

K0.3 is **not** a speedup PR. A terrible number measured correctly is a successful baseline. A faster number produced by changing runtime behavior is a failed slice.

Two classes of information must remain distinct:

```text
DETERMINISTIC IDENTITY
  exact code SHA
  workload schema / generator seed / fixture digests
  operation identity
  semantic result digests

OBSERVATION
  latency samples
  memory / allocation observations
  query/work counts
  machine / Python / PostgreSQL environment
```

Do not create a single “golden performance digest” and do not treat wall-clock values as byte-deterministic. Later K2.7/K4 comparisons must compare like-for-like environments and structural work first, then latency.

Expected artifacts:

```text
benchmarks/k0_performance_baseline.py
benchmarks/k0_performance_fixtures.py             # or equivalent helper module
Docs/Reports/K0-performance-baseline-v1.json
Docs/Reports/REPORT-2026-08-31-k0-performance-baseline.md
tests/unit/test_k0_performance_baseline.py
tests/integration/test_k0_performance_baseline_postgres.py   # focused smoke/parity lane
```

The existing `benchmarks/world_graph_reads.py` remains a supported R.2/R.3-era characterization harness and its currently known constructor drift must be repaired as part of this slice.

Recommended machine artifact schema:

```text
dm_k0_performance_baseline_v1
```

K0.3 is complete only when the checked-in artifact can serve as the named pre-demolition performance baseline inherited by K2.7 and the post-optimization comparison in K4.

---

## §2 Authority and anchors

Read these in order before changing anything. Do not use chat history as authority.

1. `Docs/Architecture/AUTHORITY.md`
   - checked-in current contracts/code/accepted ADRs outrank historical reports;
   - exact durable revisions and explicit head are authority;
   - Buddy is consumer evidence, not DungeonMind semantic authority.

2. `Docs/Architecture/ARCHITECTURE.md`
   - §3 governing invariants;
   - §4 current public read/write capability boundary;
   - §5 persistence and authority;
   - §7 read architecture / R.3a and cache-safety rule.

   Especially bind:

   > Performance optimizations may not change meaning.

   K0.3 goes further: **this slice performs no production optimization at all.**

3. `Docs/Roadmaps/ROADMAP.md`
   - K0.3 performance baseline expansion;
   - K2.7 performance non-regression proof;
   - K3 optimization-lab work-accounting and target envelope;
   - K4 post-optimization comparison.

4. K0.1 evidence at merged PR #48:
   - `Docs/Inventory/K0-dispositions.toml`
   - `Docs/Reports/K0-surface-inventory.json`
   - `Docs/Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md`

5. K0.2 evidence at merged PR #49 / base `778a3f0f96251dad5dfde39e4eb778f9840a2687`:
   - `Docs/Reports/K0-golden-semantic-witness-v1.json`
   - `Docs/Reports/REPORT-2026-08-31-k0-golden-semantic-witness.md`
   - `scripts/k0_semantic_witness.py`
   - `tests/witness/`
   - final steward PASS review `5072928209`.

   Required inherited semantic aggregate:

   ```text
   sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
   ```

6. Existing benchmark harness:
   - `benchmarks/world_graph_reads.py`

   Current known baseline defect at K0.2 merge:

   ```text
   TypeError: WorldGraphProjectionService.__init__() missing 1 required keyword-only argument:
   'reviewed_world_initializations'
   ```

   This is benchmark harness drift, not a production failure. Repairing the harness is in scope. Changing `WorldGraphProjectionService` to make the old harness work is not.

7. Current implementation boundaries used by the benchmark:
   - `WorldGraphProjectionService`
   - `WorldGraphRetrievalService`
   - `VersionedUnionGraphSnapshotReader`
   - current source/provenance repositories;
   - current finalized-review/materialization/publication path;
   - in-memory and PostgreSQL repository adapters.

Use the current code at the exact base to resolve implementation details. Do not infer an API from older reports.

### Exact-anchor rule

The baseline artifact and report must record at minimum:

```text
dungeonmind_base_sha = 778a3f0f96251dad5dfde39e4eb778f9840a2687
k0_semantic_witness_schema = dm_k0_semantic_witness_v1
k0_semantic_witness_aggregate = sha256:928d4592...
k0_inventory_schema = dm_k0_surface_inventory_v1
workload_manifest_digest
benchmark_runner_schema/version
generator seed(s)
```

The implementation PR itself will have a later head SHA. Performance observations characterize the runtime tree inherited from `778a3f0…`; benchmark/test/doc-only changes may exist on top. If any `src/`, migration, dependency, or lockfile change becomes necessary, stop rather than silently changing the thing being measured.

---

## §3 Scope

### In scope

### A. Repair the known benchmark-smoke defect

Update benchmark-only construction so `benchmarks/world_graph_reads.py` supplies the current required `reviewed_world_initializations` dependency to `WorldGraphProjectionService`.

Requirements:

- use a real empty/current repository implementation appropriate to the adapter, not a production compatibility shim;
- setup remains outside timed calls;
- do not weaken the service constructor;
- do not add a default `None` merely to make old benchmark code pass;
- existing benchmark semantic digest preflight must remain intact.

The existing CI command must become green:

```bash
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/benchmark-smoke.json
```

If fixing the harness reveals a real semantic/runtime defect rather than constructor drift, stop and report it separately.

### B. Deterministic workload shapes

Build two synthetic shapes. Both are **benchmark fixtures**, not new knowledge-domain contracts.

#### `world_like`

Model the current World workload honestly:

- moderate relationship degree;
- world-owned + campaign-owned knowledge;
- GM + PLAYER visibility mix;
- aliases/properties/assertions;
- evidence refs and source revisions;
- enough relationship depth for bounded traversal;
- deterministic searchable labels;
- a deliberately late evidence/anchor target.

It may evolve the existing `world_graph_reads.py` generator or share code with it. Avoid two independently drifting definitions of “World-like” if practical.

#### `rules_like`

Model the **shape** of a rules corpus without implementing RulesKnowledge:

- many comparatively small objects/assertion-equivalent records;
- high evidence density;
- deterministic definition/reference/exception/supersession-style relationship topology;
- repeated labels/terms suitable for exact/lexical search pressure;
- bounded neighborhoods that resemble rule dependency lookup.

This fixture still executes through current DungeonMind World authority contracts because K5 has not happened yet. Do **not** invent `RulesKnowledge`, `KnowledgeSpace`, rule authority semantics, fake generic contracts, or a new profile/plugin API in K0.3.

The report must explicitly call this **Rules-like workload shape**, not a proof that current DungeonMind represents rules correctly.

### C. Scale ladder

The canonical ladder is:

```text
100
1,000
10,000
50,000
100,000
```

Every size must appear in the machine artifact for both workload shapes.

For the in-memory lane, 100 / 1k / 10k / 50k are required measured rows. 100k must be attempted. It may be recorded as `resource_limited` only with concrete evidence of the limiting condition; silent omission is forbidden.

For PostgreSQL, 100 / 1k / 10k are required measured rows for the core read cases. 50k / 100k must be attempted where machine capacity and practical execution time permit. If not measured, record explicit `resource_limited` or `not_measured` disposition and reason for every omitted case.

Do not reduce result bounds as size grows merely to improve timing unless the result contract is intentionally bounded and identical across the ladder.

### D. Required operation families

At minimum characterize these separately where the current public seam permits it without production instrumentation:

```text
cold.parse_revision
cold.load_revision                 # adapter/storage load, separate from parse where possible
warm.project_head
warm.project_pinned
warm.get_object
warm.search
warm.neighborhood_depth_1
warm.neighborhood_depth_2
warm.get_evidence
warm.resolve_source_anchor
source.provenance_snapshot_or_load # exact current boundary; see below
write.tiny_delta_publication
canonical.serialize
canonical.hash
```

Add a case only when it answers a distinct performance question. Do not turn K0.3 into a benchmark catalog.

#### Source/provenance measurement

Use the exact current source/provenance boundary actually exercised by projection. If there is a clean repository/service call, measure it directly.

If there is no separable public boundary, instrument the benchmark adapter/wrapper to count or time the source work **without editing production code**. If it cannot be isolated honestly, record it as `subsumed_by_projection` or `unavailable` with explanation. Do not create a new production API solely for measurement.

#### Tiny-delta publication

Characterize the current governed write/materialization path for:

```text
large immutable parent + one small accepted change
```

The measured operation must go through the current governed publication/materialization boundary. Directly calling `world_graph.publish_revision()` with a fabricated child is not sufficient evidence for this case because it bypasses the work whose cost K3.7 is meant to understand.

Measure total publication latency and, where externally separable without runtime changes, parent load, materialization/validation, canonical serialization/hash, and durable write contribution.

If constructing a large-parent governed fixture exposes that the current accepted API cannot represent this case without changing production contracts, stop and hand back that fact. Do not invent the future write contract in K0.3.

### E. Measurement model

The baseline must preserve raw observations rather than only one summary number.

For latency, use a bounded adaptive sampling policy suitable for both millisecond and multi-second cases. The exact policy must be checked into the runner and recorded in the artifact. It must have:

- explicit warmup count/policy;
- explicit minimum sample count;
- explicit maximum sample count or time budget;
- raw elapsed samples;
- sample count;
- p50;
- p95 where statistically meaningful;
- min/max.

Do not claim high-confidence p95 from an obviously inadequate sample count. If a slow case has too few samples for a meaningful tail estimate, preserve the raw samples and mark the p95 quality accordingly.

Latency and memory measurement should be separate passes when the memory instrumentation materially distorts timing. In particular, do not run `tracemalloc` inside the canonical latency samples and then call those numbers normal latency.

For memory, record practical process/allocator observations available without new production dependencies, such as:

- process RSS before/after/peak where measurable;
- `tracemalloc` peak in a separate pass;
- generated payload canonical byte size;
- loaded revision payload byte size where measurable.

For structural work, record as available:

- repository method-call counts;
- PostgreSQL query count;
- rows loaded;
- bytes loaded/written;
- source artifact/revision records touched;
- graph objects/relationships/evidence in fixture and returned result;
- publication payload bytes.

Every structural metric must carry a quality/disposition such as:

```text
measured
estimated
unavailable
not_applicable
```

Never label an estimate as a measured database byte count.

K3.1 may later add deeper production observability. K0.3 must not add runtime instrumentation merely to satisfy a column.

### F. Environment identity

The checked-in baseline is one observation on one environment. Record enough to compare responsibly later without recording private machine identity.

At minimum:

```text
OS / kernel family and version
CPU model if available
physical/logical CPU count if available
memory total
Python version
DungeonMind exact base/runtime SHA
uv.lock digest
pyperf version if used
PostgreSQL version for DB lane
adapter = memory | postgres
```

Do not record hostname, username, home directory, DSN, credentials, absolute project path, or other machine-identifying/private values.

### G. Semantic correctness gate for every timed case

Performance observations are invalid unless the operation is semantically stable.

Before timing each case:

1. execute it outside the timed sample;
2. normalize its semantic result deterministically;
3. repeat enough to prove identical semantic digest for identical input;
4. record that digest with the case.

Reuse K0.2 normalization concepts where practical. Do not weaken or fork semantic rules merely because benchmark DTOs are inconvenient.

Additionally, run the full checked-in K0.2 oracle before accepting the baseline:

```text
sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
```

The performance runner's per-case semantic digests do not replace K0.2.

### H. Artifact contract

Recommended JSON shape:

```text
schema = dm_k0_performance_baseline_v1
inputs
  dungeonmind_base_sha
  k0_inventory_schema/digest
  k0_semantic_witness_schema/aggregate
  workload_manifest_digest
  runner_version
  generator_seeds
environment
  non-private machine/runtime metadata
sampling_policy
workloads[]
  shape
  size
  fixture semantic/count manifest
  fixture_digest
measurements[]
  case_id
  shape
  size
  adapter
  operation
  phase = cold | warm | write | canonical
  status = measured | resource_limited | unavailable | not_applicable
  semantic_sha256
  result_cardinality
  latency
    raw_ns[]
    sample_count
    p50_ns
    p95_ns | null
    p95_quality
    min_ns
    max_ns
  memory
  structural_work
  notes
known_baselines[]
```

The artifact must not contain one aggregate performance score. There is no K0.3 pass/fail latency threshold.

The workload manifest/digests must be deterministic. The observed timings are not expected to be byte-identical on regeneration.

### I. Existing R.3a lineage

Preserve and report the existing R.3a architectural lesson rather than erasing it with a new harness:

```text
head lookup
→ revision load
→ parsed immutable revision
→ source/provenance validation
→ scope/admission
→ retrieval-specific work
```

The baseline report must explicitly answer which portions remain dominant at the measured scales, using evidence from this PR. Do not restate the old conclusion if the new measurements do not support it.

### J. CI versus full baseline

Do not put the 50k/100k full baseline in ordinary CI.

CI should prove:

- benchmark harness imports/builds;
- known benchmark-smoke is fixed;
- deterministic fixture/manifest generation;
- schema/artifact validation;
- small-size semantic preflights;
- focused PostgreSQL benchmark smoke on a disposable DB;
- no production diff.

The full baseline is a deliberate steward/local run whose machine environment is recorded in the checked-in report/artifact.

### K. Formal review telemetry

Record review cycles in the report.

Required adversarial lenses:

1. **Methodology / false-speedup review**
   - timed setup leakage;
   - accidental cache state differences;
   - changing result bounds with size;
   - semantic digest drift;
   - memory instrumentation contaminating latency;
   - large-case omissions hidden from the artifact.

2. **Work-accounting review**
   - distinguish measured vs estimated query/row/byte counts;
   - ensure repository/proxy instrumentation does not change semantics;
   - challenge whether “point read” still performs O(N)-shaped work.

3. **Artifact-truth review**
   - every roadmap K0.3 measurement mapped to a row/disposition;
   - report claims trace to machine data;
   - environment metadata is sufficient but non-private;
   - K0.2 semantic witness remains unchanged.

Review count is telemetry, not a target.

### Out of scope (falsification)

This PR must **not**:

- change production code in `src/`;
- change migrations or durable schemas;
- change `pyproject.toml` or `uv.lock` merely for benchmark convenience;
- optimize projection, retrieval, provenance, search, serialization, or publication;
- add caches, indexes, FTS, vector search, structural sharing, or new storage models;
- weaken defensive copies, canonical hashes, evidence validation, or fail-closed behavior;
- create RulesKnowledge / KnowledgeSpace / a generic plugin system;
- change World domain semantics;
- change Buddy or repin Buddy's DungeonMind dependency;
- access or mutate live Eldyrwild data;
- “fix” the benchmark by weakening `WorldGraphProjectionService` dependencies;
- repair unrelated test failures;
- turn experimental K3 latency targets into K0.3 acceptance thresholds.

---

## §4 Invariants that bind this slice

Inherited architecture invariants:

1. Published revisions are immutable; explicit head advances by CAS.
2. Evidence participates in knowledge validity.
3. Every read has explicit world/revision/scope/admissibility.
4. PLAYER fails closed across search, traversal, anchors, and diagnostics.
5. Retrieval/ranking never becomes authority.
6. Durable writes remain governed and exact-parent bound.
7. Clients are replaceable; Buddy is not the library definition.
8. Performance work may not change meaning.

Slice-local invariants:

9. **Observe the base; do not improve it.** K0.3 may change benchmark/test/doc code only.
10. **Correctness precedes timing.** A case with unstable or wrong semantic output is not benchmarkable.
11. **Setup is not the measured operation unless named as such.** Fixture generation/service construction belong outside warm-operation timing.
12. **Cold and warm are explicit states.** Do not call a cache-warmed operation “cold” or process-start cost “warm.”
13. **Latency and memory instrumentation are separated when instrumentation changes timing materially.**
14. **Work counts outrank vibes.** Prefer query/row/payload/touched-record evidence to speculation about why a case is slow.
15. **Missing data is explicit.** `unavailable` is better than a fabricated metric.
16. **Rules-like is a workload shape only.** It earns no future generic architecture by itself.
17. **The K0.2 golden oracle remains the semantic authority for surviving World behavior.**

---

## §5 Work plan

### Step 0 — re-anchor and prove the predecessor

Confirm:

```text
steward/post-cutover-library-critique = 778a3f0f96251dad5dfde39e4eb778f9840a2687
PR #49 merged
K0.2 aggregate = sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
```

Regenerate K0.2 into `/tmp` and `cmp` it to the checked-in golden before benchmark work.

### Step 1 — repair benchmark-smoke only

Update `benchmarks/world_graph_reads.py` for the current `WorldGraphProjectionService` constructor.

Prove:

```bash
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/benchmark-smoke.json
```

passes before adding the larger K0.3 harness.

Record the old failure and exact repair in the report so the baseline chronology remains honest.

### Step 2 — freeze workload manifests

Implement deterministic `world_like` and `rules_like` generators and their count/digest manifests.

Unit tests must prove:

- same seed/shape/size => same fixture digest;
- different size => different fixture identity;
- expected object/relationship/evidence counts;
- fixed bounded target identities exist;
- PLAYER-hidden material exists in World-like fixture where required;
- no random UUID/time dependency enters fixture identity.

### Step 3 — implement the observation runner and validator

Build the K0.3 runner with:

- explicit case registry;
- deterministic semantic preflight;
- separate latency and memory passes;
- recorded sampling policy;
- non-private environment capture;
- explicit measurement quality/disposition;
- JSON schema validator or equivalent strict validation;
- deterministic workload manifest digest.

Tests must reject:

- missing required ladder rows;
- duplicate case identities;
- missing semantic digests for measured semantic operations;
- private environment keys/absolute paths/DSNs;
- `measured` metrics without samples;
- estimated metrics mislabeled measured;
- silent missing 100k attempts;
- unknown artifact schema.

### Step 4 — in-memory baseline

Run both workload shapes across the ladder.

Measure the required operation families, keeping service construction/fixture generation outside warm timings.

The report should show the scaling curve and, for point operations, the ratio of corpus size to returned result size so work amplification is visible.

### Step 5 — PostgreSQL baseline

Use `DUNGEONMIND_DATABASE_URL` and the existing migrated repository bundle conventions. Never embed the DSN in the output artifact.

Required focused integration test:

- fresh migrated DB;
- small workload fixture;
- representative point read;
- full projection;
- governed tiny publication if the full runner supports it cleanly;
- semantic digest parity with the same logical memory case where adapter-neutral.

Then run the deliberate larger Postgres baseline outside ordinary CI.

### Step 6 — publication / canonical / memory characterization

Characterize large-parent tiny-delta governed publication and canonical serialization/hash independently enough to answer whether write cost is dominated by:

- parent load;
- materialization/copy/validation;
- canonical serialization/hash;
- durable write.

Do not require production instrumentation. Record unseparable portions honestly.

Run memory observations separately from canonical latency observations.

### Step 7 — write the report

The report must answer, with measured evidence:

1. What is the current latency curve for each point-read operation?
2. Which operations visibly scale with total corpus size despite bounded results?
3. What is the current full-projection curve?
4. What is the source/provenance contribution where measurable?
5. What is the current large-parent tiny-delta publication curve?
6. Where do canonical serialization/hash and memory become material?
7. How does memory compare with PostgreSQL for the same logical case?
8. What could not be measured without changing production code?
9. Which K3 hypotheses are now supported, contradicted, or still unknown?

Do not recommend a storage redesign merely because a curve is bad. K3 exists to test simpler changes first.

### Step 8 — adversarial review

Run the three review lenses from §3K. Record actual cycles, blockers, fixes, and final PASS review ID.

### Step 9 — atomic roadmap update

Only after acceptance evidence exists:

- mark K0.3 DONE;
- link the baseline artifact/report;
- record exact implementation/runtime base and baseline artifact identity;
- state that K0 is complete;
- name K1.1 as next, but do **not** mark K1 started or modify K1 details opportunistically.

---

## §6 Acceptance gates

### A. Exact base and no production/runtime diff

```bash
git merge-base --is-ancestor 778a3f0f96251dad5dfde39e4eb778f9840a2687 HEAD

git diff --exit-code 778a3f0f96251dad5dfde39e4eb778f9840a2687 -- \
  src migrations alembic alembic.ini pyproject.toml uv.lock
```

Expected: zero production/schema/dependency diff.

### B. K0.2 semantic inheritance

```bash
uv run python scripts/k0_semantic_witness.py \
  --adapter memory \
  --output /tmp/k0-golden-semantic-witness-v1.json

cmp Docs/Reports/K0-golden-semantic-witness-v1.json \
    /tmp/k0-golden-semantic-witness-v1.json
```

Expected aggregate:

```text
sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
```

### C. Existing benchmark-smoke repaired

```bash
uv run python benchmarks/world_graph_reads.py \
  --sizes 100 \
  --fast \
  -o /tmp/benchmark-smoke.json
```

Expected: exit 0; semantic digest preflight passes.

### D. Focused K0.3 unit proof

```bash
uv run pytest \
  tests/unit/test_k0_performance_baseline.py \
  tests/unit/test_import_boundaries.py
```

Expected: green.

### E. Static / surviving non-integration suite

```bash
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
```

Expected: green. The previously known benchmark-smoke failure is no longer an accepted red after Step 1.

### F. PostgreSQL focused proof

With the existing disposable PostgreSQL/pgvector service and `DUNGEONMIND_DATABASE_URL` configured:

```bash
uv sync --locked --extra postgres --extra api
uv run alembic upgrade head
uv run pytest tests/integration/test_k0_performance_baseline_postgres.py -m integration
uv run pytest -m integration
```

Expected: green with zero required PostgreSQL skips in the owning K0.3 lane.

### G. Full in-memory baseline command

The implementation may refine CLI spelling, but the final report must record the exact reproducible command. The intended shape is:

```bash
uv run python benchmarks/k0_performance_baseline.py \
  --adapter memory \
  --shapes world_like rules_like \
  --sizes 100 1000 10000 50000 100000 \
  --output Docs/Reports/K0-performance-baseline-v1.json
```

The checked-in artifact must validate against `dm_k0_performance_baseline_v1` and contain an explicit row/disposition for every required shape/size/operation combination.

### H. PostgreSQL characterization command

The final report must record the exact command and environment contract used. The runner must consume the DB URL from environment and never persist it.

### I. Artifact/report consistency

A focused validator test or CLI must prove:

- report references the exact artifact schema/path;
- exact base SHA matches;
- K0.2 aggregate matches;
- workload manifest digest matches generated fixtures;
- required ladder rows/dispositions are complete;
- no private environment fields are present;
- every measured case has semantic preflight evidence;
- known omissions/resource limits are explicit.

### J. Formal steward review

Required final disposition:

```text
PASS — K0.3 is a trustworthy pre-demolition performance baseline.
```

Do not advance K1 on a CHANGES REQUIRED review.

---

## §7 Stop conditions

Stop and hand back instead of proceeding if any of the following becomes true:

1. K0.2 golden regeneration does not match the checked-in oracle before benchmark work.
2. Fixing `benchmark-smoke` appears to require a production/runtime change rather than benchmark construction repair.
3. Any `src/`, migration, schema, `pyproject.toml`, or `uv.lock` change appears necessary.
4. A benchmarked operation cannot produce a stable semantic digest for identical input.
5. The benchmark methodology requires changing authority semantics, result bounds, scope, visibility, evidence admission, or cache rules to obtain usable numbers.
6. The “tiny delta publication” case cannot be exercised through the existing governed boundary without inventing a new contract.
7. The Rules-like fixture begins forcing new generic/domain abstractions rather than remaining a workload-shape generator.
8. PostgreSQL measurement would require storing a DSN/credential/private machine identifier in the artifact.
9. Large-scale cases exceed machine capacity in a way that prevents a truthful baseline. Record the concrete limit and hand back whether K0.3 can still satisfy the roadmap rather than silently shrinking the ladder.
10. Instrumentation changes the operation being measured enough that the metric cannot be interpreted; split the pass or mark the metric unavailable.
11. A pre-existing non-benchmark baseline failure appears that contradicts the K0.2 accepted state.
12. Evidence suggests an actual semantic/runtime defect. Do not normalize it as “benchmark noise.”
13. The implementation starts optimizing the measured path. Move that idea to K3 instead.
14. Live Eldyrwild access appears necessary. Use only checked-in/synthetic/disposable fixtures.

---

## §8 Handback requirements

The final handback must include:

### Repositories and revisions

```text
repository
implementation branch
base SHA
head SHA
PR number / URL
merge status
K0.2 inherited aggregate
baseline artifact schema/path
baseline workload manifest digest
```

### Decisions

For each meaningful methodology choice:

```text
question
evidence
decision
rejected alternatives
consequences
reversal path
```

At minimum record decisions for:

- sampling policy;
- World-like generator reuse vs new fixture code;
- Rules-like topology;
- memory instrumentation;
- PostgreSQL query/byte accounting quality;
- publication timing boundary;
- any 50k/100k resource-limited disposition.

### Verification

Exact commands and results for:

- K0.2 `cmp`;
- benchmark-smoke;
- unit/import-boundary tests;
- Ruff;
- Pyright;
- non-integration suite;
- focused + full integration suite;
- full memory baseline;
- PostgreSQL characterization;
- no-production-diff gate;
- artifact validator.

### Baseline headline table

Include a compact table for each shape/adapter showing at least:

```text
size
exact object
search
depth-1 neighborhood
evidence
anchor
full projection
tiny-delta publication
peak memory where measured
query count where measured
```

Always include sample counts/quality when presenting p95.

### What remains false

Explicitly state that K0.3 does **not** prove:

- any operation is fast enough;
- K3 target envelopes are met;
- the current storage model should be retained or replaced;
- RulesKnowledge fits the current architecture;
- demolition is semantically safe by itself;
- Buddy can be repinned;
- historical compatibility can be deleted;
- benchmark results generalize across hardware without environment matching.

### Named next slice

If K0.3 passes, the next implementation slice is:

```text
K1.1 — runtime/public excision of proven founding/agent residue
```

K1.1 must consume:

- K0.1 demolition dispositions;
- K0.2 semantic oracle;
- K0.3 pre-demolition performance baseline.

Do not bundle K1.1 implementation into this PR.
