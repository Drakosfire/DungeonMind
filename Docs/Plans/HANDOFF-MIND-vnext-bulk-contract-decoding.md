# Bulk contract decoding for native revisions

Status — implemented, candidate timing and independent review pending.

## Outcome and topology

Remove per-record Python model_validate dispatch while retaining the exact
public contract schemas for entities, assertions, aliases and evidence.

This slice is stacked directly on reviewed Core #211 at
49ccc786be6a6709192b55bb4a428b73bd11f601, branch
codex/vnext-cold-revision-reconstruction. Validation prerequisite #213
merged as 5a3158d5e90a50701948e29cf3be01e088e0edbf. Merge #211 before
this slice, then rebase this child onto its accepted parent merge.

Metadata-reuse PR #212 was withdrawn after review found equality can conflate
True, 1, 1.0, signed zero and offset timestamps. Its cache and normalization
changes are excluded from this branch. Added regressions verify numeric type
and signed-zero preservation through decoding and parsing.

The user requires performance acceptance before cutover preparation.
The 540 ms retained classic cold-read reference remains an unmet V8 gate.

## Implementation and validation

Four module-local Pydantic TypeAdapters validate lists of the existing public
contract classes. The decoder normalizes each input iterable to a list,
preserving iteration behavior, and returns the existing tuple containers,
schema identity and payload digest. Existing typed failure classification is
retained. Public contract definitions are unchanged.

91 focused cases passed across bulk decoding, governed materialization,
parsed revision. New checks compare individual
versus bulk contract outputs, reject unknown fields across all four families,
reject nested visibility/evidence/required-field violations, preserve separate
decoded assertion metadata objects and prove per-record model_validate
dispatch is removed. Whole-repository Ruff and diff checks pass.

Candidate timing at this revised stack, CI and independent review remain pending.
The prior 7fa4694 timing included withdrawn #212 and cannot establish this
revised candidate's latency.
No latency or cutover acceptance is claimed by this slice.

## Workspace retention

Reuse the existing task-owned Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for review, candidate verification and stack delivery. Existing
environment and scratch are reused. Cleanup follows delivery after active
process, dirty-worktree and unique-commit checks. Candidate evidence is retained
with its task-owned scratch until diagnosis finishes.
