# Native read-artifact PostgreSQL storage and integration

Owner: active Elderwyld performance lane. Codec parent: accepted Core #217
aef8883238cc7c9c993e42ed666cd99bdfb1847f. Current compute base: accepted #221
6c61e8e73faf6d02c0d1f73692f185a55c050a4f; #219/#220 are also accepted.
Status: ACTIVE implementation lease on codex/vnext-read-artifact-store.
Execution authority: accepted source-bound read-artifact design #216 and operator
optimization-before-cutover goal, with implementation/review/merge authorization.
The parent passed independent exact-head review and all CI jobs before merge.

Outcome: ordinary source-context opening can consume a source-bound PostgreSQL
artifact after unchanged full revision verification. Every context still opens
fresh provenance authority. Repositories lacking the optional reader retain
ordinary parsing. Memory hits snapshot complete envelope representation, declared
graph SHA and canonical source text, without mutable/Python-equality keys.

Scope: one derived BYTEA artifact table/migration, private artifact-store helper,
PostgresKnowledgeRevisionRepository read/backfill methods and new-publication
insertion hook, native source-context optional read integration/cache keys,
owning unit/PostgreSQL proof, affected migration-head expectations and live handoff.
No Buddy, source admission, public frozen wire contracts, authority redesign,
index semantics, cutover or primary-runtime data changes.

Ordering: accepted compute through #221 -> sparse compute #222 acceptance ->
rebase store/read/write/backfill PR -> Buddy adoption after performance proof.
The current task-owned worktree/env are reused on a new codex/ branch. No new
worktree or dependency environment. No frozen baseline rerun.

Read invariants: full get_revision first; optional artifact fetch only on parsed
memory miss; size bound before packet parsing; independent blob checksum and
source/format binding; malformed matching artifacts fail closed; absent or
unsupported versions fall back; no read-side cache writes. Preserve typed storage
failures. Fresh source view opens after immutable preparation on every context.

Write invariants: derive artifacts from exact internally loaded/sealed source.
Known unsupported source shapes generate no artifact. Unexpected generation/SQL
failures roll back revision, head, event, receipt and result together. Replay
creates no implicit cache-generation work. Explicit backfill accepts only source
identities, locks/revalidates that source, and changes derived rows alone. Head
advance does not retarget a historical backfill; concurrent source updates are
blocked/rechecked. Generated artifact byte size/cost must be measured.

Validation: source proof/corruption, read-only role, missing/unsupported fallback,
mutable and equal-instant-offset memory keys, source withdrawal at unchanged
revision, historical/new-revision reads, concurrent backfill/publication,
same-ID and descendant replay, complete publication/cache rollback and migration
roundtrip. Run owning PG cohorts in a verified disposable task database, never
through destructive test fixtures against serving databases. Then measure native
10k actual-store cold/warm route with exact Core/Buddy pins and ordered DTO/citation
parity, plus affected write costs. 539 ms file-backed feasibility has insufficient
margin to claim V8 acceptance; actual-store/current Buddy evidence owns that gate.

Retention: this checked-in handoff is the current state; the task scratch
preflight and unique verification evidence remain retained until store delivery. Cleanup only after active-process/mount/dirty-data/unique-commit
checks and explicit removal scope; no removals authorized by this preflight.

## Settled implementation decisions

The row key is source(space,revision) plus codec/parsed-format versions. Bind full
envelope digest, graph SHA, artifact byte length and artifact SHA independently.
New-publication insertion never silently accepts a conflicting artifact. Explicit
identity-only backfill may replace a corrupt derived row with deterministic
regeneration from the locked, fully verified source; identical content is
idempotent. Source-row -> artifact-row is the consistent lock order.

SQL fetch must combine size-check and conditional BYTEA selection in one snapshot
so oversized data never transfers to Python; no separate check/fetch race.
The optional reader remains separate from the required repository protocol.
Existing public parser/cache method signatures stay intact.

Contract/structural rejection of otherwise publishable native opaque source
means artifact-ineligible, not publication rejection. Source-verifier failures
never become fallback. Unexpected generator faults and artifact SQL failures
roll back the whole existing publication transaction. The common insertion hook
also covers native source admission/extension; their rollback/eligibility paths
are included without changing their admission semantics.

## Reviewable slice and paths

This is one serial PR with codec origin #217 and current Git base accepted #221
(6c61e8e73faf6d02c0d1f73692f185a55c050a4f). The table, generation, cache/read
integration and owning transaction tests form one capability; Buddy adoption is
separate. Intended paths: one new migration, one private Postgres artifact helper,
vnext_knowledge.py, native_source_access.py, private factory eligibility error
classification if necessary, owning unit and integration tests, affected migration
head expectations and this handoff. Record material expansion before absorbing it.

## Current state and next question

Implementation is complete and independently code-approved. Migration0022,
bounded BYTEA reader, transaction-bound generation, locked identity-only backfill,
optional context integration and exact immutable cache keys preserve full source
verification before lookup and fresh provenance on every opening. The current-row
body-manifest mismatch and nonbytes-reader findings are repaired and independently
approved. Future stored versions remain absent/fallback; malformed current rows
fail closed. Exact storage head9f0b8062baced9803affd47a187e2d33e2883ec7 passed all
CI44387731401 jobs before this rebase/documentation refresh.

217 focused storage units passed;84 affected PostgreSQL publication/prospective,
source admission/extension, artifact and migration checks passed before a final
old-data fallback addition. The owning artifact cohort then passed20 tests.
Proof includes SELECT-only/read-only access, withdrawal across memory hits,
corruption before memory lookup, bounded transfer, forged bytes, atomic
revision/head/event/receipt/result rollback, explicit repair, concurrent source
update blocking and head advance preserving historical backfill. All role/grants
were rolled back and role absence verified. Rebased exact-head CI remains required.

Accepted compute work: #219 defers unrequested primary-record map hashes,
#220 removes per-value recursive callable cycles, #221 releases private models
at their last use. #222 separately sparsifies temporary index buckets; it has
independent approval but remains pending exact final CI/acceptance. The source
proof, public validation, structural checks and semantic digest remain mandatory.

Actual-store candidate evidence uses retained Buddyca5a0450489a94cd364183af1c53d3f041ad7d0f,
fresh parsed caches and warm DB/OS. All candidates passed full DTO parity against
an untimed same-fixture ordinary-parser correctness oracle and exact reopened
citation SHA a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
These are candidate fixtures, not serving restart/deployment acceptance.

- Original actual-store Core041e42d:558ms cold,209–212ms warm;2.29MB transfer/
  checksum12ms; generation0.82–1.09s; second-hop prepare+commit10.58s.
- Combined accepted hash/validator verification19eb48c:551/562/559ms cold,
 206–212ms warm. Full GC still93–94ms despite sharply fewer cyclic objects.
- Model-lifetime verificationa05e157:537/518/665ms cold;227–250ms warm plus346ms
  full-GC outlier. Generation1.13/1.05s; second-hop13.31s.
- Sparse-index verification9de8566:609/594/661ms cold,233–283ms warm;
  generation1.26/0.63s; second-hop11.70s. A controlled builder-only comparison
  on the same retained payload measured79–81ms sparse versus80–84ms parent,
  with full parsed equality and fewer allocations. This is not route acceptance.

The retained~540ms cold reference is not consistently met. Independent runs also
vary in get_revision/database/GC costs, so they do not isolate causal timing
improvements or regressions. No frozen baseline rerun, write parity, current Buddy
adoption, V8 acceptance or cutover. Keep the PR draft until remaining performance
and integration obligations are satisfied.

Next primary question: which remaining source verification/decoding allocations
and live-heap scans can be removed while preserving full independent verification,
and can repeated actual SQL/current Buddy cold and warm reads meet the retained
reference without shifting cost into publication or latency outliers? Required
successor evidence includes restart/eviction/new-revision, affected routes and
matched writes, then the current deployment and V8 joint record.

Retain this handoff as living state; detailed history belongs in PRs and scratch.

## Retained verification resources

The existing task-owned codex_vnext_cold_20261118 database was confirmed present
and idle (zero clients) before destructive isolated-test fixtures ran. Those
fixtures migrated/truncated only that verification database. The temporary
SELECT-only role and grants were rolled back; the test checked role absence.
No serving data, new worktrees, environments or containers were changed.
The existing worktree/env/database and preflight draft in scratch/v8-core remain
retained by this active lane for delivery/review. Cleanup follows delivery with
explicit scope and active-process/mount/dirty-data/unique-commit checks; no removals
or reclaimed bytes.

Actual-store probe resources under task scratch/v8-core are retained:
`test_v8_postgres_artifact_http_candidate.py`,
`native-postgres-artifact-candidate-041e42d.{json,log}`, its pytest directory and
`native-artifact-eager-hash-work-count.json`. The probe fixture created/dropped
its own databases. The component work count used the retained payload under a
synthetic lab envelope; it is diagnostic only, not HTTP/authority acceptance.
The active performance lane owns these resources for review/next optimization;
cleanup follows delivery with the existing checks and explicit scope.

Additional retained verification resources: codex/vnext-record-hash-store-verification
atcb779c1, codex/vnext-json-cycle-store-verification at19eb48c,
codex/vnext-lifetime-store-verification ata05e157 and
codex/vnext-sparse-store-verification at9de8566; corresponding candidate probe
scripts, JSON/logs and pytest directories in scratch/v8-core, plus the controlled
hash/sparse component reports and allocation/lifetime diagnostics. The active
performance lane owns them for integration/review; cleanup follows delivery with
explicit removal scope and process/mount/dirty-data/unique-commit checks. No new
worktrees/env/containers or removals. Fixture databases were created/dropped by
the probes; serving data was untouched.
