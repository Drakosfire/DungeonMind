# Bulk contract decoding for native revisions

Status — implemented, candidate timing and independent review pending.

## Outcome and topology

Remove per-record Python model_validate dispatch while retaining the exact
public contract schemas for entities, assertions, aliases and evidence.

This slice is stacked on Core #212 at
56753c238d06f0a03801466776395118e673a54d.
The actual parent ref is codex/vnext-immutable-metadata-reuse; verify its exact
commit before rebase. Merge order is the validation prerequisite #213,
reconstruction #211, immutable metadata #212, then this slice. Each child
rebases onto its accepted parent merge before final review.

The user requires performance acceptance before cutover preparation.
The 540 ms retained classic cold-read reference remains an unmet V8 gate.

## Implementation and validation

Four module-local Pydantic TypeAdapters validate lists of the existing public
contract classes. The decoder normalizes each input iterable to a list,
preserving iteration behavior, and returns the existing tuple containers,
schema identity and payload digest. Existing typed failure classification is
retained. Public contract definitions are unchanged.

93 focused cases passed across bulk decoding, governed materialization,
parsed revision and immutable metadata reuse. New checks compare individual
versus bulk contract outputs, reject unknown fields across all four families,
reject nested visibility/evidence/required-field violations, preserve separate
decoded assertion metadata objects and prove per-record model_validate
dispatch is removed. Whole-repository Ruff and diff checks pass.

Native-only candidate route timing, CI and independent review remain pending.
No latency or cutover acceptance is claimed by this slice.

## Workspace retention

Reuse the existing task-owned Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for review, candidate verification and stack delivery. Existing
environment and scratch are reused. Cleanup follows delivery after active
process, dirty-worktree and unique-commit checks. Candidate evidence is retained
with its task-owned scratch until diagnosis finishes.
