# MIND — atomic prospective evidence-bearing aliases

Status: ACTIVE. Owner/designer: Elderwyld vNext completion lane. Explicit operator
implementation, independent review, merge and launch authority; no PRIME dependency.
Parent:9b4e0af51d343feb4ab5aafaab6a1026cfcfe0b8. Serial prerequisite after Buddy4087
merge5574068634341c57235800b77f7278bf0c6c08ad; no Git stack on Buddy.

## Outcome and design

Provide an explicit additive wrapper around the unchanged V5.4 prospective
contribution, with governed alias creates targeting accepted new entity results.
Each alias carries caller-owned alias_id (as existing decision-owned alias IDs),
exact text, explicit standing and nonempty unique evidence IDs. All evidence must
exist in the verified parent. This is structural membership, not mutable source
admission or a new write principal. Existing actual readers revalidate source
scope/visibility/standing/withdrawal. Product preparation retains its source and
review freshness/write-fence obligations.

Dispositions close over base and alias item IDs exactly. Accepted aliases cannot
target absent, rejected or assertion results, guessed durable IDs, or overwrite
parent/base-generated aliases. No implicit casefold/whitespace deduplication.
After ordinary V5.1 base materialization, reconstruct and validate the complete
augmented child and seal a new command. Domain-separate the full request hash over
base contribution, every alias and every disposition, including rejected intent.
Reuse the V5.3/V5.4 atomic receipt/result/revision/head/event transaction and exact
verification/recovery through one shared publication seam. No receipt/result or
frozen V0/V5.4 wire-format modification; no new alias result mapping is needed.

## Exclusive write set (nine paths)

- this handoff;
- src/dungeonmind/contracts/vnext/prospective_aliases.py (new);
- src/dungeonmind/contracts/vnext/__init__.py (additive exports, frozen inventory unchanged);
- src/dungeonmind/application/vnext/prospective_aliases.py (new);
- src/dungeonmind/application/vnext/prospective.py (shared sealed publication seam only);
- Docs/Contracts/vnext/dm_prospective_alias_contribution_v1.json (new deterministic bundle);
- tests/unit/test_vnext_prospective_aliases.py (new owning contract/materialization/read tests);
- tests/integration/test_postgres_vnext_prospective_aliases.py (new transaction proofs);
- Docs/Decisions/ADR-0027-prospective-evidence-bearing-aliases.md (new generic decision).

Open Core158/150/149/148/147/146/145/143 patches were inspected: no vNext runtime
path overlap. Core158 owns global Steward/roadmap; do not edit those files. No
repositories/migration/product/profile/WK/dependency/serving changes in this slice.
Any new durable contract, extra path or boundary expansion requires rebrief.

## Validation and acceptance

Unit/contract: frozen V0 bundle unchanged, old wrapper refuses new fields; new
schema bundle deterministic; exact disposition closure and alias collision rules;
wrong/unknown/rejected result targets; missing evidence; sealed final payload;
changed alias text/evidence/standing/target/rejected intent conflicts; exact replay,
descendant replay, response-loss recovery and deterministic failures preserved.
Read actual published aliases through EntityReadService/KnowledgeReadContext;
prove visibility, scope, standing and source withdrawal revalidation on cached data.
PostgreSQL: fresh/replay, concurrent same-ID replay/conflict, full transaction
rollback, changed-parent zero mutation, response loss and direct committed content.
Run affected V5.1/V5.4 cohorts, full required core and integration checks, Ruff and
Pyright with task-owned existing tooling. Never rerun frozen classic retrieval
baseline. Independent cumulative exact-head review before merge.

## What remains false

No Buddy native first-World writer exists from this prerequisite alone. No WK
operation or repin, managed-default retirement, serving rollout, latency claim,
complete V10 or V11 acceptance follows. Next: adopt this generic capability through
owning consumer contracts, then integrated native first-World prepare/confirm/
recovery, remaining current classic retirement, qualified deployment and V11 proof.

## Storage

Reuse existing task-owned Core checkout under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and host writability verified before allocation.
Scratch/cache/owned disposable DB proof belongs under the same task root. Retain
unique evidence; record created/retained/removed paths, owner, bytes/filesystem and
cleanup follow-up. No manual deletion authority is implied. Serving mirrors/live
DBs and other lanes remain untouched.
