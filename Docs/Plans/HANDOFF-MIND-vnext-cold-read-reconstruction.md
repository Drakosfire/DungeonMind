# vNext cold read reconstruction

Status — implemented, awaiting independent review and candidate route measurement.

## Objective and gate

Optimize Elderwyld's native vNext experience before preparing cutover.
V8 performance acceptance requires the native cold neighborhood request to
meet or beat the retained comparable classic reference, preserve the native
warm advantage, and preserve ordered results, authorization, source withdrawal
and exact citation bytes. V9 preparation follows accepted V8 evidence.

The retained paired 10k route reference is approximately 2.12 seconds native
and 0.54 seconds classic cold, with native repeat reads of 378–387 ms.
Reuse the retained baseline and measure candidates.

## Evidence and ownership

The retained shared-route-cold profile places 2.885 of 2.910 profiled seconds
inside pinned context preparation. Parsing accounts for 1.994 seconds and
repository retrieval for 0.887 seconds. These nested timings describe a separate
profiled run and cannot be added to the unprofiled 2.12-second sample.

Retained evidence is under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/scratch/v8-core/,
including shared-route-cold-profile.log and shared-native-profile.log.

Core owns revision reconstruction, integrity and parsed indexes. Buddy owns
route composition and deployment adoption. Current source authority must be
opened afresh even when immutable revision work is reused.

## Serial slices

1. Core repository reconstruction, based on main a672791. Replace construction
   of a publication command during reads with direct payload hash and revision
   ID recomputation. Serialize canonical payload once for both hashing and the
   stored snapshot. Preserve fingerprint, envelope, column and identity checks.
   Include integrity tests and a regression rejecting publication-command
   validation during reads. This PR has no parent implementation PR.
2. Reassess remaining parsing work using retained profiles and current code.
   Deliver further independently reviewable Core changes as evidence warrants.
3. Buddy adopts accepted Core pins and measures candidate cold and warm routes
   against the retained baseline, checking affected routes and citation parity.
   Exact pins, outputs and latency evidence determine V8 acceptance.

The first slice alone does not establish latency acceptance.

## Validation

37 focused unit cases passed, including publication, source-context refresh
and 11 reconstruction integrity/work cases. All 14 PostgreSQL publication
integration cases passed in the disposable codex_vnext_cold_20261118 database.
Focused Ruff and git diff checks passed.

At Core a04245cb5886d17e4335611dcbf435a13aa4a060 and retained Buddy
ca5a0450489a94cd364183af1c53d3f041ad7d0f, a native-only candidate probe
using the retained 10k PostgreSQL fixture measured 1840.18 ms first request
and 267.78, 266.05, 296.01 and 263.77 ms repeats. Ordered labels were
Object 0, Endpoint, Object 1, with two relationships and one source anchor.
All repeated response bodies matched. The citation reopened exactly and
had SHA-256 a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
The candidate uses a retained Buddy pin to isolate Core work. This single
diagnostic run remains above the cold-read gate and establishes no current
serving latency claim.

The native-only probe, JSON result and log are retained in the evidence
directory as test_v8_native_cold_candidate.py,
native-cold-candidate-a04245c.json and native-cold-candidate-a04245c.log.
Its temporary pytest output directory candidate-a04245c-pytest is retained
for diagnosis and should be removed after candidate verification. Fixture
Core and APP databases were created and dropped by their existing test
fixtures. The original baseline was not rerun.

## Workspace retention

Reuse the existing task-owned Core worktree at
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for this PR and subsequent serial optimization work. Cleanup follows
review and delivery, after dirty-data and unique-commit checks.

The disposable database codex_vnext_cold_20261118 is retained on container
4df9d2e50d09 for candidate verification. Remove it after this task's database
checks and any active users finish. No new worktree, cache or environment was
allocated. Existing task environment and retained evidence were reused.

## CI scope amendment

The initial core CI job stopped on three inherited E501 violations in
world_graph_retrieval.py and its unit test. The repair wraps exactly those
three expressions in a separate commit. Python ASTs match before and after.
These two additional paths unblock validation and add no behavioral scope.

The next core job exposed two inherited missing-import diagnostics for the
optional pypdf extra. Targeted Pyright annotations on those imports preserve
runtime behavior in minimal installations. Reconstruction tests explicitly
skip when psycopg is absent, preserving the optional PostgreSQL dependency.

## Remaining parse profile

A separate candidate run at runtime-equivalent 6f4e32b measured 1665.54 ms
for its first HTTP request and preserved the same ordered result and citation.
A direct cProfile of that revision's parse reported 1.721 cumulative seconds:
1.048 in build_parsed_knowledge_revision, including 0.594 in the internal
record/index builder and 0.407 in compute_semantic_digest; 0.511 in contract
decoding; and 0.121 loading and checking the stored payload. These are nested
profile timings and are not additive end-to-end latency measurements.

The next slice should address complete-revision parsing and normalization,
with equality of immutable records, indexes and semantic digests established
against the current builder. Shared mutable contract state must not escape
through decoded results. This profile does not establish the cold-read gate.

Profile probe, result and log are retained as test_v8_native_cold_candidate_profile.py,
native-cold-candidate-6f4e32b-profile.json and
native-cold-candidate-6f4e32b-profile.log. The task owns the retained temporary
candidate-6f4e32b-profile-pytest directory; cleanup follows diagnosis. Both
fixture databases were dropped by their existing fixture teardown.
