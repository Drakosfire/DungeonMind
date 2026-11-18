# vNext cold read reconstruction

Status — implemented and independently reviewed before rebase; exact-head
CI and rebase delta review pending.

## Scope and dependency

Optimize Elderwyld's native vNext experience before cutover preparation.
V8 requires a comparable native cold neighborhood read at or below the retained
approximately 540 ms classic reference, preservation of warm performance,
ordered results, authorization, source withdrawal and exact citation bytes.

Core #213 merged as 5a3158d5e90a50701948e29cf3be01e088e0edbf and restored
current validation. This PR is rebased onto that accepted main. Its own scope
is the PostgreSQL reconstruction adapter, reconstruction regressions and this
handoff. Bulk decoding #214 follows this slice directly. Metadata reuse #212
was withdrawn after review. Buddy adopts accepted Core pins in its own lane.

## Implementation

Stored reads recompute payload hash and revision ID directly using existing
canonical functions. The canonical payload text is serialized once and reused
for hashing and the immutable snapshot. The full publication command and its
redundant recursive JSON validation are removed from the read path.

Envelope validation, record fingerprint, column consistency, payload hash
and revision identity checks remain enforced. PostgreSQL JSONB already
supplies canonical JSON-compatible value types. The old command construction
did not perform domain graph-schema validation.

## Verified evidence

37 focused author unit cases and all 14 PostgreSQL publication cases passed.
The new reconstruction tests cover removed command-validation work and
payload, identity and column corruption. They skip when psycopg is absent.

Independent read-only review of exact 7d8d150c against a672791b found no
actionable issues. The reviewer ran 11 reconstruction cases and compared old
and new reconstruction across 24 payload/envelope combinations including
Unicode, numeric, parent and migration-origin variants. Canonical hash/text
reuse was equivalent. The adapter and reconstruction-test blobs remain
unchanged by the rebase onto #213.

At runtime a04245cb with retained Buddy ca5a0450489a94cd364183af1c53d3f041ad7d0f,
the native-only 10k fixture measured 1840 ms cold and 264–296 ms repeated.
A separate run measured 1666 ms cold. Both retained the ordered three-node,
two-relationship response and exact citation SHA-256
a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
These diagnostic runs remain above the cold gate and do not establish serving
performance. The retained baseline was not rerun.

The candidate parse profile reports 1.048 cumulative seconds in parsed-model
construction, including 0.407 in semantic digest computation, plus 0.511 in
contract decoding and 0.121 loading/checking the stored payload. These are
nested profile timings from a separate run.

## Retention and continuation

Task owner retains the existing Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind
for review and stack delivery. Existing environment and caches are reused.
The disposable codex_vnext_cold_20261118 database on container 4df9d2e50d09
is retained for verification; remove it after database checks and active users
finish.

Evidence remains under the task's scratch/v8-core directory. Retain
test_v8_native_cold_candidate.py, native-cold-candidate-a04245c.json/log,
test_v8_native_cold_candidate_profile.py and
native-cold-candidate-6f4e32b-profile.json/log for diagnosis.
candidate-a04245c-pytest and candidate-6f4e32b-profile-pytest are disposable
task outputs pending cleanup after diagnosis. Fixture-created databases were
dropped by teardown. Worktree cleanup follows review/delivery after checking
active processes, dirty data and unique commits.
