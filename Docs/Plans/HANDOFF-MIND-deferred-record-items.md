# Avoid retained pair tuples in private parsed record maps

Status: COMPLETE, accepted Core PR224. Owner: Elderwyld pre-cutover optimization lane.
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

Delivered as a serial compute PR from223. Reviewedba0d02444d62bfa0943209c9c84314323c790316
merged asf174923bf7962f78d14faeb36a41f77004520676; all CI44408031871 jobs passed.
Independent cumulative review approved, no findings. Storage218 is rebased on
this merge; it remains draft pending performance and consumer gates.
Proof: complete ordinary/artifact parity; sorted iteration and errors; input
mapping isolation; requested hash parity/caching; all pickle protocols;
concurrent hash behavior; no retained pair tuples at0/10/50000 entries even after
hash/pickle requests. Actual full-app candidate measurement before speed claims.

Reuse existing task-owned Projects Core/Buddy checkout/env. Evidence under
v7-elderwyld-scope/scratch/v8-core, verified UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8.
Retain unique refs/probes/logs for review/integration, with cleanup follow-up once
explicit scope and process/mount/dirty/unique-data checks allow. No new worktree,
environment or serving changes. V8 and cutover remain gated.

231 focused checks pass. Synthetic10k/50k entities and20k/100k assertions preserve
complete ordinary models/hashes and remove30002/150002 retained primary pairs.
Full-app candidateb2263ae/Buddy174639d passed exact responses/citations and fresh
verification/provenance/new-historical checks. First probe timing was excluded
because a concurrent allocation count overlapped. Separate candidate-only rerun
passed in91.42s: first447–548ms, warm201–266ms, eviction664–757ms, newrevision
470–513ms, historical710–846ms, firstcitations193–262ms with0duplicatefetch.
Eviction fullGC207–217ms persists. No stable end-to-end benefit established;
allocation reduction is accepted, V8/cutover is not. Frozen baseline untouched.
Both probes/count process terminal; fixtures dropped owned source DBs. Retain
count evidence and candidate probes/JSON/log/pytest dirs and unique combinedref
b2263ae for dependent integration under existing ownership/cleanup follow-up.
