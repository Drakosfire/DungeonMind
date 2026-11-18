# Avoid retained pair tuples in private parsed record maps

Status: ACTIVE. Owner: Elderwyld pre-cutover optimization lane.
Authority: operator optimization goal and implementation/review/merge authority.
Exact base: accepted223 mergead87ab1a42ed6d311e8f30e1536dbad12a94dfa4.

Outcome: private owner-validated record maps retain a sorted owned dictionary,
not a second tuple of (key, record) pairs. Materialize the same ordered pair
representation only when explicitly hashing or serializing. Preserve public
FrozenDict construction, iteration, equality, repr, errors, copy/deepcopy, pickle
and requested hash behavior. No record mutation, format or authority change.

Evidence: retained actual socket eviction/new-revision misses include193–241ms
full-heap GC; no production GC tuning is authorized by this slice. A synthetic
10k-entity/20k-literal parsed graph contains30002 primary-map pair entries;
tracked tuple count30047. Collection-trigger phase does not prove object costs.
Removing these pairs is a measured work hypothesis, not latency acceptance.
Frozen baseline must not be rerun. No graph prewarming or verification bypass.

Three-path lease: application/vnext/frozen_json.py, existing
unit/test_vnext_deferred_record_hash.py and this handoff only. No builder,
contracts, source wire, PostgreSQL, Buddy, GC settings, cache capacity/lifecycle,
publication or cutover edits. Private factory accepts owner-validated immutable
records; public constructor keeps eager hash and tuple storage as before.

Serial compute PR from223. Draft storage218 remains separate and gated; rebase
it only after this slice is accepted, or retain pinned combined verification.
Proof: complete ordinary/artifact parity; sorted iteration and errors; input
mapping isolation; requested hash parity/caching; all pickle protocols;
concurrent hash behavior; no retained pair tuples at0/10/50000 entries even after
hash/pickle requests. Actual full-app candidate measurement before speed claims.

Reuse existing task-owned Projects Core/Buddy checkout/env. Evidence under
v7-elderwyld-scope/scratch/v8-core, verified UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8.
Retain unique refs/probes/logs for review/integration, with cleanup follow-up once
explicit scope and process/mount/dirty/unique-data checks allow. No new worktree,
environment or serving changes. V8 and cutover remain gated.
