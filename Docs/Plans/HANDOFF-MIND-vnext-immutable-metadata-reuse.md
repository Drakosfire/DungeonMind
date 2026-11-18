# Reuse immutable parsed assertion metadata

Status — implemented, candidate measurement and independent review pending.

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

Native candidate route timing and exact-head CI remain pending. Reuse the
retained 10k native fixture and compare against the retained reference.

## Workspace retention

Reuse the existing task worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
The task owns the worktree and retains it for the stack, review and delivery.
Existing environment and scratch are reused. Cleanup follows review after
dirty-worktree and unique-commit checks. Candidate scratch cleanup follows
diagnosis, as recorded in the parent handoff.
