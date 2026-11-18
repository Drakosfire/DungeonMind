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
Focused Ruff and git diff checks passed. Candidate timing remains pending.

## Workspace retention

Reuse the existing task-owned Core worktree at
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for this PR and subsequent serial optimization work. Cleanup follows
review and delivery, after dirty-data and unique-commit checks.

The disposable database codex_vnext_cold_20261118 is retained on container
4df9d2e50d09 for candidate verification. Remove it after this task's database
checks and any active users finish. No new worktree, cache or environment was
allocated. Existing task environment and retained evidence were reused.
