# Single canonical payload pass during revision reconstruction

Status — accepted and merged as Core #215 at
3025ac182ebdaae3544dd52f965bb3c472bad514 after independent review and
all exact-head CI jobs passed.

## Outcome and scope

Serialize the native PostgreSQL graph payload once while preserving its stored
record fingerprint, graph hash and exact snapshot text. This independent
three-file slice is based on accepted main
aba1652b38b111415d7cf078a9513a75b4d862ea, following Core #211.

The adapter streams the canonical two-key record wrapper into SHA-256, reusing
the canonical graph bytes for the payload hash. Sorted wrapper keys remain
graph_payload followed by revision. Both values use the existing canonical
serializer. Stored record format and all drift checks retain their meaning.

The user requires vNext performance acceptance before cutover preparation.
The approximately 540 ms retained classic cold-neighborhood reference remains
an unmet gate. This slice alone does not establish acceptance.

## Validation and review map

The adapter change is confined to _reconstruct. Writer fingerprint generation
continues to use canonical_sha256 on the two-key wrapper, providing an
independent compatibility reference for persisted rows.

32 focused reconstruction/publication unit cases passed. New cases compare
reconstruction with the existing wrapper for Unicode, nested JSON, numeric
forms, signed zero and JSON-like strings. A work regression instruments both
canonical call paths and requires exactly one traversal of the graph payload.

All 14 PostgreSQL publication integration cases passed in the task-owned
codex_vnext_cold_20261118 database, including persisted read, replay and
corruption checks. Focused lint and diff checks passed. Independent review and
all CI jobs passed. At runtime e8f70e45 with retained Buddy ca5a045,
the native-only 10k route measured 1599 ms cold and 194–206 ms warm.
Verified revision retrieval took 175–183 ms. Complete response and exact
citation checks passed. The original baseline was reused.

## Successors and retention

Bulk decoding #214 remains a draft with no established latency benefit.
The derived-snapshot codec is scratch feasibility work. A future cache design
must preserve full revision verification, exact envelope/content binding,
fresh source authority, immutable artifacts, old-data fallback and publication
atomicity, and must measure governed-write costs as well as read latency.

Reuse the existing task-owned Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
The task retains it and the existing environment for review, measurement and
delivery. The named disposable database is retained for verification.
Existing scratch evidence remains under the task's scratch/v8-core directory.
Cleanup follows diagnosis and delivery after active-process, dirty-data and
unique-commit checks. No new environment, worktree or database was allocated.
