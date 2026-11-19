# MIND: transfer the validated prospective command once

Status: COMPLETE — accepted Core #228. Owner: Elderwyld pre-cutover optimization lane.
Authority: operator optimization-before-cutover goal with implementation/review/
merge authorization. Serial successor to accepted Core #218 and Buddy #4024.
Base: e8b05965bb43df370a1292149c8c809aec0e7fb9, fetched Core main.
Branch: codex/vnext-validated-command-transfer.

## Outcome and exclusive scope

The private prospective planner already restores and validates a sealed command.
Return that locally owned command to both callers instead of immediately restoring
it again. Ordinary publication should need two command restorations, not three;
governed source extension should need one per plan, not two. Keep binding validation
inside the planner and keep the fresh sealed restoration AFTER the repository call.
Public materialization command/payload properties remain copy-on-read.

Six paths: src/dungeonmind/application/vnext/prospective.py;
src/dungeonmind/application/vnext/native_source_extension.py;
tests/unit/test_vnext_prospective_publication.py;
tests/unit/test_vnext_native_source_evidence_extension.py; this handoff;
Docs/Plans/HANDOFF-MIND-native-read-artifact-store.md (accepted #218 settlement).
No new cache, durable/public contract, repository/schema/transaction, identity,
source admission, authorization, WorldKeeper/Buddy, GC, deployment or cutover change.
Open Core158/150/149/148/147/146/145/143 file lists have no write-set overlap.

This is one coupled change: private planner return shape and both callers must
change together. Both caller tests accompany it. Eight old adopted/source-policy
PRs remain independent. No stacked/unmerged parent or new worktree is required.

## Invariants and proof obligations

- Preserve binding validation before revision identity calculation, receipt replay
  verification or any persistence attempt. Local failure must not enter recovery.
- The repository may mutate its command argument. Post-publication verification
  must restore the original sealed materialization independently and reject an
  otherwise self-consistent receipt for the mutated request.
- Public copy-on-read isolation, deterministic allocation, parent CAS, exact replay,
  response-loss recovery, source extension proof/rollback and typed failures remain.
- Assert restoration work counts for ordinary publication/replay and extension/replay;
  reject forged planner bindings before mutation on both paths; prove repository
  mutation cannot redefine successful receipt verification.
- Run owning prospective/materialization/extension unit cohorts; inspect the cumulative
  diff, request independent review and require exact-head CI. Use a native-only
  candidate probe for work counts and diagnostic attribution; never rerun the frozen
  classic baseline or call profiled durations an unprofiled speedup.

## Evidence and limits

Retained diagnostic native-write-stage-profile-f392a33-5dff4ec.json measured three
sealed command restorations at roughly440ms each in BOTH commit and replay.
Profiled prepare1.95s/commit12.42s/replay10.60s are not acceptance latencies.
Materialization3.32–3.46s and repository/postcheck spans overlap. Existing review
limits bind the original result: receipt wrapper missed its imported call binding;
head checks did not count events; recorded HEADs are not loaded-source attestation.
Do not use those omissions as proof that checks were absent. No integrity check
may be removed to make a timer smaller.

V8 remains open: current-route/citation/visibility/withdrawal and memory/scale/write
acceptance plus the canonical joint artifact still gate V9. No serving switch.

## Current implementation evidence

Accepted exact head `8c5b29188e27c7ef1f55c3ada9dccdc131f7c7db` merged as
`4b6516e2c0dfd81acaa4410b9b9bb9da18894c90`. Independent cumulative review
approved; exact-head CI run44432180173 passed. Owning prospective/materialization/
extension regressions include restoration counts, forged bindings and repository
mutation. Buddy #4029 adopted that Core pin. The later native-only matched HTTP
receipt is recorded in the V8 optimized evidence report with single-sample and
setup/display limits; unit counts alone are not an end-to-end speedup claim.

## Resources and settlement

Reuse task-owned Core/Buddy checkouts and existing owning Python environment.
All new scratch/cache/evidence stays under existing Projects task root
/home/drakosfire/Projects/.codex/v7-elderwyld-scope, filesystem UUID
48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8. Use existing task PostgreSQL on32903
only for uniquely isolated fixtures. Honor the unchanged shared verification lock.
Retain unique refs, tests/probes/logs and receipts for optimization-lane review and
integration. Cleanup follows explicit scope, active process/connection/mount and
dirty/unique-data/commit checks; no standing deletion permission or manual removal.
Settle accepted #218 in this slice; settle this slice after its own actual merge
through the next dependent consumer, never by inventing a future merge identity.
