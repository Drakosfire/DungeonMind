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

Initial verification: 73 affected PostgreSQL checks passed across artifact,
publication/prospective, source admission/extension and migration cohorts. Four
additional owning checks subsequently passed, for a 12-check artifact cohort:
SQL/receipt rollback, transactional SELECT-only role (rolled back afterward),
source withdrawal across actual artifact memory hits, and ordinary source
corruption detection before a memory hit. The initial seven cache tests plus
12 source-refresh checks pass. Focused Ruff and cumulative diff checks pass.

Still required before acceptance: source-update/head-advance backfill races,
historical/descendant/prospective artifact rollback details, actual-store native
HTTP cold/warm parity and write-generation costs, complete independent review
and exact-head CI. The codec-only539ms file-backed result has not established
actual-store/current Buddy acceptance. Next question: does the complete SQL path
preserve the same result and meet latency requirements?

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
