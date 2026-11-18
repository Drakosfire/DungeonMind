# Share immutable empty entries across dense native indexes

Status: COMPLETE, accepted Core PR #223. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal and lane implementation/
review/merge authorization. Exact base: accepted #222
9f4e3469f2244e5c79ff04295e63d979b3251dbc.

Outcome: allocate one immutable (entity_id,()) entry per entity and reuse it
across the seven dense per-entity indexes when that index has no memberships.
Preserve every key, sorted tuple, iteration order, FrozenDict type, eager index
hash behavior, copy/pickle and semantic digest. Sort the common key domain once.
Primary records, validation, admission, public signatures and formats stay fixed.

Evidence: retained10k graph has60014 empty final entries across10004 keys,
represented by60014 separate pair objects;50010 are redundant immutable entries.
Buddy3994 accepted citation parse reuse, but actual socket eviction642–655ms and
historical-return696–707ms still exceed retained~540ms. No performance baseline
rerun. Work count is not evidence that this change improves latency.

Scope: frozen_json.py private owner-validated dense-index factory, builder.py
finalization, tests/unit/test_vnext_sparse_index_builders.py regressions, and this
handoff only. No PostgreSQL, cache/read-source authority, Buddy, public contract,
profile, GC policy, prewarming or cutover changes. Existing sparse accumulation
and referential-validation ordering remain unchanged.

One serial compute PR from the pinned accepted base; no behavioral dependency
on unmerged storage218. After independent cumulative review and exact CI, accept
this compute PR, then rebase storage218 and measure the combined actual socket
path with accepted Buddy cache reuse. Pinned local combination may verify before
acceptance. Do not silently fold the compute change into the storage PR.

Proof: empty/sparse/dense/self-loop/alias/input-permutation graphs retain all
index keys/memberships and hashes; immutable sharing removes duplicate pair
allocations; nonempty values remain distinct; source input mutations cannot
alter results; copy/deepcopy/pickle and concurrent build behavior stay sound.
Compare ordinary/artifact complete models and semantic digests, retain current
structural/error checks, measure actual full-app/readiness/cold/warm/eviction/
new-revision/history/citation and generation costs before claiming speed.
Public FrozenDict construction and standalone uses retain existing semantics.

Reuse existing Projects Core/Buddy checkout/env. Temporary evidence stays under
v7-elderwyld-scope/scratch/v8-core (filesystemUUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8).
Retain verification refs/probes/logs for review and remaining integration; cleanup
after delivery with explicit scope and active-task/process/mount/dirty/unique-data/
commit checks. No deletion permission inferred. V8/cutover remains gated.

Acceptance: reviewed head96027747b45b786fcca50bce69f89253058c7873 merged as
ad87ab1a42ed6d311e8f30e1536dbad12a94dfa4. Independent cumulative review approved;
222 focused tests and all exact-head CI44405940347 jobs passed. Retained10k
full-model/hash parity confirms60014 empty entries now use10004 pair objects,
removing50010 allocations. This is a work-reduction acceptance, not V8 acceptance.
Actual full-app composition9b6b582 with Buddy174639d passed exact response/citation,
fresh source/revision and lifecycle assertions. First reads452–514ms, warm200–244ms,
eviction647–718ms and new revision659–737ms; historical return462–490ms.
Citations187–207ms fetch no duplicate artifact. Full-heap GC193–241ms remains in
miss tails. No stable latency benefit established; frozen baseline not rerun.
Storage218 rebases on this merge; performance/cutover gates remain open.
