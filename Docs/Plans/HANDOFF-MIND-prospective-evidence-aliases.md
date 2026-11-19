# MIND — atomic prospective evidence-bearing aliases

Status: COMPLETE — MIND_PROSPECTIVE_EVIDENCE_ALIASES_ACCEPTED. Owner/designer: Elderwyld vNext completion lane. Explicit operator
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
- Docs/Decisions/ADR-0029-prospective-evidence-bearing-aliases.md (new generic decision).

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
prove visibility, standing and source withdrawal revalidation on cached data.
Scope retains current semantics: assertion/list membership is scoped; IdentityAlias
has no scope field and exact identity aliases are source-authorized space-wide.
Prove unmatched-scope listings omit entities/aliases without inventing a new alias
scope policy. Product scope requirements beyond this contract require a new design.
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

## Implementation checkpoint

Explicit wrapper/planner and shared publication seam implemented. Owning alias
module27 tests passed; affected V5.1/V5.4 cohorts passed81 before the final four
additional replay/scope proofs. Focused PostgreSQL17 passed including new alias and
inherited prospective cases. Full Ruff and source Pyright pass (explicit external
interpreter/pinned Node; no repository .venv allocation). Frozen V0 bundle check
passes. Full core/integration and independent exact-head review remain pending.

Independent design/implementation critique found no demonstrated code blocker;
requested stronger accepted-target/evidence replay tests and clarified scope.
Those tests now vary valid entity targets and parent evidence IDs/order. Exact
identity aliases are space-wide subject to source/standing gates; unmatched scope
filters assertions and entity listings, which also omits their listed aliases.
No new alias scope policy is introduced.

Owned isolated PostgreSQL proof database:codex_v10_alias_test_6475b2069389 on32903.
Only this newly allocated test database receives destructive integration fixtures.
Scratch evidence owner Elderwyld prospective-alias lane:
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/scratch/v8-core/v10-prospective-aliases.
Retain database/logs/XML and reused task-owned caches through acceptance; inspect
connections/processes/mounts/unique data and specifically approved cleanup scope
before disposal. No manual paths removed or reclaimed bytes claimed.


## Acceptance seal

Disposition:MIND_PROSPECTIVE_EVIDENCE_ALIASES_ACCEPTED. Implementation head
c9a64a81431121e189123e098856d216a4f7f807; independent cumulative code review recorded
as5973452695 on PR231 through the operator account (not a separate GitHub-user
approval). Local exact-head full core2997 passed11 skipped; full PostgreSQL519
passed1 skipped (only new owned test database), owning alias27 and focused SQL17
passed. Full Ruff/Pyright and frozen V0 bundle check passed. Existing Buddy
first-World typed evidence module39 passed with explicit candidate Core source;
this is compatibility evidence, not installed-pin or serving rollout acceptance.

GitHub implementation-head CI44506845522 passed core/integration/benchmark-smoke,
including the actual accepted WorldKeeper source/evidence consumer witness.
Final documentation-head CI and independent delta review are required before merge.
Local XML/log/type evidence lives in the task-owned scratch path above; no frozen
classic baseline, provider request, live data or serving process changed.

The finalization rebrief replaces only the new ADR path0027 with0029 because0027
(open predicate namespaces) and0028 (source admission) already exist. Open active
patches do not claim0029. Same nine-path/capability boundary; runtime/test/schema
blobs are unchanged from the reviewed implementation. No broader source work is
absorbed by this correction.

Next primary question: how does Buddy compose the accepted reviewed first-World
intent, source/span evidence and exact parent into this native publication without
losing any accepted field or creating a second authority? Consumer pin/composition,
versioned product prepare/confirm/recovery and activation remain unimplemented by
this Core slice. Trace actual WK needs before introducing another contract. The
larger optimized native deployment, current classic retirement and V11 performance/
semantic evidence objective remains active.
