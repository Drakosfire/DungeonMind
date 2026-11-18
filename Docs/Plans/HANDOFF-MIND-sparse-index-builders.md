# Sparse temporary structural index builders

Status: ACTIVE. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal. Parent: accepted #221 merge6c61e8e73faf6d02c0d1f73692f185a55c050a4f.

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
One independently reviewable serial compute slice. #221 is accepted; this PR
is rebased onto its merge. Review/test/merge it, then rebase storage #218. Pinned local combination may verify
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

Current evidence: independent APPROVEde2bf6381e8781bed7ac89064508efbf7d59b121 against18c8f90,214 author checks and213 independent checks plus12 parent/ordinary/artifact full-field/index/digest/hash comparisons. Local SQL verification9de856667db1d8742d7e909748fe17f3a16ca114 cold609/594/661ms, warm233–283ms; full DTO/exact citations match. Generation1.26/0.63s, second-hop11.70s. Full GC still costs133ms in one cold sample; source verification also varied196–244ms. This does not pass the~540ms gate or establish a causal component regression. Controlled same-payload builder comparison now completes the component proof: sparse79–81ms versus parent80–84ms across eight alternating trials, with full parsed equality. This removes temporary allocations without an observed component penalty; it does not establish end-to-end latency acceptance. No baseline rerun. Retain test_v8_postgres_artifact_sparse_staged_candidate.py, native-postgres-artifact-sparse-staged-9de8566.{json,log}, pytest directory and local codex/vnext-sparse-store-verification at9de8566 under the active lane's existing cleanup obligations. ProbeDB was dropped.

Retain sparse-index-controlled-component.json (same retained10k payload, synthetic lab envelope, isolated builder-only comparison with pre-trial diagnostic gc.collect). No production GC settings or baseline route were changed.
