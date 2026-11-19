# Native read-artifact PostgreSQL storage and integration

Status: ACTIVE, draft Core PR #218. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal with implementation, review
and merge authorization; accepted source-bound artifact design #216/#217.
Current Git base: accepted #227 mergea9e308fe5b208f7ee447bf483a252d08ed04ea0b.
Codec origin: #217 aef8883238cc7c9c993e42ed666cd99bdfb1847f.
Storage implementation evidence anchor:74f24c23d70e8b39c3f884cddc80cd10ddd33275.
Current source adds accepted227 proof-reuse API to measured compositionb2263ae.
Storage-owned behavior is unchanged. The new-source HTTP proof is complete at
Core8931b854/Buddy5dcd5ff, with limits recorded below. This handoff is living
state; detailed trial history belongs in PRs and the retained scratch ledger.

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
settlement of accepted #217/#222/#223/#224/#227 handoffs brings the current slice to14 paths.
Integration rebrief: one additional owning verification-cache test path makes15.
Migration0022 creates derived foreign-key dependents; the destructive identity/
missing-source fixtures must remove those dependents before their intentional
source mutations. Keep the production foreign key and cache assertions unchanged.
CI44427051616 exposed three fixture-setup failures (510 integration checks passed);
core and benchmark passed. Repair belongs to this storage integration slice.
Rebrief: the additional paths only seal accepted223/224/227; no storage runtime expansion.
No Buddy runtime, public/frozen contract or required protocol changes, authority
redesign, index semantics, serving data, cutover or production GC policy changes.

Serial order: accepted compute #219/#220/#221/#222/#223/#224/#227 -> storage #218 acceptance ->
joint V8 evidence -> V9 preparation. Buddy adoption #4013 depends only on
accepted227 and is independently merged; it did not require unmerged218.
#219 removes unrequested primary-map hashes, #220 removes per-value callable
cycles, #221 releases private models at last use, #222 sparsifies temporary
index buckets; #223 shares immutable empty final entries and #224 removes
retained private primary-map pair tuples. Those compute PRs passed independent review and exact CI.
The current task-owned Projects checkout/env is reused; no new worktree/env.

## Mandatory read and write invariants

- Full get_revision integrity validation precedes every parsed-memory lookup.
  Accepted226/227 permits explicitly injected pure proof reuse only after a fresh
  complete raw-row SELECT and exact all-field representation equality. Changed/
  missing/corrupt rows cannot hide behind reuse; provenance remains fresh.
  The parsed-cache key snapshots complete canonical envelope representation, declared graph SHA and
  canonical source text. It is distinct from the complete raw-row proof key.
  Mutable models and Python-equality keys are forbidden.
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

Earlier consumer evidence uses retained Buddyca5a0450489a94cd364183af1c53d3f041ad7d0f.
The independently reviewed immutable anchor-preparation reuse is now accepted
as Buddy #3994 merge415e9f0d52ff0396f765849b6807559af30ce124. Its actual code was
measured at77354de; final docs-only head174639d passed248 auth-app checks,
1408 hosted tests/build and canonical exact-source evidence validation. Its
handler blob is unchanged by merge. This does not update the deployed Core pin.
The Buddy handoff's post-merge disposition travels with the next dependent Buddy
adoption slice, per its repository process.
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

Prior visible full-socket probe at74f24c2/Buddyca5a045, before readiness separation
and the accepted anchor reuse:

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

Current actual-code probe at Buddy77354de/Core77f20f8 used the full socket/lifespan
composition after ordinary readiness, which performed zero graph/revision/source
preparation. Cold neighborhood449–463ms, warm196–208ms, citation187–191ms with
zero duplicate artifact fetches; visibly changed revision465–474ms, with full
response/citation/401 and12 loaded-module hash proofs. However, explicit eviction
642–655ms and historical-return696–707ms still exceed the retained reference.
Readiness/startup cost is separate, not removed work or graph prewarming.

Disposition: representative cache-miss latency is not consistently within the
retained reference. Keep #218 draft. No current Buddy adoption, V8 acceptance, V9 preparation or cutover.
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
still reached662/712ms, so performance acceptance remains open. That bounded Buddy implementation is accepted as #3994: six owning regressions
prove parse reuse with fresh revision/source checks, withdrawal/scope denials,
standalone default and visible new/historical restoration. Its required source-
inspection player test seam was repaired without changing runtime authorization.
Core's table/authority scope does not expand. Prior nested-hook/alternate-JSON-decoder
experiments showed no reliable benefit or general equivalence proof and were not
implemented. Do not add prewarming or tune production GC to hide the measured work.

Accepted compute223 (mergead87ab1) shares immutable empty final entries. Exact
reviewed9602774 passed222 focused tests and all CI44405940347 jobs. Complete10k
model/hash parity proves60014 empty entries use10004 pairs, removing50010.
The actual13-module-attested socket composition9b6b582 with accepted Buddy174639d
passed in86.08s: first reads452–514ms, warm200–244ms, eviction647–718ms,
new revision659–737ms, historical return462–490ms, first citations187–207ms with no
duplicate artifact fetch. Exact responses/citations and fresh revision/source
checks passed. This is not a stable latency improvement or V8 acceptance.
Accepted compute224 (mergef174923) removes30002/150002 retained primary-map pairs
on synthetic10k/50k entity graphs with complete ordinary model/hash parity.
Reviewedba0d024 passed231 focused checks and all CI44408031871 jobs. Its actual
full-app compositionb2263ae/Buddy174639d passed exact response/citation/authority
and new/historical lifecycle assertions. Candidate-only run91.42s: first447–548ms,
warm201–266ms, eviction664–757ms, newrevision470–513ms, historical710–846ms,
firstcitations193–262ms,0duplicatefetch. Earlier same-source probe timings were
excluded for count-process overlap. No stable end-to-end improvement established.
Eviction fullGC207–217ms and historical fullGC216–248ms remain; trigger phase
is not an inventory of objects causing scan cost. Next investigate whole source
JSON reconstruction allocation without weakening independent integrity checks.
Record-at-a-time source JSON candidate225 was implemented and rejected unmerged.
Measured actual full-app composition5e0d6f2 retained verification225–234ms,
warm253–263ms, eviction712–713ms and historical720–731ms; fullGC206–212ms
persisted. Independent review found deep-fallback recursion compatibility loss.
Do not incorporate its parser. Storage-owned source/tests/migration blobs remain
unchanged from b2263ae; the complete source tree also includes accepted227.
Exact-source proof reuse is separately accepted as226design/227implementation
(mergea9e308f),44unit/27PG and all exactCI44415286696 green, independent review
approved. This rebriefs the earlier no-verification-cache condition: complete
fresh raw source reads plus exact complete representation equality may reuse a
successful immutable pure proof; no admission or source freshness is cached.
The implementation belongs to accepted227, not this storage patch. Buddy #4013
explicitly adopts it, merged at8be0a02841014f1661145f8b1bcab1556d55a98d
from reviewed4e8709a. Runtime5dcd5ff passed78 focused checks; final4e passed
253 auth-app checks,1410 hosted frontend tests/build/canonical receipt validation
and all three automatic workflows. Cumulative runtime and final docs reviews
approved. The serving deployment is unchanged; this is repository adoption.
The Core proof-cache native10k component takes225.80ms first,52.78–57.06ms next5reads,6freshSELECTs/
1fullverify and exact ordinaryrecordparity; content28357004bytes/64MiBtestedcap.

Latest actual full-app/socket proof uses Core8931b854 and Buddy5dcd5ff.
Fourteen loaded module hashes match the pinned sources. Readiness performs no
knowledge preparation; database/OS are warm and identity uses local fixture auth.
Three fresh workers measured first reads485–493ms, warm78–84ms, parsed eviction
510–512ms, new revision505–514ms, historical536–554ms (median539ms), and first
citations67–70ms. Complete DTOs, exact citation bytes, anonymous401, visible new
revision and historical restoration pass. Every read obtains fresh complete source
and provenance; old/new/old requires two full proofs. Retained proof content is
56,721,035bytes, below64MiB; end process RSS is approximately595MiB. The content
budget does not bound total RSS or detached in-flight request memory.
Independent review approved runtime composition and this bounded evidence at893.
One historical sample554.2ms exceeds retained~540ms classic reference. FullGC
still contributes202–218ms historically. Candidate prepare/commit costs10.55–10.75s
lack matched-write acceptance. No V8 or current deployment acceptance is claimed.
The frozen baseline was not rerun.

Remaining gates: current documentation delta review and exact-head CI;
consistent representative cold/new-revision/eviction latency; affected route,
scope/visibility, source withdrawal and historical checks; matched write costs;
current Elderwyld snapshot and broader route/memory/scale evidence; and the
canonical joint V8 record. Buddy repository dependency adoption is now merged,
but serving adoption remains a later explicit gate.
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

Additional retained evidence: final-empty-index-pair-work-count.json, actual
anchor-cache socket helper/harness/JSON/log/pytest directory, both Core-pin248-case
auth logs, hosted verifier77354de/174639d evidence and validation reports. The
verifiers removed their own clean disposable roots (pqw13yx3/ficiikqt), reporting
cleanup_complete; ficiikqt had596357120 allocated bytes in the last size sample,
while exact final reclaimed sizes are not exposed. Same verified backing UUID.
Task-local checksum-verified Node22.23/npm10.9.8 cache/archive and exact Corea672
source mirror remain active for adoption/review with the existing cleanup follow-up.
No unrelated processes or serving state were altered; the frontend lock released
without intervention by this lane. The resource queue and all local probes ended.

Additional retained evidence: shared-empty-index-count-9602774.json and native-
postgres-artifact-shared-empty-9b6b582 probe/JSON/log/pytest directory, plus local
combined verification ref9b6b582. Owner and cleanup follow-up remain this lane's
review/integration record. Probe is terminal; fixtures dropped owned databases.
No new manual worktree/mirror/env/cache, manual removal or serving mutation.

Retain deferred-record-items-count-ba0d024.json; deferred-items and deferred-items-
uncontended-b2263ae probes/JSON/log/pytest directories; local combinedrefb2263ae;
and stream-source-json-preflight.py/json. Owner is optimization lane, for review/
integration; cleanup follow-up follows explicit scope and process/mount/dirty/
unique-data checks. All local probes/count processes terminal, fixture DBs dropped.
No new worktree/mirror/env/cache, manual removals or serving changes.

Negative evidence retained: rejected225 branch3773333, measured combinedref5e0d6f2,
stream-json candidate probe/JSON/log/pytest directory and unitPG resource receipt.
Its unique codex_vnext_stream_a4c3a5faa2 DB was idle and dropped; full-app fixture
also dropped its owned source DB. Preserve failed CI44411006825 and independent
review rejection; final225 follow-up only closes disposition/fixes test imports.
All probes terminal; cleanup follow-up remains lane-owned after explicit scope.

Retain source-proof-cache-component-8a5b6b2 probe/JSON/log/pytestdir and consumer
preflight for dependent Buddy adoption. Measured component is not RSS/route proof.
Source fixture801f9bf6393b dropped; all localprobes terminal. No serving changes.

Latest retained evidence: native-postgres-artifact-source-proof-pool-8931b85-5dcd5ff
JSON/log/pytest directory and socket helper/harness; completed Buddy final4e
auth log/pytest and source-proof-hosted-4e8709a-attempt1 receipt/logs. The verifier
removed its own clean root frontend-verification-squ8n3px with cleanup_complete;
exact reclaimed bytes unavailable. Its queue is terminal. Owned source fixture
dmb_recap_source_test_794732f99a8f was dropped. No manual removal. Retain these
paths for optimization-lane integration/review with the existing cleanup follow-up.
