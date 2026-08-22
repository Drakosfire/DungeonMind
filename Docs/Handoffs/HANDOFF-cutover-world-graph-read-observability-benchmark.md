# HANDOFF — CUTOVER World Graph read observability + benchmark baseline

**Created:** 2026-08-22  
**Status:** ACTIVE — dispatch exactly this R.2a implementation capability.  
**Repository / branch:** `Drakosfire/DungeonMind` / `cutover/world-graph-read-observability-benchmark`  
**Base:** DungeonMind PR #40 merge `fd0b76056ecd159662dd1d314858aab5c9ff4440`  
**Reviewed predecessor head:** `e06b6895df4329f93870572733218d79c0ef2736`  
**Predecessor:** DungeonMind PR #40 / roadmap lane R.2  
**One-line mission:** Make DungeonMind's direct World Graph read seam operationally measurable and reproducibly characterized, without changing graph-read semantics or binding the core to a telemetry vendor, so R.3 can cut over Buddy production reads with a known performance and failure baseline.

---

## §1 Outcome

A caller can inject one DungeonMind-native `WorldGraphReadObserver` into the direct projection and retrieval services and receive privacy-safe, low-cardinality terminal observations for every direct World Graph read. Those observations distinguish projection cost from retrieval work, report stable success/miss/error and truncation/provenance health signals, and never carry graph or user content. With the no-op observer, R.1/R.2 behavior and results remain unchanged.

The repository also contains one reproducible, synthetic-v6 benchmark harness and checked-in reference baselines that characterize latency distribution, peak traced memory, deterministic output stability, and scaling for the direct read operations before DungeonMindBuddy removes its legacy hydrated read path.

This slice is complete when R.3 can answer, before deletion of the old Buddy path:

- which direct DungeonMind operation ran;
- whether it succeeded, missed, truncated, or failed;
- where the direct read spent its time at the major application phases;
- how large the parsed/admitted graph and returned result were;
- whether provenance/scope exclusions or anchor revalidation misses are occurring;
- how latency and memory scale as synthetic v6 graph size grows; and
- whether repeated identical benchmark inputs produce the same semantic output digest.

R.2a does **not** perform the Buddy-vs-DungeonMind shadow comparison. It establishes the DungeonMind observation seam and native baseline that R.3 will consume.

## §2 Authority and anchors

Read these first, in order. Checked-in code and docs are authority; chat history and PR prose are not.

1. `Docs/Architecture/ARCHITECTURE.md` and `Docs/Architecture/AUTHORITY.md` — DungeonMind owns graph/retrieval semantics independently of UI, agent provider, database adapter, or sibling repository. Observability must not become a new authority or dependency inversion.
2. `Docs/Roadmaps/ROADMAP.md` — R.2a is the first-priority successor after R.2 and must precede R.3.
3. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-projection.md` — R.1 exact revision + scoped projection contract.
4. `Docs/Handoffs/HANDOFF-cutover-direct-world-graph-retrieval.md` — R.2 native retrieval contract and its graph-only/source-anchor boundaries.
5. `src/dungeonmind/application/world_graph_projection.py` — projection phases and exact read authority.
6. `src/dungeonmind/application/world_graph_retrieval.py` — direct retrieval operations and explicit coverage/truncation semantics.
7. `src/dungeonmind/application/graph_scope.py` — exclusion/provenance diagnostics and hidden-identity rules. Observation may count these conditions; it must not export their private IDs.
8. `src/dungeonmind/application/graph_snapshot.py` — parsed graph schema and object/relationship/evidence counts.
9. `pyproject.toml`, `uv.lock`, and `.github/workflows/ci.yml` — the core currently has only Pydantic as a runtime dependency; benchmark tooling must remain dev-only and core importability without dev extras must stay proven.
10. DungeonMind PR #40 exact landed implementation — R.2a instruments the landed seam; it must not redesign R.2 behavior while adding measurement.

OpenTelemetry conventions are useful future adapter guidance, not a dependency or authority for this slice. Do not add an OpenTelemetry SDK/API, Prometheus client, vendor exporter, tracing backend, hosted telemetry client, or product-specific logger to core in R.2a.

## §3 Scope

### In scope — application observability seam

- Add one narrow application module, preferred path `src/dungeonmind/application/world_graph_observability.py`, defining a transport/vendor-neutral observation vocabulary and observer port.
- Preferred names unless implementation evidence requires an equally narrow alternative:
  - `WorldGraphReadObserver` — protocol with one terminal `observe(...)` call;
  - `WorldGraphReadObservation` — immutable application value;
  - `WorldGraphReadPhaseDuration` — immutable `(phase, duration_seconds)` value;
  - `WorldGraphReadClock` — monotonic timing port;
  - no-op default observer / system monotonic clock implementation.
- `WorldGraphProjectionService` and `WorldGraphRetrievalService` accept optional observer + monotonic clock dependencies while preserving all existing required constructor inputs and default behavior.
- Use monotonic elapsed time (`perf_counter_ns` or equivalent) for duration measurement. Do not derive durations from `projected_at`, wall clock, UTC timestamps, or repository timestamps.
- Each public direct-read method invocation emits exactly one **terminal observation for that method** after its semantic result or error is known:
  - `project`
  - `get_object`
  - `search`
  - `get_neighborhood`
  - `get_evidence`
  - `resolve_source_anchor`
- When R.2 composes R.1 with the same observer, one retrieval call intentionally yields two terminal observations: one `project` observation for the nested R.1 work and one outer retrieval-operation observation. No correlation/trace/span identifier is required in core for R.2a.
- Observer callback execution is not graph authority and must be fail-open:
  - an observer exception must not change a successful read result;
  - an observer exception must not replace or mask the original graph-read exception;
  - observer failure is not persisted as graph/retrieval state.
- Record major phase durations only where the phase is semantically meaningful and stable. Do not instrument every helper or produce method-name-shaped telemetry simply because a helper exists.
- Observations may expose counts and low-cardinality policy/schema values only. They must never expose graph/user/source identity or text.
- Preserve exact historical pins, scope semantics, player/GM leak prevention, retrieval ordering, result caps, source-anchor identity, and every R.1/R.2 test behavior.

### In scope — benchmark and baseline

- Add one repository-owned benchmark harness under `benchmarks/`, preferred path `benchmarks/world_graph_reads.py`.
- Use a dedicated benchmark tool as a **dev-only** dependency; `pyperf` is the preferred tool for calibration, warmups, worker isolation, JSON metadata, distribution reporting, and unstable-run diagnostics. Lock the chosen version through the existing uv lockfile.
- The benchmark harness must generate deterministic synthetic `dm_union_graph_v6` graphs against the bundled D&D v3 semantic profile. It must not require a live database, DungeonMindBuddy checkout, external source corpus, network access, or private Eldyrwild content.
- Generated graphs must contain enough structure to exercise the actual R.1/R.2 work rather than a degenerate object dictionary: world-owned and at least two campaign scopes, player-visible and GM-only assertions, evidence/source records, aliases, properties/aspects, and relationships with controlled density.
- The generator must use a fixed seed and record its graph-generation parameters in benchmark metadata so the same named benchmark means the same shape across runs.
- The reference scaling set is `100`, `1_000`, `5_000`, and `10_000` graph objects unless implementation evidence proves one size is operationally unreasonable. If a size must change, stop and document the reason rather than silently changing the ladder.
- Benchmark the direct operations independently:
  - projection, unpinned/current head;
  - projection, explicit historical/exact pin;
  - exact object lookup hit;
  - deterministic lexical search with bounded results;
  - depth-1 neighborhood;
  - depth-2 neighborhood;
  - evidence retrieval;
  - source-anchor resolution.
- `resolve_source_anchor` must be exercised with a deterministic anchor whose lookup does not accidentally terminate at the first generated anchor. The purpose is to characterize the current whole-projection/whole-anchor rederivation behavior rather than hide it behind a lucky target.
- Benchmark setup (graph generation, repository publication, service construction, target/anchor selection) must occur outside the timed function. The timed function measures the operation itself.
- Use the no-op observer for the reference performance baselines. R.2a measures the instrumented service's normal default path; it does not benchmark a logging/export backend that this PR does not own.
- Before timing a case, run deterministic output-digest preflight across repeated identical calls. A semantic digest mismatch is a correctness failure, not benchmark noise.
- Produce checked-in reference artifacts for:
  - latency distributions; and
  - peak traced memory (using the benchmark tool's supported memory/tracemalloc mode rather than a hand-written stopwatch/memory loop).
- Record at minimum: exact DungeonMind commit, Python version, platform/CPU metadata supplied by the benchmark tool, graph size, generation seed/density parameters, operation, request scope/admissibility, result bounds, and units.
- Add a concise checked-in baseline summary documenting commands, reference environment, results/scaling, unstable-run warnings, and interpretation. It must explicitly state that the baseline is **not an SLO** and cross-machine absolute latency comparisons are not valid without comparable environment metadata.
- Add an informational CI benchmark smoke path using a tiny generated graph and fast benchmark mode. CI blocks only if the harness is broken or nondeterministic; it must not fail a PR because an absolute latency or memory number moved.

### Out of scope (falsification)

- No DungeonMindBuddy code, imports, DTOs, hydration, dual-run, shadow execution, semantic parity comparison, or deletion. Those belong to R.3.
- No production switch from Buddy to DungeonMind reads.
- No OpenTelemetry/Prometheus/Datadog/Honeycomb/Sentry/vendor SDK, exporter, collector, dashboard, alert, SLO, or deployment configuration.
- No new HTTP endpoint, FastAPI route, admin UI, diagnostics page, websocket, CLI daemon, or product surface.
- No durable telemetry store or database migration.
- No raw query text, labels, aliases, summaries, property values, object IDs, relationship IDs, assertion IDs, evidence IDs, source IDs/revisions, world IDs, campaign IDs, graph revision IDs, source locator values, URIs, anchor IDs, or exception messages in observation payloads.
- No `focus` value or focus identifier in observation payloads. Focus is potentially content/identity-bearing request context and is not needed for this operational baseline.
- No new public serialized/wire contract. The observer values are application-layer Python interfaces. If an external serialization contract becomes necessary, stop and version it separately.
- No change to `dm_projection_request_v1`, `dm_projection_snapshot_v1`, v2 projection semantics, graph schemas, semantic-profile revisions, evidence contracts, or retrieval result contracts.
- No cache, batching, memoization, index, algorithmic optimization, or anchor-resolution rewrite in the same PR. R.2a measures the current direct read seam; it does not optimize against its own first baseline.
- No hard performance threshold in CI.
- No checked-in benchmark of real/private Eldyrwild graph content. The real production/campaign comparison belongs in R.3's cutover witness, where both paths and deployment context exist.

## §4 Invariants that bind this slice

1. **Read semantics are unchanged.** For the same repositories, graph reader, source repository, projection request, retrieval input, and clock used for projection identity, adding the default/no-op R.2a instrumentation cannot change result values, ordering, coverage, errors, anchor IDs, or revision selection.
2. **Observability is not authority.** The observer receives terminal facts after/while a read is evaluated; it cannot select revisions, admit evidence, broaden scope, mutate repositories, or alter return values.
3. **Observer failure is fail-open.** Instrumentation failure never converts read success to failure and never masks an original read failure.
4. **One terminal event per public method invocation.** Success, ordinary miss, and raised error paths are all observed exactly once for the invoked method. A nested R.1 projection also emits its own `project` event when wired to the same observer.
5. **Content-safe by construction.** Observation values contain only fixed operation/phase/outcome/failure vocabularies, booleans, bounded policy/schema enums/strings, counts, and durations. No content/identity field is merely "redacted later"; forbidden data never enters the observation value.
6. **Low-cardinality attributes stay low-cardinality.** `operation`, `phase`, `outcome`, `failure_code`, `scope_mode`, `admissibility`, `graph_schema`, `pinned_read`, `neighborhood_depth`, and truncation field names are the categorical dimensions. Request/entity IDs and arbitrary exception/type/message strings are prohibited.
7. **Timing is monotonic and non-negative.** Every recorded total/phase duration is derived from the injected monotonic clock, is >= 0, and excludes benchmark setup. Observation callback execution itself is not included in the measured graph operation duration.
8. **Projection cost is visible.** R.1 exposes head lookup, revision load, parse, and scope/provenance projection timing; R.2 outer events expose total retrieval time and a projection phase so consumers can distinguish graph materialization/scope cost from retrieval-specific work.
9. **Benchmark is a characterization, not policy.** Baseline numbers do not change runtime behavior and do not become acceptance SLOs in this PR.
10. **Benchmark output is reproducible and self-describing.** Synthetic fixture parameters, code revision, environment metadata, operation inputs/bounds, units, and deterministic semantic digest checks make the baseline interpretable later.
11. **No optimization before evidence.** If the baseline exposes expensive scaling (especially source-anchor resolution), record it truthfully. Do not optimize it inside R.2a unless the measured behavior makes the benchmark itself impossible to complete; that is a stop/split condition.

## §5 Observation contract

### Terminal observation vocabulary

The exact Python shape may remain an immutable dataclass, but the semantic fields below are required. Optional fields are `None` when the operation failed before the information became available or the field is not applicable.

| Field | Required semantics | Cardinality / privacy rule |
|---|---|---|
| `operation` | `project`, `get_object`, `search`, `get_neighborhood`, `get_evidence`, `resolve_source_anchor` | Closed low-cardinality vocabulary |
| `outcome` | `success`, `miss`, or `error` | Closed low-cardinality vocabulary |
| `failure_code` | Stable sanitized class on error; absent otherwise | Closed vocabulary; never exception class/message text |
| `duration_seconds` | Total application operation duration before observer callback | Numeric; seconds |
| `phase_durations` | Ordered/unique stable phase durations for phases actually reached | Closed phase vocabulary; seconds |
| `pinned_read` | Whether caller supplied an explicit revision pin | Boolean only; never revision ID |
| `scope_mode` | v2 scope mode | Enum/value only; never campaign ID |
| `admissibility` | GM/PLAYER policy value | Enum/value only |
| `graph_schema` | Parsed graph schema when known | Small bounded schema value |
| parsed graph counts | object / relationship / evidence counts before scoping when known | Integers only |
| admitted graph counts | object / relationship / evidence counts after scoping when known | Integers only |
| exclusion / provenance counts | object/relationship/assertion exclusion counts, provenance rejection count, scope-unknown exclusion count when known | Integers only; never rejected IDs |
| result counts | returned object / relationship / assertion / anchor counts as applicable | Integers only |
| seed counts | requested/present/missing seed counts for search/neighborhood as applicable | Integers only; never seed IDs |
| `truncated_fields` | Stable result field names that were truncated | Closed field-name vocabulary |
| `neighborhood_depth` | 1 or 2 for neighborhood, absent otherwise | Small integer |
| coverage gap counts | number of safe coverage gap codes / named missing records, not their identities | Integers only |

Do **not** add fields just because an exporter might want them. In particular, no correlation ID, trace ID, tenant/caller ID, world ID, campaign ID, revision ID, operation target ID, query fingerprint, query length, source locator, or exception text belongs in the core observation value in R.2a.

### Outcome matrix

| Operation | `success` | `miss` | `error` | Truncation treatment |
|---|---|---|---|---|
| `project` | exact scoped projection returned | Not applicable | method raises | Not applicable |
| `get_object` | admitted object returned | `found == False` | method raises | result coverage only; outcome remains success/miss |
| `search` | at least one matched object returned | zero matched objects | method raises | `truncated_fields` records truncation; outcome remains success |
| `get_neighborhood` | at least one admitted seed returned | no admitted seed returned | method raises | `truncated_fields` records truncation; outcome remains success |
| `get_evidence` | target found | `found == False` | method raises | anchor truncation is separate metadata |
| `resolve_source_anchor` | anchor resolves | `found == False` | method raises | Not applicable |

A partial neighborhood/search with some missing seeds is not a new outcome class. Record success plus missing-seed counts and existing coverage/truncation facts.

### Failure-code minimum

Use a small explicit mapping. The exact implementation helper is flexible, but at minimum distinguish known authority/input failures without exporting arbitrary exception identity:

- `head_not_found`
- `revision_not_found`
- `scope_resolution`
- `invalid_input`
- `graph_read_failed`
- `unexpected`

If an additional failure code is needed, it must be a stable operational class shared by multiple instances, not a formatted exception class/message or entity-specific value.

### Required phase matrix

Phase names are semantic observability vocabulary, not helper names. The minimum required phases are:

| Operation | Required phases when reached |
|---|---|
| `project` | `head_lookup`, `revision_load`, `parse`, `scope_projection` |
| `get_object` | `projection`, `object_selection`, `anchor_derivation` |
| `search` | `projection`, `referent_and_lexical_scoring`, `anchor_derivation` |
| `get_neighborhood` | `projection`, `traversal`, `anchor_derivation` |
| `get_evidence` | `projection`, `evidence_revalidation`, `anchor_derivation` |
| `resolve_source_anchor` | `projection`, `anchor_derivation` |

Do not force phases to sum exactly to total time; uninstrumented result assembly and Python overhead may remain in the difference. Phase timing must not duplicate work or call a graph operation twice merely to measure it.

### Observer failure behavior

```text
Successful read
→ build terminal observation
→ observer raises
→ swallow observer failure
→ return the original successful read result unchanged

Failed read
→ capture stable failure_code + elapsed phases
→ build terminal observation
→ observer raises
→ preserve/re-raise the original graph-read exception
```

Do not log the observer exception from inside core as a substitute exporter. A deployment adapter may decide how to report its own failure later.

## §6 Benchmark contract

### Synthetic graph shape

The benchmark generator must be deterministic and v6-valid. Exact ratios may be chosen during implementation, but the following dimensions must exist and be recorded in metadata:

- `object_count` from the named size ladder;
- deterministic relationship density that grows linearly with object count;
- deterministic evidence/source density;
- world-owned + campaign-alpha + campaign-beta knowledge;
- player-visible + GM-only assertions/evidence;
- aliases and summaries;
- properties/aspects;
- object and relationship evidence;
- at least one source-anchor-capable locator shape.

The benchmark should use bounded retrieval result sizes so result serialization/cardinality does not grow accidentally with the full graph. The graph itself should grow; the returned result should stay controlled.

### Benchmark cases

Use stable benchmark names that encode only operation + graph size + fixed scenario, not generated IDs.

At every size in the scaling ladder, benchmark the primary GM `world_cross_campaign` context for:

1. current-head projection;
2. exact-pinned projection;
3. exact object hit;
4. lexical search;
5. depth-1 neighborhood;
6. depth-2 neighborhood;
7. evidence retrieval;
8. source-anchor resolution.

Add at least one medium-size (`1_000` or `5_000`) PLAYER campaign projection/read case so the baseline covers meaningful admissibility filtering rather than only an all-admitted graph.

### Deterministic stability preflight

For each benchmark case:

1. run the operation repeatedly before the timed benchmark;
2. reduce the semantic result to a canonical synthetic-fixture digest that excludes non-semantic timing/projected-at values;
3. assert all repeated digests are identical;
4. only then hand the callable to the benchmark runner.

The preflight is a correctness gate. Do not convert digest mismatches into benchmark variance warnings.

### Reference artifacts

Preferred checked-in paths:

- `benchmarks/baselines/world_graph_reads-r2a-latency.json`
- `benchmarks/baselines/world_graph_reads-r2a-memory.json`
- `Docs/Benchmarks/BASELINE-world-graph-reads-r2a.md`

The summary document must state:

- exact commit benchmarked;
- exact commands used;
- environment metadata;
- fixture generation parameters;
- per-operation/per-size latency distribution summary;
- per-operation/per-size peak traced-memory summary;
- any benchmark-tool instability warnings;
- observed scaling ratios / obvious nonlinear behavior;
- explicit note on `resolve_source_anchor` scaling;
- explicit statement that the values are reference characterization, **not an SLO and not a merge threshold**.

Do not hand-edit raw benchmark JSON. Regenerate it from the harness.

### CI behavior

Add one informational benchmark-smoke job or step that:

- installs locked dev dependencies;
- runs the harness on a tiny synthetic graph in the benchmark tool's fast mode;
- exercises deterministic digest preflight;
- writes a benchmark JSON artifact;
- uploads the artifact for inspection;
- has **no numeric latency/memory assertion**.

The CI job may fail when the harness crashes, fixture generation becomes invalid, output becomes nondeterministic, or the benchmark tool reports an execution error. It must not fail merely because a runner is slower than a checked-in baseline.

## §7 Files in scope (allowlist)

Expected focused diff:

| Action | Path | Purpose |
|---|---|---|
| Create | `src/dungeonmind/application/world_graph_observability.py` | Native observation values, observer port, monotonic clock/no-op defaults |
| Modify | `src/dungeonmind/application/world_graph_projection.py` | Emit project total + phase observations without changing projection semantics |
| Modify | `src/dungeonmind/application/world_graph_retrieval.py` | Emit retrieval total + phase/result observations without changing retrieval semantics |
| Modify | `src/dungeonmind/application/__init__.py` | Export the application observation seam if current application services are exported there |
| Create / Modify | `tests/unit/test_world_graph_read_observability.py` | Pure observer/privacy/fail-open/clock behavior if a dedicated test file is useful |
| Modify | `tests/unit/test_world_graph_projection_service.py` | Projection event success/error/phase/count regression proof |
| Modify | `tests/unit/test_world_graph_retrieval_service.py` | Retrieval event miss/truncation/provenance/phase/privacy regression proof |
| Create | `benchmarks/world_graph_reads.py` | Deterministic synthetic v6 generator + pyperf benchmark harness + digest preflight |
| Create | `benchmarks/baselines/world_graph_reads-r2a-latency.json` | Raw reference latency distribution artifact |
| Create | `benchmarks/baselines/world_graph_reads-r2a-memory.json` | Raw reference peak traced-memory artifact |
| Create | `Docs/Benchmarks/BASELINE-world-graph-reads-r2a.md` | Human-readable reference environment/results/scaling interpretation |
| Modify | `pyproject.toml` | Dev-only benchmark dependency; no new runtime dependency |
| Modify | `uv.lock` | Reproducible benchmark-tool lock |
| Modify | `.github/workflows/ci.yml` | Informational benchmark-smoke artifact; no performance threshold |
| Modify | `Docs/Roadmaps/ROADMAP.md` | Mark exact R.2 landed truth, R.2a implementation/review truth, handoff link, and preserve R.3 as successor |

**Bounded discovery exception:** one additional benchmark-only helper module under `benchmarks/` is permitted **only** if the single benchmark script would otherwise duplicate substantial fixture-generation code across latency and memory modes. It must contain no runtime import side effects and no product logic. No additional `src/dungeonmind/**` production path is allowed without stopping for review.

Do not modify PR #40's approved branch while implementing this handoff.

## §8 Work plan

1. **Verify exact R.2 base.** Confirm this branch descends from PR #40 merge `fd0b76056ecd159662dd1d314858aab5c9ff4440` and that the approved R.2 fixes are present. Record the base SHA in the implementation PR. If the branch moved to a different base, stop and reconcile before implementation.
2. **Define the safe observation value first.** Implement the closed operation/outcome/failure/phase vocabulary, count-only metadata, observer protocol, monotonic clock, and no-op default. Add structural/privacy tests before instrumenting services.
3. **Instrument R.1 projection.** Time head lookup, revision load, parse, and scope projection without duplicating calls. Emit one terminal `project` observation on success/error. Prove parsed/admitted/exclusion/provenance counts and no identifier leakage.
4. **Instrument R.2 retrieval.** Add outer-operation timing for object/search/neighborhood/evidence/anchor resolution with the phase matrix in §5. Preserve one R.1 projection call per R.2 operation. Derive result/coverage counts from the already-produced result; do not re-run retrieval for telemetry.
5. **Prove fail-open behavior.** Use a deliberately throwing observer on both success and error paths. Successful result must remain byte/value-equivalent; original typed graph error must remain the raised error.
6. **Build deterministic benchmark fixture/harness.** Generate valid v6+D&D-v3 graphs at configurable sizes; keep setup out of timed functions; add semantic digest preflight and stable case naming.
7. **Generate latency + memory references.** Run the full size ladder on one recorded reference environment. Preserve raw benchmark JSON and write the concise baseline summary. Do not optimize code in response to the first numbers.
8. **Add CI smoke artifact.** Fast/tiny generated graph only; correctness/executability gate, no latency threshold.
9. **Run complete repository gates.** Core import without dev extras must still work; full unit/integration CI must remain green.
10. **Update roadmap atomically.** R.2 is landed, R.2a points at this handoff/implementation truth, R.3 remains the next cross-repo cutover and explicitly consumes the baseline/observer seam.

## §9 Acceptance gates

### Focused tests

At minimum:

```bash
uv run pytest tests/unit/test_world_graph_projection_service.py
uv run pytest tests/unit/test_world_graph_retrieval_service.py
uv run pytest tests/unit/test_world_graph_read_observability.py
```

If the dedicated observability test file is not needed, document which two existing files own every required proof instead of creating an empty/duplicative test module.

### Full quality gates

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
```

Existing PostgreSQL integration CI must remain green even though R.2a adds no PostgreSQL semantics.

### Dependency/boundary proofs

```bash
rg -i 'opentelemetry|prometheus|datadog|honeycomb|sentry' src/dungeonmind
rg 'world_id|campaign_id|revision_id|object_id|relationship_id|assertion_id|evidence_ref_id|source_artifact_id|anchor_id|query_text|label|alias|summary|locator|uri' src/dungeonmind/application/world_graph_observability.py
```

Expected:

- first command: no new R.2a telemetry/export dependency under core;
- second command: no forbidden identity/content field in the observation model. Explanatory module comments naming prohibited fields are allowed only if review confirms they are not model attributes or emitted values; prefer keeping the model structurally obvious enough that this search is clean.

Also prove `pyperf` (or chosen benchmark library) exists only in dev/benchmark surfaces and is not imported by `src/dungeonmind`.

### Behavioral observability gates

- Default construction with no observer preserves every R.1/R.2 result/error test.
- Injected recording observer receives exactly one terminal event per invoked public method; a retrieval call using the same observer on its projection service produces exactly one nested `project` event plus exactly one outer retrieval event.
- Successful project event includes all required project phases reached, non-negative durations, graph schema, pre/post scope counts, and no IDs/content.
- Pinned and unpinned reads are distinguishable by boolean only; neither observation contains revision/head ID.
- PLAYER/campaign and GM/cross-campaign events expose policy values/counts without campaign/world IDs or hidden object/source/evidence identities.
- Object/search/neighborhood/evidence/anchor ordinary misses produce `outcome=miss`, not errors.
- Search/neighborhood/anchor truncation remains explicit without inventing a separate authority/result path.
- Neighborhood records depth + seed counts but never seed IDs.
- Broken in-scope provenance and scope-unknown exclusions affect counts only; hidden IDs never enter the observation.
- Observer exception on success does not alter the returned result.
- Observer exception during error observation does not mask the original typed DungeonMind error.
- An unexpected exception maps to the generic stable failure code without exporting exception class/message text.
- No operation is executed a second time merely to derive observation metadata.

### Benchmark gates

Required harness smoke, command spelling may adapt to the chosen script CLI:

```bash
uv run python benchmarks/world_graph_reads.py --help
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/world-graph-read-smoke.json
```

Required reference generation must cover all §6 cases and the full size ladder. Exact `pyperf` flags/commands must be copied into `Docs/Benchmarks/BASELINE-world-graph-reads-r2a.md`.

Reference artifacts must demonstrate:

- deterministic semantic digest preflight passes for every case;
- latency distributions exist for every required operation/size;
- peak traced-memory results exist for every required operation/size or the baseline summary names a benchmark-tool limitation and the implementation stops for design review rather than substituting an ad-hoc measurement loop;
- environment + commit + fixture parameters are recorded;
- `resolve_source_anchor` scaling is explicitly summarized;
- no hard SLO/pass-fail threshold is introduced.

### CI gate

CI must finish green end-to-end with:

- existing `core` job;
- existing PostgreSQL `integration` job; and
- informational benchmark smoke artifact/step.

The benchmark smoke must not compare current numbers to checked-in absolute thresholds.

## §10 Stop conditions

Stop and report rather than widening or optimizing the slice if:

- The implementation branch does not descend from PR #40 merge `fd0b76056ecd159662dd1d314858aab5c9ff4440`, or the landed R.2 content no longer matches the reviewed predecessor contract.
- Adding observation requires changing a projection/retrieval result contract, scope semantics, source-anchor identity, graph schema, or durable wire schema.
- Timing a phase would require calling head/revision/parse/projection/retrieval work twice.
- A proposed observation field requires graph/user/source text or any world/campaign/revision/object/relationship/assertion/evidence/source/anchor identity.
- An exporter requires a vendor SDK or runtime dependency under `src/dungeonmind`.
- Observer failure cannot be isolated from read semantics without a broader service/runtime refactor.
- A stable failure classification would require exporting arbitrary exception messages/types rather than a small generic class.
- The benchmark cannot construct a valid representative v6 fixture without changing graph/profile contracts.
- The benchmark needs DungeonMindBuddy, a live database, external/private campaign corpus, network service, or production credentials to produce the required R.2a baseline.
- `pyperf`/the chosen dedicated benchmark tool cannot produce the required latency and memory characterization without a custom timing engine. Stop and reassess the benchmark boundary rather than quietly replacing it with ad-hoc loops.
- The `10_000` object reference case makes a full baseline operationally unreasonable. Record the observed behavior and decide explicitly whether to reduce the ladder or treat the result itself as a scaling blocker.
- The first baseline exposes a performance problem. Do **not** optimize inside R.2a; record it and dispatch a separate optimization only if it blocks R.3's acceptable cutover plan.
- CI requires an absolute timing threshold to be useful. Keep CI informational and move any later regression policy to a separately designed lane after stable baselines exist.
- Real-current-campaign benchmarking is proposed as a merge requirement. Keep R.2a self-contained; R.3 owns real cutover comparison against the live/actual graph context.

## §11 Handoff back to reviewer / R.3 successor contract

Implementation handback must include:

- exact base SHA (R.2 merge) and head SHA;
- cumulative diff stat and nano-commit sequence;
- exact changed paths, all within §7;
- focused + full test output;
- `ruff`, `pyright`, core-no-dev import proof, and CI run/job IDs;
- structural privacy/boundary search results;
- benchmark smoke command/result;
- full latency + memory baseline commands;
- reference environment metadata;
- concise scaling findings, including `resolve_source_anchor`;
- confirmation that no runtime exporter/vendor dependency was added;
- confirmation that no R.1/R.2 semantic result changed intentionally.

**What remains false after R.2a:**

- DungeonMindBuddy still has not switched production reads.
- Buddy still hydrates its legacy `UnionSupergraphStore` until R.3 lands.
- No Buddy-vs-DungeonMind semantic parity corpus has been run by this PR.
- No old/new production performance comparison has been run by this PR.
- No telemetry exporter/dashboard/SLO has been selected.
- No graph-read optimization has been performed merely because the first baseline revealed cost.

**Named next slice:** R.3 in `Drakosfire/DungeonMindBuddy`, `CUTOVER: remove Buddy graph hydration from production reads`.

R.3 must pin the landed R.2a DungeonMind dependency and use the observer/baseline in two separate cutover witnesses before deleting the old read path:

1. **Semantic parity witness** — run the same bounded request corpus through legacy Buddy hydration/kernel reads and direct DungeonMind reads, normalize into a cutover comparison shape, and classify exact parity vs intentional divergence. Search ranking need not be byte-identical when R.2 intentionally changed semantics, but every divergence must be categorized.
2. **Performance/operational witness** — compare old hydrated Buddy and direct DungeonMind latency/memory on the same operations/inputs, and record direct DungeonMind observation facts (projection share, truncation, miss/error/provenance health) so deletion is informed by measured behavior rather than assumption.

Do not broaden R.2a into R.3 and do not begin Buddy deletion in the DungeonMind repository.
