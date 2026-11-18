# Implement exact current-source verification proof reuse

Status: ACTIVE. Owner: Elderwyld pre-cutover optimization lane.
Authority: operator goal and implementation/review/merge authority; design226
24a8bdf58c8c1a5c45f1d6dbdfec2a6b1eec08a6 independently APPROVED, no blockers.
Stack: parent PR226 design branch; this Core implementation PR targets that parent
until226 merges, then rebase/retarget main. Merge226 before implementation; only
then rebase separate draft storage218. Buddy wiring/pin is a later serial slice.

Outcome: explicit reader-owned single-entry, byte-capped cache of successful pure
source verification. Every get_revision fetches complete current raw source;
exact type-sensitive full-row representation equality may reuse immutable proof.
All changes/misses run unchanged verification; source/provenance admission stays
fresh and absent/corrupt/unavailable source cannot hide behind a memory hit.

Six-path lease: private postgres/_revision_verification_cache.py,
postgres/vnext_knowledge.py, postgres/vnext_sources.py,
unit/test_postgres_revision_verification_cache.py,
integration/test_postgres_revision_verification_cache.py, this handoff.
No migration, artifact store, public contract/port requirement, Buddy, GC tuning,
prewarm, deployment, cutover or source publication change. Default no injection
preserves ordinary path. Native source repository forwards optional cache only.

Key: explicit verifier version + requested identity + all scalar/raw JSONB text
fields. Strings/None/timestamp representation snapshots only, never model/JSON
Python equality. Immutable proof retains canonical envelope/payload and verified
hash only; each return reconstructs fresh Python-mode envelope state. Required
max_bytes covers raw and canonical strings; one entry, no implicit global owner.
Concurrent clear uses generation protection; no lock around DB/verification.
Failed verification/oversized entries must not replace the last good proof.

A miss decodes full raw JSON and calls original _reconstruct at the same active
stack depth as ordinary _read_revision. Deep-input detection/decoder recursion
failure bypasses back to original read at its original depth, after the cache
helper returns. No225parser reuse. Fail closed on ordinary errors, never admit
using checksums/IDs alone. No cached transaction, model, context or permission.

Proof: serial fresh DB fetch count versus full-verification count; all columns,
number/offset/exact text drift, unknown envelope/self-consistent forged identity,
missing row/errors, input/caller mutations, clear/byte cap/concurrent namespace
isolation and deep boundary. Direct PG corruption tests against ordinary failure
results before parsed lookup. Owning unit+PG checks, cumulative independent review
and exact CI required; actual full-app/memory/write/affected-route/V8 acceptance
remains separate. Frozen classic baseline must not be rerun.

Reuse existing task-owned Projects Core/Buddy checkout/env, scratch/v8-core and
UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8. Retain new evidence/refs for dependent
integration with cleanup follow-up after explicit scope/process/mount/dirty/
unique-data checks. No new worktree/env/cache directory or manual removals.
