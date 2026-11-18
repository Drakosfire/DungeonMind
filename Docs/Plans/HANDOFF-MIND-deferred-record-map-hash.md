# Defer unrequested immutable record-map hashes

Status: ACTIVE bounded compute slice. Owner: Elderwyld pre-cutover performance lane.
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
