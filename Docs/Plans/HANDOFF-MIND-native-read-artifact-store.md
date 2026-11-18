# Native read-artifact PostgreSQL storage and integration

Status: ACTIVE, draft Core PR #218. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal with implementation, review
and merge authorization; accepted source-bound artifact design #216/#217.
Current Git base: accepted #222 merge9f4e3469f2244e5c79ff04295e63d979b3251dbc.
Codec origin: #217 aef8883238cc7c9c993e42ed666cd99bdfb1847f.
Implementation evidence anchor:74f24c23d70e8b39c3f884cddc80cd10ddd33275.
Its complete src tree1ae6aecd548125136c72a8ed703232273849d4fc matches combined
verification9de8566. This handoff is living state; detailed trial history is in
PRs and the retained scratch ledger, not duplicated here.

## Outcome, scope and ordering

Consume a derived source-bound PostgreSQL artifact on an immutable parsed-cache
miss, after unchanged full independent revision verification. Open fresh source
and provenance authority on every context, including warm memory hits. Missing
optional reader/row or genuinely unsupported stored versions use ordinary parsing.
No read generates or repairs derived rows. Malformed current rows fail closed.

One coherent storage PR owns migration0022, private BYTEA store helper,
PostgresKnowledgeRevisionRepository optional reader/identity-only backfill and
new-publication insertion hook, native context/cache integration, owning tests,
affected migration expectations and current handoff. Bounded control-plane
settlement of accepted #217/#222 handoffs brings the current slice to11 paths.
No Buddy runtime, public/frozen contract or required protocol changes, authority
redesign, index semantics, serving data, cutover or production GC policy changes.

Serial order: accepted compute #219/#220/#221/#222 -> storage #218 acceptance ->
separate current Buddy adoption -> joint V8 evidence -> V9 preparation.
#219 removes unrequested primary-map hashes, #220 removes per-value callable
cycles, #221 releases private models at last use, #222 sparsifies temporary
index buckets. Those compute PRs passed independent review and exact CI.
The current task-owned Projects checkout/env is reused; no new worktree/env.

## Mandatory read and write invariants

- Full get_revision verification precedes every parsed-memory lookup. The key
  snapshots complete canonical envelope representation, declared graph SHA and
  canonical source text; mutable models and Python-equality keys are forbidden.
- Optional BYTEA fetch occurs only on parsed miss. SQL size-check and conditional
  body selection share one snapshot; oversized bytes never transfer. Bind source
  space/revision, codec/parsed versions, complete envelope digest, graph SHA,
  artifact SHA and byte length. Packet bounds precede parsing (8x source+4096).
- Readers return current-version bytes or None for absent/unsupported stored
  versions. Current-row/body manifest disagreement, nonbytes responses and
  malformed matching artifacts fail closed with typed integrity errors. Ordinary
  verifier and storage failures are never disguised as cache fallback.
- Matching pins/checksums alone are insufficient. The exact consumed artifact
  facts must reconstruct the independently verified canonical source SHA. Public
  Python-mode contract validation and immutable freezing remain mandatory, as do
  structural validation, index construction and semantic digest computation.
  Index/digest construction and returned results follow successful source proof.
- Every successful context opens fresh provenance after immutable preparation;
  revision-only graph reuse cannot preserve stale admission or withdrawn text.
- Derive artifacts internally from the exact sealed source. Expected opaque
  source wire/contract/structural ineligibility produces no artifact, preserving
  publication behavior. Source verifier failures and unexpected generator/SQL
  errors remain failures and roll back revision/head/event/receipt/result together.
- Common insertion covers governed/prospective publication and native source
  admission/extension. Replay performs no implicit regeneration. New-publication
  artifact insertion never silently accepts a conflicting existing row.
- Explicit backfill accepts source identity alone, locks and fully revalidates that
  exact revision before artifact write. Source-row then artifact-row lock order;
  concurrent source updates block/recheck, and head advance cannot retarget the
  historical revision. Explicit backfill may replace corrupt derived rows through
  deterministic regeneration. Identical regeneration is idempotent.

## Current verification

Storage code is independently approved through the current implementation anchor.
The earlier manifest-fallback and nonbytes return findings are repaired. All exact
CI44393764767 jobs passed at74f24c2, including core/integration/benchmark-smoke.
Later evidence-only documentation updates require their own current-head CI.
217 focused storage units passed. An84-test affected PostgreSQL cohort passed
before the final old-data addition; the owning artifact cohort then passed20.
Proof covers SELECT-only role/read-only transactions, absent/future fallback,
mutable and equal-instant-offset keys, corruption before memory lookup, byte
forgeries/bounded transfer, withdrawal across memory hits, all publication/cache
rollback boundaries, concurrent repair, source update locks and historical backfill.
Role/grants were rolled back and absence checked. Destructive fixtures use only
verified idle task-owned databases, never serving databases.

Consumer evidence uses retained Buddyca5a0450489a94cd364183af1c53d3f041ad7d0f.
The independent review of the earlier instrumented minimal-worker proof approved
its precise scope: five reads made5 ordinary revision verifications,5 fresh source
views and1 persisted artifact fetch; eviction caused1 new fetch and the next warm
read none. Full response, exact citation and anonymous401 assertions passed.

## Latest performance and correctness disposition

The retained paired10k reference remains~540ms classic versus original~2.12s
native. It was not rerun. Minimal fresh TestClient workers measured450–500ms
first requests,196–216ms warm and513–536ms after eviction. That narrow fixture
witness is insufficient to certify the complete serving application.

The stronger full-app probe uses Buddy main.app with its actual lifespan,
uvicorn and real owned loopback sockets. It passes explicit disposable native/APP
DSNs, uses the production read-only native repository, overrides only the fixture
managed-world binding, and confines dotenv/session/world roots to task scratch.
No provider worker is launched. Startup/import/app/client creation precedes request
timing; DB/OS are warm. Twelve actually loaded module paths/SHA256s (including
main) match committed Core/Buddy files. This is candidate local composition,
not adoption by current deployment5202 or hosted identity certification.

A new revision adds a reachable object and edge: ordinary-parser oracles after
head advance require4 nodes/3 edges instead of the historical3 nodes/2 edges.
Each child switches new/historical pins, fetches the exact revision's persisted
artifact on miss, retains ordinary verification/fresh source views on repeats,
reopens exact citations, and restores the old visible response historically.
Anonymous calls return401. Reopened citation-content SHA remains
 a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
The earlier isolated-object revision witness was weak for visible content and is
superseded; its evidence remains retained rather than silently rewritten.

Latest visible full-socket probe at74f24c2:

| Case | Observed latency |
| --- | --- |
| First request, three fresh servers |627/645/659ms |
| Repeats |195–224ms |
| Explicit parsed-cache eviction |449–468ms |
| New visibly changed revision |665–715ms |
| Return to exact historical revision |491–516ms |

First-read passive observations record177–196ms full GC scans. Initial GC windows
also include response assertions, so they are diagnostic rather than exact causal
attribution. A single-worker refinement located the first full scan during lazy AnyIO
backend import before request-stage revision/artifact work; production GC thresholds/tracking/collection policy are unchanged.
Full DTO, citation, visibility/authority semantics remain protected. All probes
closed their owned servers and fixture DBs. No frozen baseline rerun.

Publication generation at this probe took0.82–0.95s for the10k artifacts. The
second-hop prepare+commit took12.71s; the visibly changing revision took10.72s.
These include generation and are not matched classic/native write acceptance.

Disposition: full-app cold latency still exceeds the retained reference. Keep
#218 draft. No current Buddy adoption, V8 acceptance, V9 preparation or cutover.
A minimal-worker pass cannot override the stronger composition failure.

## Next primary question and acceptance obligations

Which unnecessary allocations trigger the full-app scans, and can they be removed
without weakening independent verification or shifting unacceptable cost to writes?
The exact-window refinement located the first full scan during AnyIO's lazy
async worker-backend import, before request-stage revision/artifact work. Later lifecycle data still
contained warm/citation windows and must not be attributed entirely to cold
requests. A readiness-separated experiment follows the existing production
Compose /health/ready flow and asserts zero revision/artifact/source-view work
and an empty parsed cache after readiness; it does not prewarm knowledge.
Readiness cost is recorded separately (~195–201ms). First graph reads then
measured457–463ms on the full socket composition.

The same native-only controlled experiment found Buddy's source-anchor path
calls inspect -> _pinned without the parsed cache already populated by neighborhood.
Test-local reuse preserved complete results/citations and fresh authority while
removing the duplicate artifact fetch: citation688ms became193ms; later new/
historical citations743/736ms became212/213ms. These two arms are feasibility,
not a production patch or causal cohort acceptance. Eviction/historical outliers
still reached662/712ms, so performance acceptance remains open. The next bounded
implementation belongs to Buddy: reuse only the immutable parse on this anchor
path, retain ordinary revision verification and fresh provenance, and add denial/
withdrawal/history regressions. Core's table/authority scope does not expand. Prior nested-hook/alternate-JSON-decoder
experiments showed no reliable benefit or general equivalence proof and were not
implemented. Do not add prewarming or tune production GC to hide the measured work.

Remaining gates: independent review of the latest visible/socket evidence;
consistent representative cold/new-revision/eviction latency; affected route,
scope/visibility, source withdrawal and historical checks; matched write costs;
current Buddy dependency/runtime adoption; and the canonical joint V8 record.
Only accepted V8 evidence permits V9 serving authority and rollback preparation.

## Retention and cleanup

All scratch is under /home/drakosfire/Projects/.codex/v7-elderwyld-scope/scratch/v8-core;
verified filesystem UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8. Existing Core/Buddy
worktrees, shared env, task database and verification refs remain active. Retain
unique refs cb779c1/19eb48c/a05e157/9de8566 and source/store preflights, candidate
probes/JSON/logs/pytest directories, component/allocation/lifetime diagnostics,
parsed-snapshot-findings.md and optimization-lifetime-sparse-turn-record.md.

Latest owning probe families: native_fresh_worker_revision_probe.py and
native-postgres-artifact-revision-proof-74f24c2; native_socket_revision_probe.py and
native-postgres-artifact-socket-proof-74f24c2; native_socket_visible_revision_probe.py
and native-postgres-artifact-socket-visible-proof-74f24c2; corresponding test_v8
harnesses plus single-worker socket-GC attribution probe/evidence. Retain owned
socket-lifecycle-74f24c2 dotenv/session/world roots. Detailed paths/pins and earlier
negative evidence are listed in the scratch resource record and ledger.

The active performance lane owns all retained paths for review/reproduction and
integration. Cleanup follows delivery with explicit scope, active-task/process/
mount checks and protection of dirty/unique data and commits. No new worktree,
dependency env or container; no serving-data/config writes, removals or reclaimed
bytes. These instructions do not grant deletion permission.

Latest additional evidence families retained in task scratch: socket-GC-attribution
and anchor-cache-experiment at74f24c2, their helper/harness scripts, JSON/logs and
pytest directories. No frozen baseline was rerun; native-only feasibility arms are
not an alternative baseline. Exact gate state remains draft/optimization active.

The GC stack identifies the allocation site triggering collection; it does not
identify every object contributing to the scan cost. Core modules were imported
for attestation before requests. Do not infer otherwise from request-phase labels.
