# Release private artifact validation models at last use

Status: ACTIVE. Owner: Elderwyld pre-cutover performance lane.
Authority: operator optimization-before-cutover goal and accepted source-bound
artifact design #216/#217. Base: accepted #220 merge
8f686bf4c21944a9564c76d24386de660aef6673.

Outcome: retain public validation models only until their last assertion use,
while preserving once-per-distinct-byte validation and immutable record sharing.
The retained 10k payload diagnostic found10003 LiteralValue,1 TermRefValue,
2 EntityRefValue and2 AssertionMetadata instances still live at index construction,
then none after the factory returns. They are no longer needed once rows freeze.
Latest actual-store candidate551/562/559ms cold still misses retained~540ms.
No frozen baseline rerun; production acceptance and cutover remain gated.

Scope: private _source_wire.py callback lifetime hints derived from exact packet
references, _read_artifact.py model memo eviction, owning regression tests and
this living handoff. First control-plane commit settles accepted #220 state.
No public API, wire/parsed-format version, source proof, schema, index, digest,
admission, PostgreSQL, Buddy or production GC configuration changes.

One independently reviewable compute PR from accepted main; storage #218 remains
separate. Merge this slice after exact cumulative independent review and CI,
then rebase #218 onto it. Local pinned verification may combine both beforehand.
No new worktree/environment; reuse existing task-owned Projects checkout.

Validation: complete parsed/index/digest/representation equality; repeated,
interleaved and unique references; once-per-distinct validation; release before
index construction and between independent rows; malformed references and forged
proof still fail closed before indexes. Existing concurrency, schema and boundary
regressions stay green. Then measure combined actual PostgreSQL route cold/warm,
GC and generation/write costs with full DTO and exact citation parity. Candidate
results do not prove current deployment or V8 acceptance.

Retained resources: existing worktree/env and scratch/v8-core lifetime preflight
JSON, candidate probes/logs and local verification refs remain owned by this
active lane for integration/review. Cleanup follows delivery with explicit scope
and process/mount/dirty-data/unique-commit checks. No removals or reclaimed bytes.
