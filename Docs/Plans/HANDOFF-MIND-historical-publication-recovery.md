# V10 prerequisite — read-only historical finalized-publication recovery

Status: COMPLETE — accepted and merged as Core PR #247 at
`d206e56a9aa34ae6eb6cc7ac61980a7ac8919c4d`. Owner MIND under the operator's full-lane design, implementation,
review and merge authority. Base `67db2e5cffa772467cec5cf911fea9683e6a0f8d`, branch
`codex/v10-historical-publication-recovery`, existing clean task Core checkout.
This nine-path assignment is pinned before runtime edits. Independent Hubble
readiness PASS; Aristotle supplied the read-only owning-family audit.

## Outcome and serial dependencies

Expose one explicit compatibility read that returns an already-verified terminal
publication, the same original durable review and original child envelope in a
coherent caller-owned aggregate. Reuse VerifiedPublicationHistoryEntry; success
requires non-null publication/review. Add a narrow protocol with only
read_verified_publication(world_id, operation_id), plus compatibility helper
read_historical_finalized_publication with existing V1/V2 receipt-family ceilings.
No new persisted/wire schema, expectation bag, table, migration or recovery ledger.

This Core capability preserves current publishers. Subsequent Buddy adoption must
authorize current owner/binding before I/O and independently match original signed
packets against immutable history before mutable run/source/head/expiry checks.
Old manual contribution_digest is not Core's reviewed-contribution digest. Then
remove absent-receipt write fallbacks and retire actual Core classic application,
HTTP and repository writers after all real consumers have explicit dispositions.
None never authorizes republishing or resolves an ambiguous original outcome.
Historical FirstWorld and accepted native/source-publication families stay separate.

## Exact nine-path write lease

1. This handoff, contract/evidence/limits only.
2. New src/dungeonmind/application/compatibility/publication_recovery.py: explicit
   historical read helper, ceiling and returned-selector/terminal checks. No fresh
   publisher/materializer import or host authorization policy.
3. Existing compatibility/__init__.py: explicit helper export only; sealed codec
   functions/manifest and mapping implementation digest remain unchanged.
4. application/repositories.py: narrow HistoricalFinalizedPublicationReader
   protocol, terminal-reader guarantee on existing caller-owned history entry.
5. infrastructure/memory/repositories.py: new read method and optional local
   reconstruction loaders only. Preserve all existing call defaults/publishers.
6. infrastructure/postgres/review_publication.py: new coherent read method only,
   reuse existing _load_verified with operation-local exact review/revision loaders.
7. New tests/unit/test_historical_publication_recovery.py: owning memory/helper
   and boundary proof, using existing immutable V1/V2 fixture families.
8. Existing tests/integration/test_postgres_review_publication.py: new owning
   SQL aggregate-read cases, preserving existing writer tests and helpers.
9. Docs/Handoffs/HANDOFF-v8-joint-acceptance-checkpoint.md: first-commit settlement
   of accepted246/4222/4224 and true next primary question; preserve V8/serving bytes.

Actual open Core158/143–150 are retained independent lanes. MIND allocates only
these new read regions, protocol/helper and owning proof; do not absorb older
publication/property/correction regions. If another path or new authority is
needed, rebrief/split before editing. Nine paths, one independently useful reader.

## Invariants and failure classification

- One PostgreSQL REPEATABLE READ READ ONLY transaction. Select exact World/op;
  verify requested keys and companion World/review/contribution/parent/child keys
  before caching. Reuse _load_verified on one cached review and original parent
  and child, return detached copies of the SAME verified objects. No ancestry walk.
- Memory: existing graph -> source -> review/contribution lock ordering throughout
  selection, verification/copy. Cross-check all three selected terminal indexes;
  operation-index miss checks other receipt indexes for partial-index corruption.
  Complete loss of every terminal record cannot necessarily be distinguished from
  absence. Do not invent a second truth store or repair indexes during reads.
- None means coherent absence only. Missing/corrupt companions, substituted valid
  rows, conflicting indexes, wrong hashes/timestamps or unknown stored family are
  persistence integrity failures. Storage unavailability propagates as unavailable.
  No broad exception-to-None fallback. Disallowed/invalid caller receipt ceiling
  is typed CapabilityDenied, never silent downgrade, data stripping or absence.
- Retained immutable source revisions and publication policies remain mandatory
  receipt verification dependencies. No current artifact lifecycle/body opening,
  source admission, current head, finalization, publication or materialization.
  Withdrawn current sources and descendant/rolled-back heads are not eligibility.
- Host ownership authorization precedes this privileged historical metadata read;
  it grants neither current source access nor fresh publication authority. Core
  verifies stored correspondence; Buddy still proves complete request equivalence.

## Required evidence

Unit/helper and adapter tests cover V1/V2 family ceilings, absence with finalized
review and writer tripwires, original after descendant/rollback/withdrawal,
caller-owned nested detachment, requested-key/valid-row substitution, missing and
corrupt review/contribution/parent/child/index/payload/timestamp/source-revision
companions, unavailable storage and no mutation. SQL proves readonly/repeatable
transaction and one original review/parent/child load with no ancestry/head/source
artifact reads. Preserve immutable-source/policy proof; no generic validator rerun.

Use retained Core unit/tool environments with unchanged dependency inputs; no
resync of Buddy/serving environments. Dedicated fixture-owned disposable SQL DB
on loopback32903 only; integration fixtures TRUNCATE, never use admin/operator DB
as test target. Set TMPDIR/UV_CACHE_DIR per process under task Projects storage.
Run owning unit/conformance and SQL cohorts, required Core lint/types and final
exact-head CI. Build/inspect installed wheel for direct helper boundary and
pinned source identity, explicitly distinguish Core's still-eager parent imports.
No frozen retrieval baseline rerun. Independent exact cumulative source/evidence
review, commit/push/PR and expected-head merge complete this slice.

## Current continuity and still false

Core246 accepted merge67db, exactfd345/review5988441626, all3CI44686872284 green;
actual WK348 native source consumer witness passed. Buddy4222 accepted merge7e35,
exact62b9/review5988377665; installed WK98/native96/auth315 and hosted1412 pass,
with explicit375PASS1staletestFAIL preservation diagnostic retained. Buddy4224
accepted merge30554065f3362c662b35484510b9c24dad6bf5db, exact0b2/review5988492229;
24 owning cases and1412 selectedhosted/build/canonical pass. Neither later merge
execution, broad full-backend green nor deployed cutover follows.

Broader GraphDocSource fresh-classic HTTP test expectations need explicit future
historical/test disposition. Buddy native presentation imports and direct classic
projection/recap-context capabilities still need isolation/disposition. Full Threat
entry-path matrix, old packet correspondence and external Core host consumers are
open proof gates. FullV10, compatible primary/fallback rollout, later-write-safe
rollback/restart/restore and deployedV11 remain open. No new bridge/ingestion.

## Resources

MIND retains existing task checkouts/envs and new reports under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope. Verified Projects UUID
48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and writable parents. No new worktree or manual
deletion. Any new package verification env/SQL fixture is task-owned, with explicit
lifecycle and approved-scoped cleanup follow-up after process/mount, dirty/unique
data and unique-commit protection. No reclaimed bytes claimed without measurement.

## Implementation checkpoint

Lease pin `ab3d4d4` precedes runtime edits. Existing publisher defaults and exact
legacy-codec functions/manifest remain unchanged. Working evidence:169 unit/
conformance cases passed; incremental corruption/policy checks9 passed; SQL39
passed after correcting the missing-row fault filter, plus4 additional unknown-
family/unavailability cases passed. All3 uniquely named fixture DBs dropped after
zero connections and confirmed absent. Initial validation-error classification
and test-harness failures are retained externally, not qualifying passes.
Core/PG type checks and changed-path lint pass. Final exact-head results, wheel
identity/origin proof, CI and independent acceptance belong in the PR/evidence.
No package-pin, frozen-contract, schema, migration or serving changes.

## Consuming-slice settlement of Core247

Accepted exact head `6987087a08458dce995510e69b45426d6c1febee` merged as
`d206e56a9aa34ae6eb6cc7ac61980a7ac8919c4d`. Hubble bounded ACCEPT review
`PRR_kwDOToHpZs8AAAABZPbwKQ`; CI44692015442 all three jobs succeeded:
3,220 core passes/11 skips;622 integration passes/one skip; benchmark smoke and
WK348 native source consumer witness passed. The installed minimal wheel
(no postgres extras) passed172 owning/conformance cases, with218 source files
independently equal to the committed source. Parent eager publisher loading was
explicitly recorded, not accepted as a current-import isolation proof.

Buddy later adopted this reader for ordinary manual, Worldbuilding and Recap
historical recovery; classic Threat HTTP mutation retirement is accepted at
Buddy4234/e4829505224a29ea9b4d3688ac22762588d60b05. Current serving cutover and
full V10/V11 were not established by those commits. The next Core import slice
addresses parent loading only; existing compatibility codecs/manifest and
historical review/receipt correspondence remain unchanged.
