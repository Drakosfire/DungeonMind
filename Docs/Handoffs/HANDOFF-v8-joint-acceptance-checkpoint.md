# V8 — optimized acceptance checkpoint

Status: **V8 ACCEPTED — PR #229 merged; V9.B actual serving activation accepted.**
Owner: Elderwyld pre-cutover optimization lane. Execution authority: operator's
optimization-before-cutover goal, including implementation/review/merge authority.

## Current anchor and phase

- Core runtime: `4b6516e2c0dfd81acaa4410b9b9bb9da18894c90` — accepted #228.
- Buddy runtime: `0a746752da32324256d83b018e884aa7cb8ad692` — accepted #4029,
  pinning that Core. Buddy main separately observed at `532ef4e4742afaebb3ac5e994402b699457bee77`.
- Phase: V8 accepted at Core229 merge f770098ad27b772e6351f2827a2b7bd6628705e8.
  V9.B actual native serving accepted at Buddy4079 merge
  e36abef5d75d543b7e8c656d611b93723757b362; reviewed5b422140079b357e064176732b20918a85ba14d5,
  Cycle1 review5971846921, exact frontend1411 selected passes/build/canonical/cleanup.
  Current serving mirrors Buddy4f4ed526/Core4b6516e are fixed independently of main.
- Scope: [V7 fresh-native Elderwyld](HANDOFF-v7-elderwyld-fresh-native-scope.md),
  accepted Core #174,47-session published source cohort. Legacy bridge out of scope.
- Owning bounded lease: [V8 acceptance handoff](../Plans/HANDOFF-MIND-v8-optimized-acceptance.md).

Read the [canonical acceptance artifact](dm_vnext_contract_acceptance_v1.json),
[decision review](V8-joint-evidence-review.md), then the
[portable evidence report](../Reports/V8-optimized-evidence-v1.json).
The artifact binds contract/domain/profile/scope/fixture/result digests and each
required operation to its actual evidence. Prior outputs remain at their original
pins through linked Git history; old prose is not current runtime truth.

## What has been proved

- Comparable first native neighborhood484.92–492.57ms versus retained approximately
  540ms classic; warm77.80–84.04ms. No frozen classic baseline rerun.
- Parsed eviction509.63–512.21ms, new revision505.31–514.38ms. Historical return
  includes554.24ms above-reference sample, explicitly retained for disposition/V11.
- Exact current-candidate Buddy GM/player, organizational-memory and adversarial
  fixture outputs.269 Core semantic,117 Core bounded-work and94 Buddy owning checks
  passed, zero skips. Report names authority/work cases and source hashes.
- Exact citations and fresh scope/withdrawal checks survive immutable parse/proof
  reuse. Current parsed/citation cache ownership is bounded; no admitted-result cache.
- Matched10000-entity tiny-delta native prepare+confirm908.15ms versus retained
  classic4626.42ms; exact44-byte citation/replay/direction/player-withholding proof.
- Both full-input practical ladders passed100/1k/10k;50k failed primary JSONB
  insertion before artifact generation;100k unattempted. Metadata duplication and
  cold9.4–9.6s are explicit limits, not hidden or generalized capacity claims.
- Isolated Elderwyld's18 completed mounted route cases and six citations are
  preserved with the original final harness failure plus independent bound head
  check. No deployed process qualification is inferred from that composite.

## What remains false

V8 acceptance is effective following final review/checks and merged PR229.
The554.24ms historical sample is not below the point reference.
Universal classic/native DTO, secondary search order and capped citation selection
parity are not proved or promised. Rules-like equivalent-work performance parity
is not established.50k full-input publication and100k full-input reads did not pass.
A repository pin alone is not proof of loaded serving code. V9.B now has actual
loaded-code/read/browser/process-rollback proof at Buddy4079. No new live publication
or deployed latency benchmark is inferred. V10 retirement and V11 remain incomplete.

## Next primary question and blockers

V8 independent review accepted the evidence map and scoped dispositions at proposal
4357a91f78edb45abe7f5b6b247279e2cfba763d (review5968294321), followed by final acceptance
and merged229. Buddy V9.A4041 qualified the integrated consumer; V9.B4079 activated
actual5202 with84 matching read cases, exact citations, retained current authority,
loaded-source attestations and same-version process rollback/restart. Its report
and runbook own operational details and bounded recovery limitations.

Next primary question: which classic current/public surfaces can be removed while
exact historical reconstruction remains under an explicit compatibility boundary?
The dedicated HANDOFF-MIND-v10-historical-codec-quarantine.md begins that serial work.
It is not overall V10 completion. V11 deployed baseline and successor performance
handoff remain required; do not rerun the frozen classic reference.

## Safe parallel work and resources

Other existing product/hosted/combat lanes may continue within their own scopes.
Do not seize their service ports or treat their serving processes as this lane's.
Core #158 retains its roadmap/standing-role index files; this dedicated checkpoint
provides current V8 continuity without overlapping its write set.

Owner: optimization lane. Existing Projects task root
`/home/drakosfire/Projects/.codex/v7-elderwyld-scope` retains source refs, fixtures,
logs, cache and V8 PostgreSQL container/clone for acceptance/V9 integration. All
new fuller-ladder/proof workers are terminal; their three unique databases were
dropped only after zero connections. Logical DB sizes are not reclaimed filesystem
bytes. No manual worktree/cache/file removal occurred. Cleanup follow-up: scoped
reproducible artifacts only after explicit cleanup authorization and active task,
process/mount/connection, dirty-worktree and unique-data/commit checks. No blanket
cleanup, new worktree/environment/container or serving mutation in this slice.
