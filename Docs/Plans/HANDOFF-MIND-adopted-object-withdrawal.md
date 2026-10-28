# MIND: governed withdrawal of dependency-free adopted objects

Status: ACTIVE. Human explicitly grants full repair ownership and authority. PRIME confirms no competing Core/Buddy identity/mutation lease; primary databases remain read-only. This slice extends the established adopted-assertion withdrawal contract for object existence; no new parallel repair authority.

Lane: codex/historical-object-withdrawal in /home/drakosfire/Projects/.codex/historical-graph-repair/worktrees/DungeonMind. Stacked Core topology: parent PR144 exacta33914d2d7e713585203ab5a691a6a0498b57c60;144must settle before this successor merges. Cross-repository relation to Buddy1853 is parallel-independent: different write/runtime ownership and no behavioral dependency. Core143retrieval allocation untouched. No merge/deploy authority inferred.

Expected paths: this handoff; src/dungeonmind/contracts/adopted_assertion_withdrawal.py; application/adopted_assertion_withdrawal.py; infrastructure/postgres/existing_world_adoption.py; infrastructure/memory/repositories.py; migrations/versions/0018_adopted_object_withdrawal.py; owning unit/integration withdrawal tests. Parent144changes are inherited unchanged. No other schemas, identity registries or primary data writes.

Contract: versioned object-target command/receipt retains exact World/adoption/current-parent/source/assertion/digest/actor binding. Existing V1/V2relationship contracts remain disjoint and compatible. Object target is subject_object_id, relationship/predicate/object endpoint fields explicitly null. Nullable locator is explicit. New schema versions use the existing append-only receipt transaction, replay integrity and capability/GM scope/CAS checks.

Invariant: remove exactly one unchanged adopted canonical object from current child graph only when its complete single-reference source binding matches the reviewed request and no incident relationship exists. Preserve all source/evidence records and immutable historical snapshots. Refuse changed targets, reused assertion IDs, mismatched source/World/adoption/hash, stale parents, dependencies, and uncertain/replayed differing requests. Refusal must leave graph/receipt state unchanged. This first slice refuses dependent objects; edge disposition and reviewed location binding remain successors, not silent extra capability.

Verify: original unit tests remain green; positive object withdrawal, exact replay, changed request conflict, source/target forgery, dependency refusal, stale parent, transactional rollback and receipt reconstruction tested at owner repositories, including real PostgreSQL. Then use a uniquely named full native/APP clone and existing Grit wrong-kind orphan records; preserve original clone. No source/model/harness changes, provider calls or primary mutation. Examine exact cumulative base→head diff and open one Core successor PR.

Storage: verified Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8. Retain task-owned worktree/cache for active implementation and full-clone evidence; cleanup after repair acceptance with process/mount/unique-data checks. Do not prune shared storage or other worktrees.

## Full-World owning-boundary evidence (2026-10-28)

Disposable clone evidence: `/home/drakosfire/Projects/.codex/historical-graph-repair/cache/full-world-object-repair-caf8af81c4`.
Before migration, all 37 native tables (1,216 rows) and 47 APP tables (3,873 rows) matched the retained full-World benchmark snapshot by per-row hashes. The original snapshot and primary databases were not modified. Existing source files were reused read-only.

The sealed adoption bundle SHA-256 `90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f` matched the durable adoption receipt. The existing governed source-classification API successfully preflighted and upgraded the clone's V3 receipt to V4, authenticating the exact observed historical classification changes; no membership gate was bypassed. Initial overbroad intents were rejected with artifact-corruption errors before mutation; the exact sealed-to-observed intent passed. Those diagnostic failures and field-level drift are retained.

Two actual V3 object-withdrawal commands removed `node:grit_and_grime` and `node:session10:item:grit_and_grime`. Each command passed the application capability gate with exact World/revision scope, published an immutable child and durable receipt, and returned the identical receipt on exact replay. Each child equals its complete parent payload minus precisely its one target object. The original historical revision remains identical. Correct location, all relationships, evidence and unrelated objects are preserved. Commands, receipts and full before/after payloads are retained in the evidence directory.

This is repair evidence, not full-system ingestion success. Correct later source-bound location binding and the remaining source-adjudicated repair cohort are outstanding.

Verification so far: 40 unit tests and nine new PostgreSQL integration tests pass; focused Ruff and Pyright pass. Three pre-existing profile-drift integration setup failures reproduce independently against unchanged parent `a33914d2d7e713585203ab5a691a6a0498b57c60`; the logs are retained at `cache/parent-a339-inherited-profile-failures.log` under the task root. The nine PostgreSQL cases include stale-parent rejection, changed-target rejection and direct SQL rejection of each non-null relationship target column. The cumulative implementation diff has been inspected; independent review remains outstanding.
