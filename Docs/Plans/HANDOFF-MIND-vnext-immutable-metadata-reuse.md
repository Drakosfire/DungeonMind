# Reuse immutable parsed assertion metadata

Status — implemented, candidate route verified, independent review pending.

## Scope and topology

Reduce repeated construction and semantic normalization of equal assertion
metadata while preserving the full parsed revision, indexes and semantic digest.

This is a serial stack on Core PR #211, branch
codex/vnext-cold-revision-reconstruction, exact parent
7d8d150c9d89be22f2849abedd94d863211eb2a1. Merge #211 first, then rebase this
slice onto main and review its own cumulative diff before merge. Buddy adoption
follows accepted Core work.

The user requires performance acceptance before V9 cutover preparation.
The retained comparable classic cold reference is approximately 540 ms.
This slice alone does not establish that gate.

## Implementation and review map

builder.py keeps one build-local metadata cache entry. Equal public contract
metadata reuses a deeply immutable ParsedAssertionMetadata. The mutable cache
key is deep-copied on a miss. Referential integrity checks still run for each
assertion. Input contract instances remain caller-owned.

model.py reuses normalized metadata only for the exact same immutable metadata
object. The canonical semantic payload still includes metadata for every
assertion, preserving digest meaning and output bytes.

No state is shared between builds. Distinct metadata retains its own visibility,
scope, standing, temporal values, domain payloads and evidence.

## Verification

50 parsed-revision and new metadata-reuse cases passed. New checks cover one
metadata construction for repeated equal inputs, deep output immutability,
distinct evidence/visibility, mutation during input iteration and equal
digests for shared versus separately allocated immutable metadata. The
full-variant fixture retains the exact parent digest. A direct comparison
against the parent builder also produced equal parsed revisions.

At Core f75bc88d607a79973fb8e2815bad89828267ef3f and retained Buddy
ca5a0450489a94cd364183af1c53d3f041ad7d0f, the native-only 10k candidate
measured 1683.04 ms cold and 316.52, 337.93, 304.10 and 310.19 ms warm.
Ordered labels, two relationships, identical repeat responses and exact cited
bytes matched the parent candidate. Citation SHA-256 remains
a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
The cold value overlaps prior candidate variation, so latency improvement
remains unproved. The removed construction work has a deterministic regression.
The cold-read acceptance gate remains open.

The parent CI passed lint, typing and minimal imports before unit failures
on inherited PDF import-policy/optional-dependency tests and stale classic
NeighborhoodResult field assertions. The adjacent read cohort reproduced the
latter failures. These require a separate bounded prerequisite repair.
Exact-head CI and independent review remain pending.

## Workspace retention

Reuse the existing task worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
The task owns the worktree and retains it for the stack, review and delivery.
Existing environment and scratch are reused. Cleanup follows review after
dirty-worktree and unique-commit checks. Candidate scratch cleanup follows
diagnosis, as recorded in the parent handoff.

The task retains test_v8_native_cold_candidate_f75bc88.py,
native-cold-candidate-f75bc88.json, native-cold-candidate-f75bc88.log and
candidate-f75bc88-pytest under the existing v8-core scratch directory for
diagnosis. Cleanup follows candidate verification. Fixture-owned databases
were dropped by the existing teardown. No baseline run was performed.
