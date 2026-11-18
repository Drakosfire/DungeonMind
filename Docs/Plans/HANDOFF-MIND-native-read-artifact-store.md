# Native read-artifact PostgreSQL storage and integration

Owner: active Elderwyld performance lane. Parent: Core #217 exact
aef8883238cc7c9c993e42ed666cd99bdfb1847f, accepted #217 squash merge.
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

Ordering: #217 accepted merge -> store/read/write/backfill PR -> Buddy adoption.
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

Retention: this draft stays in task scratch for handoff preparation/review. It
will be incorporated into the owning PR's durable handoff and retained until
store delivery. Cleanup only after active-process/mount/dirty-data/unique-commit
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

This is one serial PR based on accepted #217. The table, generation, cache/read
integration and owning transaction tests form one capability; Buddy adoption is
separate. Intended paths: one new migration, one private Postgres artifact helper,
vnext_knowledge.py, native_source_access.py, private factory eligibility error
classification if necessary, owning unit and integration tests, affected migration
head expectations and this handoff. Record material expansion before absorbing it.

## Current state and next question

The migration, bounded BYTEA reader, synchronous transaction-bound generation,
identity-only locked backfill and optional context/cache integration are implemented.
The private generator classifies only known unsupported wire forms, expected
contract-validation failures and structural failures as artifact-ineligible.
Source verification and unexpected faults remain typed failures/rollback.

Current verification: 214 focused unit checks pass. The affected PostgreSQL
publication/prospective, source admission/extension, artifact and migration
cohort passed 84 checks; a subsequently added old-data fallback test brings the
owning artifact cohort to 20 passing checks. Proof includes SQL/receipt/result
rollback, SELECT-only role and read-only transaction, source withdrawal across
memory hits, corruption before memory lookup, bounded transfer, explicit repair,
source-update blocking during backfill and concurrent head advance preserving
the historical target. Role/grants are rolled back and absence is checked.

Initial independent review found current-row/body manifest disagreement could
fall back. The repair makes the optional reader's contract explicit: return only
current-version bound rows, or None for absent/unsupported stored versions. A
returned body's differing wire/parsed manifest now fails closed, without another
full JSON parse. Unit/SQL cases distinguish inconsistent current rows from
genuine future-version rows. Delta review and exact-head CI remain pending.

Actual-store candidate Core041e42d3dc5f37c28a362607b0b3a4a3457434f2 with retained
Buddyca5a0450489a94cd364183af1c53d3f041ad7d0f measured 558 ms cold and209–212 ms
warm, with full DTO parity against an untimed same-fixture ordinary-parser
correctness oracle and exact reopened citation SHA
 a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
The first artifact lookup/transfer/checksum took12 ms for2291524 bytes.
The fixture used a fresh parsed cache and warm DB/OS; it is not restart/current
serving deployment evidence. The successful read path is unchanged by the
manifest-error repair; the candidate pin is recorded explicitly.

10k generation consumed0.82–1.09 seconds inside publication transactions.
Second-hop prepare+commit took10.58 seconds, including0.82 seconds generation.
Write parity is not established. Both cold latency against the retained540ms
reference and generation costs require further optimization before adoption.
The frozen baseline was not rerun. No production V8 acceptance or cutover.

A retained-payload component work count found20008 assertion hash calls and
20008 metadata hash calls during immutable construction, with no explicit map
hash request. Prior profiling attributed time to FrozenDict construction. This
is the next bounded compute question; any change to hashing will be a separate
reviewable PR, not silently absorbed into this persistence slice.

Next question: can unnecessary immutable-map hash preparation be removed while
preserving all hash/immutability behavior and improve actual SQL route/write
costs enough for acceptance? Remaining obligations also include complete review,
exact-head CI, current Buddy adoption, repeated/restart/eviction/new-revision
performance checks and affected write-route comparison to retained evidence.

Retain this handoff as living state and replace stale sections as implementation
and review evidence arrives. Detailed history stays in PRs and task evidence.

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
