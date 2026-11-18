# Defer unrequested immutable record-map hashes

Status: ACCEPTED in #219 merge371930d307be0dbaf946df06a7438b23ee3dd521.
Owner: Elderwyld pre-cutover performance lane.
Base: accepted codec #217 merge aef8883238cc7c9c993e42ed666cd99bdfb1847f.

## Outcome and scope

Remove hash preparation that the native read never requests. Retained 10k payload
work counts show 20008 assertion hashes and20008 metadata hashes during immutable
construction, with no explicit map hash request. Actual PostgreSQL storage candidate
#218 measured558ms cold versus the retained approximately540ms reference; artifact
lookup adds12ms and generation costs0.82–1.09s. The full performance gate is open.

This independent PR owns a private deferred-hash FrozenDict constructor, its use
for immutable primary record maps only in the private fast builder, and owning
immutability/hash/work-count tests. Public constructors/parser signatures, ordinary
builder behavior, facts, indexes, digests, authority and wire versions stay stable.
The deferred path accepts only internally owned immutable parsed-record mappings.
No PostgreSQL, Buddy, source admission, public contract or cutover change.

Delivery is parallel-independent of storage #218 at
f9ea1a3783cfacf643203e5b55b0a5d4e740ce23. Both base on accepted #217. Merge this
compute PR after its own review/CI, then rebase #218 onto the accepted compute
merge and verify the combined actual-store route. Buddy adoption follows accepted
combined Core evidence. A temporary local verification branch may combine the
pinned PR heads in the existing checkout; no new worktree/environment is needed.

## Required proof

Default FrozenDict construction remains eager. The private record-map path copies
and sorts its backing data, exposes no mutation, and computes the identical hash
only when explicitly requested. Hash caching, empty/nested/unhashable data,
copy/deepcopy/pickle behavior, source mutation isolation and concurrent calls must
remain sound. Deferred cache state is not semantic content or persisted data.

Compare complete parsed records/indexes/digests against ordinary parsing. Preserve
numeric representation, signed zero, offset timestamps and exact citation bytes.
Retain a regression proving no assertion/metadata hash calls on the fast path
without a map hash request, and correct results after explicit hashing.
Measure the candidate on the actual PostgreSQL route and generation path using
pinned combined Core/Buddy refs. Do not rerun the frozen baseline. Single diagnostic
samples cannot establish current-deployment/restart/eviction or write parity.

## Retention

Reuse the existing task-owned Core worktree and shared verification environment.
Evidence and any local verification branch remain owned by this active lane for
review and store integration. Record exact paths/refs and cleanup follow-up.
No removal is authorized here; cleanup follows delivery after active-process,
mount, dirty-data and unique-commit checks with explicit scope.

## Accepted evidence and successor

Exact44693c853d53f2a82766497115ada1f9c219eefe passed independent review and all
CI44378135459 jobs. 205 owning checks pass;227 combined store/compute checks pass.
Record/metadata hash counts fall from20008 each tozero until explicitly requested.
Controlled component trials show a modest saving, but combined staged SQL cold
reads546/547/560ms still miss the retained~540ms reference. GC2 costs89–99ms per
staged cold read. The JSON validator allocation handoff owns that next finding.
No performance/V8 acceptance or current Buddy deployment is claimed.

Retain local verification branch codex/vnext-record-hash-store-verification at
cb779c1cf95dcb168629fd38c6b92905e96678a7 (parents218f9ea1a3 and21944693c8),
controlled-component/staged HTTP JSON/log/probe outputs under task scratch/v8-core
for diagnosis and store integration. Fixtures dropped their test databases. No
new worktree/environment or removals; cleanup follows delivery with existing checks
and explicit scope.
