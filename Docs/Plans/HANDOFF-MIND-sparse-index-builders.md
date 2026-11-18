# Sparse temporary structural index builders

Status: ACTIVE. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal. Parent compute PR #221
at18c8f901fd0fcf16fedc7a5b17ad1844212b0ccc, based on accepted #220.

Outcome: allocate temporary per-entity/evidence lists/sets only for actual index
entries. Final immutable indexes must still contain every entity/evidence key,
including empty tuples, with unchanged order, semantics and digest. The builder
currently creates six mutable collections per entity before populating indexes,
even with only two edges and no aliases in the retained10k fixture. Last-use
model release alone leaves full-GC outliers (537/518/665ms cold candidate).

Scope: builder.py structural accumulation/finalization, owning unit regressions
and this living handoff. No public signature/format/schema, primary records,
validation, admission, storage, Buddy or GC configuration change. Maintain exact
ordinary and artifact parser behavior, referential error order, sharing and hashes.
One independently reviewable serial compute slice. Merge #221, rebase this PR,
review/test/merge it, then rebase storage #218. Pinned local combination may verify
candidate route before acceptance. Storage and compute remain separate PRs.

Required proof: empty/sparse/dense/disconnected/self-loop/duplicate-neighbor graphs,
all final index keys and sorted tuple contents, every index versus independent
record-derived expectations, input permutation and semantic digest equality,
ordinary/artifact equivalence, structural failures unchanged. Allocation work
regression must show adding isolated entities/evidence does not allocate mutable
index buckets and that actual memberships still do. No timing-only unit threshold.
Measure actual SQL cold/warm/write generation with ordered DTO/exact citations.
Do not rerun frozen baseline. V8/current serving acceptance and cutover stay open.

Reuse task-owned Projects worktree/env; retain probes/logs and verification refs
for active review/integration. Cleanup follows delivery with explicit scope and
process/mount/dirty-data/unique-commit checks. No removals or reclaimed bytes.
