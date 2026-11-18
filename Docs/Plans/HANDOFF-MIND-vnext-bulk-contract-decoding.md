# Bulk contract decoding for native revisions

Status — implemented and independently reviewed before rebase; candidate
latency improvement unproved and exact-head CI pending.

## Outcome and topology

Remove per-record Python model_validate dispatch while retaining the exact
public contract schemas for entities, assertions, aliases and evidence.

Core #211 merged as aba1652b38b111415d7cf078a9513a75b4d862ea.
This child is rebased onto that accepted main. Validation prerequisite #213
merged as 5a3158d5e90a50701948e29cf3be01e088e0edbf. This draft remains
pending performance disposition and exact-head validation.

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

Independent read-only review of exact 128fb286 against 49ccc786 found no
actionable findings, verified 90 tests and compared 61 parent/head cases
covering iterable handling, nested validation and failure classification.
The decoder, builder, model and test blobs remain unchanged by rebase.

At Core 128fb286 and retained Buddy ca5a045, the corrected native-only 10k
candidate measured 2046.13 ms cold and 314.35, 334.54, 320.42, 309.60 ms repeats.
The response retained Object 0, Endpoint, Object 1 ordering, two relationships,
identical repeat bodies and exact citation SHA-256
a64c21442cb988b1e92e410b34c30668317174ebdfe9e6792ccbea25593dafbc.
This diagnostic does not establish improvement and exceeds the cold gate.
The prior 7fa4694 run included withdrawn #212 and is excluded from this
revised candidate's performance evidence.

Exact-head CI remains pending. Keep this PR draft until its performance
disposition is justified. Investigate removal of whole-revision preparation
for bounded reads rather than inferring speed from fewer validation calls.
No latency or cutover acceptance is claimed by this slice.

## Workspace retention

Reuse the existing task-owned Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for review, candidate verification and stack delivery. Existing
environment and scratch are reused. Cleanup follows delivery after active
process, dirty-worktree and unique-commit checks. Candidate evidence is retained
with its task-owned scratch until diagnosis finishes.

The task retains test_v8_native_cold_candidate_128fb28.py,
native-cold-candidate-128fb28.json/log and candidate-128fb28-pytest under
scratch/v8-core for diagnosis. Existing fixtures dropped their Core and APP
databases after the run. Cleanup of retained probe outputs follows diagnosis.
The retained baseline was not rerun.
