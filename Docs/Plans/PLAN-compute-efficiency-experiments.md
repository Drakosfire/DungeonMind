# MIND compute-efficiency experiment plan and register

Status: ACTIVE, 2026-10-17. This is the executable measurement register under the
existing [Core roadmap](../Roadmaps/ROADMAP.md), not a second migration roadmap.
Owner: MIND (Core experiments and knowledge-side dependencies). ARCHITECTURE
independently reviews implementation heads; PRIME owns merges. Buddy owns
orchestration, context/writer policy, UI and serving; GE owns provider execution.

## Authority and code inventory

Read the [pinned assignment](https://github.com/Drakosfire/DungeonOverMind/blob/c5a8f8ce601bc48cc54c320eb663908d76e601a0/Docs/Plans/HANDOFF-MIND-compute-efficiency.md)
and [complete research](https://github.com/Drakosfire/DungeonOverMind/blob/c5a8f8ce601bc48cc54c320eb663908d76e601a0/Docs/Research/RESEARCH-dungeonmind-compute-efficiency-2026-10-17.txt).
The research supplies hypotheses, not proof of a production bottleneck. Private
corpus/runtime evidence stays local; this register records reproducible commands,
synthetic results and decisions without duplicating that payload.

Baseline: Core `632468ac43d8b321bf5379589a737aede9d7327c` (merged #133).
Inspected consumer source: Buddy `e63131e1ebbc012bfd4f266036779e64ec0c5aff`,
whose dependency file pins that Core revision. These are source observations,
not a claim that a running deployment uses latest main.

| Finding | Current source evidence | Disposition |
| --- | --- | --- |
| R.3a and default-off direct rollout are still pending | README was stale; Buddy's graph roadmap retires the toggle | Corrected here; historical timing is not a current baseline |
| Reviewed-source reads still lack reuse | Core #131/#132/#133 and Buddy #1340 already implement bounded reuse | Stale as a missing-feature claim; retain accepted behavior |
| Classic parse hit avoids all graph-sized work | `world_graph_projection.py` loads the revision before cache lookup; `parsed_revision_cache.py` deeply isolates cache returns | False; measure load, parse/copy, provenance and projection separately |
| Ordinary factory retains a process-wide parse cache | Buddy `world_graph_reads.py` constructs a new repository bundle and projection service per factory call | Confirmed construction shape; measure before changing owners/lifetimes |
| A revision key freezes source admission | A new `open_read_context` gets a fresh provenance snapshot | False; source changes at the same revision must remain visible |
| A slow Council answer proves slow SQL | Current reported failure is context construction in Buddy; server SQL timings are absent | Unsupported; no SQL/storage redesign justified |
| vNext index benchmarks describe ordinary Buddy reads | Accepted V6.2 complete-object integration is explicitly dormant | False; keep component and current-route measurements separate |

Current source entry points: [projection](../../src/dungeonmind/application/world_graph_projection.py),
[parse cache](../../src/dungeonmind/application/parsed_revision_cache.py),
[database lifetime](../../src/dungeonmind/infrastructure/postgres/database.py),
[reviewed-source session proof](../../tests/conformance/test_reviewed_source_session.py).
The session handoff still says ACTIVE at this baseline despite its merged code;
that stale historical header does not allocate a competing implementation lease.

## Execution, storage and reproducibility

Reuse `/home/drakosfire/.codex/worktrees/corpus-identity-binding/DungeonMind`;
preserve primary dirty work. No new checkout, runtime environment, export or
serving process is needed. Verify Projects UUID
`48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8` and executor write access before allocation.
Task-owned evidence root:
`/home/drakosfire/Projects/.codex/mind-compute-efficiency-20261017/scratch`.
Task cache sibling: `cache`. No new temporary output goes to root-backed storage.

Use the existing Python/dependencies, with source imports pinned to this checkout.
Record executable, Python/Pydantic versions and any cached dependency overlay.
Do not install or update an environment as an incidental benchmark step. The
currently available interpreter is the existing `nonlive-graph-review-ec1da1b`
venv; its Python 3.13.12 / Pydantic 2.13.4 differ from the research's offline
benchmark environment, so timing across those environments is not a controlled
comparison. System `python3` lacks Pydantic: that is an environment failure,
not a product failure. RTK was unavailable at re-entry.

```bash
cd /home/drakosfire/.codex/worktrees/corpus-identity-binding/DungeonMind
export DM_PY=/home/drakosfire/.local/state/dungeonmindbuddy/nonlive-graph-review-ec1da1b/venv/bin/python
export DM_EVIDENCE=/home/drakosfire/Projects/.codex/mind-compute-efficiency-20261017/scratch
export TMPDIR="$DM_EVIDENCE"
export UV_CACHE_DIR=/home/drakosfire/Projects/.codex/mind-compute-efficiency-20261017/cache
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/src:$PWD:/home/drakosfire/.cache/uv/archive-v0/AKJlMlsqJbbxmbhqFBFWM"
git rev-parse HEAD
"$DM_PY" -c 'import sys,pydantic; print(sys.executable, sys.version, pydantic.__version__)'
```

Each run records beginning/end source and implementation refs; fixture and
semantic digests; request selection/order; elapsed and process CPU samples;
process RSS versus traced allocation peak; payload/output bytes; phase times;
connections, SQL, graph reconstructions, copies, source snapshots and cache hits.
Use `null` with a reason for unexercised/unavailable dimensions, never invented
zeroes. Keep raw samples, failures and negative results. Record first-process,
first-cache and repeated-cache conditions separately; never call this true-cold
database or provider-cache evidence. Profile runs are separate from timing runs.

## Experiment order and commands

| ID | Hypothesis and owner | Baseline/candidate and workload | Acceptance / next decision |
| --- | --- | --- | --- |
| CE-00 | Existing Core observations can attribute current classic preparation; MIND | Baseline above, no candidate; deterministic classic V6 100/1k fixtures, selected object plus complete scoped result | Preserve semantic digests, record graph-sized work; do not infer SQL server or whole-turn latency from memory fixtures |
| CE-01 | Retaining immutable parses still observes source withdrawal/access changes and isolates callers; MIND | Same baseline; GM/PLAYER/campaign axes, same revision with changed source, historical pin, incompatible profile and caller mutation | All owning tests pass before expanding reuse; a failing boundary blocks its optimization |
| CE-02 | Reusing a compatible cache across fresh operation services reduces reconstruction; MIND measures, Buddy owns production resource lifetime | New fresh cache per operation versus one explicitly injected compatible cache; alternating order, 100/1k/5k synthetic V6 fixtures | Exact output/qualification/anchor parity; fewer parses; report remaining full payload fetches/copies/snapshots, CPU/RSS and latency; take a cross-owner design to review if worthwhile |
| CE-03 | Connection establishment is a material fixed cost; MIND with deployment owner | Same safe read workload against an existing authorized database; current connections versus existing available pool injection; no new environment/dependency | Count connections and checkout/execute/fetch time, preserve transaction/snapshot/error semantics; defer pool change if data/dependencies unavailable or connect cost negligible |
| CE-04 | Work remains repeated outside the accepted source session; MIND | Same exact reads with current #133 session versus independently opened operations | Preserve full ordered outputs/evidence/qualifiers; count contexts/ancestry/reconstructions; never extend an admitted context across provider decisions/turns |
| CE-05 | Copying/serialization/materialization dominates after lifetime work; MIND | Exact same selected/revision fixture and schema; separate profile and unprofiled runs | Preserve nested ownership, corruption detection and publication concurrency; change one mechanism per PR |
| CE-06 | Concurrency/storage is warranted by prior measurements; MIND | Only after a named remaining bottleneck; independent worlds and same-world publications are distinct | Preserve CAS/history/integrity; disposable write fixtures only; no retained publication, migration or restart |

CE-00/01 reproducible owning-boundary commands:

```bash
"$DM_PY" -m pytest -q -p no:cacheprovider \
  tests/unit/test_world_graph_read_context.py \
  tests/unit/test_world_graph_read_observability.py \
  tests/unit/test_reviewed_init_genesis_provenance.py \
  tests/conformance/test_reviewed_source_session.py
```

The final `PYTHONPATH` entry selects the existing cached `pyperf` package after
the interpreter preflight found it absent from the venv. It does not install
packages or create an environment. Existing component benchmark command:

```bash
"$DM_PY" benchmarks/world_graph_reads.py --sizes 100 1000 \
  --cases get_object --processes 1 --values 5 --warmups 1 --loops 1 \
  --inherit-environ PYTHONPATH,TMPDIR,PYTHONDONTWRITEBYTECODE \
  -o "$DM_EVIDENCE/ce00-classic-object.json"
```

The first successor measurement slice implements a small reproducible
`benchmarks/classic_read_lifetime.py` harness, with
`tests/unit/test_classic_read_lifetime_benchmark.py` and factual results in this
register as its exclusive source write lease. It stacks on the documentation
PR until that parent merges, reuses this checkout, and changes no production
read service. Baseline/candidate are existing service construction configurations,
not invented code refs. Pin harness head and SHA before measuring:

```bash
"$DM_PY" benchmarks/classic_read_lifetime.py --sizes 100 1000 5000 \
  --repeats 5 --output "$DM_EVIDENCE/ce02-classic-lifetime.json"
"$DM_PY" benchmarks/classic_read_lifetime.py --sizes 1000 --repeats 2 \
  --profile --output "$DM_EVIDENCE/ce02-classic-lifetime-profile.json"
```

CE-03–06 are ordered conditional experiments, not pre-approved implementation
write sets. Before each starts, pin its exact harness/implementation lease, refs,
fixture and command here; use prior results to select it. A lack of usable pool,
representative DB or owning evidence is recorded as deferred, not silently
replaced by guessed timings. Continue independent safe work during review/CI.

CE-03 transport-only preflight is now leased locally: task scratch script
`ce03_connection_probe.py`, SHA256
`5878e934367f585c554e9ada1ab4c73139760fc8d711a31c2768b80a6471a658`.
It reads the existing serving configuration without printing it and asserts the
already authorized loopback authority port. Five fresh connections and one
retained sequential connection each execute five `SELECT 1` transactions with
read-only enforcement and a statement timeout, alternating mode order. It
touches no knowledge/source tables and adds no pool package (none is installed).
This supplies a transport lower bound, not a pooling, graph-read or load result.
Its exclusive output lease is `ce03-connection-probe.json` and `.log` in task
scratch, with factual register update only; no source/runtime implementation.

```bash
"$DM_PY" "$DM_EVIDENCE/ce03_connection_probe.py"
```

## Correctness and product gates

Every deterministic candidate retains evidence/qualifiers and output digest
parity, fresh source admission and withdrawal at the same graph revision,
scope/caller isolation, profile compatibility and historical identity. Exercise
affected corruption failures, error behavior and publication races before
acceptance. Reusing cached authorization by revision alone, shallow mutable
sharing, dropping evidence and weakening locks/fingerprints are not experiments.

The gold matrix includes exact object, two-source relationship, ambiguous alias,
unsupported question, broad synthesis, long history and larger synthetic worlds.
Core fixtures cover mechanical contracts; Buddy owns ordinary useful-answer,
coverage, entailment and openable-citation acceptance. Full saved-source ingestion
through publication, restart/history after edits and operator inspection remains
required. No fixed provider/Graph-operation authorization cap is introduced.
V7/V8/V11 and later vNext/storage gates remain unsatisfied by these experiments.

## Results and decisions

| Run | Ref / conditions | Outcome | Decision |
| --- | --- | --- | --- |
| Re-entry 2026-10-17 | Core baseline above; no open Core PR; research hash verified; assigned checkout clean | README drift and short classic cache lifetime confirmed by code; #131/#132/#133 are already merged | Documentation PR first, then CE-00/01 and CE-02 without another operator prompt |
| Environment preflight | Existing system Python, before environment selection | `ModuleNotFoundError: pydantic`; existing venv works; its `pyperf` import is absent | Reuse installed dependencies; retain failure; do not create an environment |
| CE-01 | Docs head `8f5c7ef7d98c5906a5a2c5468cb21ca6a9f71fe7`; existing Python; Core source unchanged | Freshness/context/observability/genesis/session cohort passed (84 cases); `ce01-freshness-tests.log` retained locally | Proceed to cache-lifetime measurement; these are mechanical gates, not product answer acceptance |
| CE-00 | Same source; existing cached pyperf; one process, five samples, one loop; already-warm benchmark fixture | Object lookup mean 27.5 ms (100) / 357 ms (1k); standard deviations 6.7 / 61 ms; pyperf flags instability | Keep raw `ce00-classic-object.json` and log; treat as exploratory observations, not stable percentiles or a performance claim |
| CE-02 | Harness begin/end `f3032649ffa2002a94eccafc60c443fb8a5fed25`; SHA256 `d739671dd94dcf41dbebef27c515fffb958d76f663e2bd581d158fcde77382cb`; 5 samples/mode/size, alternating order; one fixed memory authority | Exact semantic digests match across every sample. Parses 5→1; cache isolation copies 10→6; head/revision/source snapshot/initialization receipt reads stay 5 each | Compatible cache lifetime removes work, but full revision load, copy and scope work remain. Review a separately bounded resource-lifetime/authority namespace contract before any consumer adoption |
| CE-03 preflight | Existing venv lacks `psycopg_pool`; transport probe pinned above | Pool implementation unavailable in the existing environment; no installation attempted | Measure read-only connection cost independently before choosing a pool/dependency change |

CE-02 observations (milliseconds):

| Objects | First local / shared | Repeated median local / shared (4 samples each) | Synthetic result SHA256 |
| --- | --- | --- | --- |
| 100 | 37.29 / 34.74 | 38.43 / 24.00 | `b4ee15af2dca87f5d4f14975c96affd8e5af083b046f75f0fd1c113ed4b1f5fd` |
| 1,000 | 551.94 / 505.97 | 617.73 / 361.57 | `594439722da62e581f9e96c1c5e492772bdae64dbd2d75343bbb1aecf2a85e34` |
| 5,000 | 4,911.49 / 4,536.49 | 5,313.00 / 2,841.44 | `cb905286b5f786eb69ab92f8090437818fc8211d9b92dc2470b211e2dcf5819c` |

These are counter-instrumented memory-repository observations on a loaded host,
not a controlled Buddy/deployment latency gain or a percentile estimate. The
recorded final load average was 6.88/5.17/3.42. Process high-water RSS reached
567,582,720 bytes across the complete ladder and includes imports, fixtures and
caches; it cannot attribute memory savings by mode. SQL/connections/decode are
explicitly unmeasured. The independent 1k profiler run uses two samples/mode;
its shared warm traced allocation peak is 46,224,362 bytes versus about
67.5 MB for the miss configurations. Its roughly 4–6 second profiled samples
must not be compared to unprofiled latency.

Artifacts under task scratch: `ce02-classic-lifetime.json` SHA256
`0b8805ad1e63caf247dda9f625040d2c81e1d2846af0f891f92e13c12c8deb6d`;
`ce02-classic-lifetime-profile.json` SHA256
`1375e897f0f0974b34d1e7fd16e6b1c39fc7aa0273e6e883607277a0a9e970a1`.
The artifacts retain all raw timing/count/phase/CPU/RSS samples, fixture digest,
source refs, output size and result digest. Full serialized requests/responses
were not captured; synthetic inputs and request selection are reproducible from
the pinned fixture and harness. No private runtime evidence is included.

Raw private traces and reports referenced by the assignment are inherited
evidence, not newly reproduced results. Raw Jev responses absent from the
retained Council failure cannot be reconstructed or advertised as exact replay.

## Completion and storage record

Created: task-owned `scratch` and `cache` under the Projects root above. Owner:
MIND; retained for reproducible experiment evidence and required temporary files.
Reused: assigned existing Core checkout; no new worktree/mirror/environment.
Removed: nothing; reclaimed bytes: zero. No deletion is authorized here.
At each handback record active processes/mounts, dirty files and unpushed commits
before cleanup. Follow-up: after evidence review and PRIME merge decisions,
inventory these two task directories and propose removal only of reproducible
disposable outputs; retain unique measurements and source refs until archived.
