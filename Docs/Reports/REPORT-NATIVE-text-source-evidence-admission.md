# Native text-source and evidence admission — implementation evidence

**Disposition:** `NATIVE_TEXT_SOURCE_EVIDENCE_ADMISSION_ACCEPTED`
**PR:** [#85](https://github.com/Drakosfire/DungeonMind/pull/85) — merged
**Accepted head:** `0803faf9f84b44148291c68c8dd115f73c68d464`
**PRIME review:** Cycle 2 PASS `5334796956`
**Merge:** `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`
**Design checkpoint:** `86e8f22d007df99de577cb412301c5a6d4e2d597`
**Implementation branch:** `codex/native-source-evidence-admission`
**Implementation base:** `3ebdefaf1303089f21d3c94f2759df2d9274a71f` (PR #84 settlement)

## Result

The candidate implements the approved additive V1 native text-source capability.
One bounded admission stores exact UTF-8 bytes, source/revision/span proof,
evidence membership, child revision, normal publication receipt, companion
receipt, head/event and source-authority epoch atomically. Replay recovers the
same durable allocation after a descendant. Context-bound preview verifies
exact revision membership, visibility, status and body/span digests; unavailable
cases are non-disclosing and stored corruption fails closed.

The PostgreSQL proof also injects a lost response after the transaction has
committed. The public admission operation recovers the original companion
receipt; a fresh repository instance then verifies exact replay without another
child, head event, admission row or source-epoch increment.

This does not establish mutable source lifecycle, source freshness across Keeper
prepare/commit, Buddy saved-document authenticity, DEMO adoption, J3, or V7.
No Keeper, Buddy, dependency manifest, frozen source/evidence contract or
historical migration was changed. Migration `0011_native_source_v1` adds the new
native authority tables after `0010_vnext_prospective_results`.

## Owning-boundary evidence

- Exact-head CI core: `2046 passed, 3 skipped` in run `36386951061`.
- Exact-head CI PostgreSQL integration: `308 passed, 1 skipped, 2116 deselected`
  in run `36386951061`; this includes the pinned WorldKeeper consumer witness.
- Local core rerun: `2046 passed, 11 skipped, 253 deselected` under Python 3.13;
  sandbox-blocked uv-cache/socket tests passed when rerun with those restrictions
  removed. CI's Python 3.12 result above is the acceptance count.
- Focused source-admission/migration rerun after the repair: `10 passed` against
  disposable `pgvector/pgvector:0.8.6-pg16`, including injected rollback stages,
  lost post-commit response recovery, fresh-repository exact replay, same-ID
  concurrent replay, distinct-ID parent race, and replay after a descendant.
- `ruff check .`: pass.
- `pyright src` with the repository virtual environment: `0 errors, 0 warnings`.
- Exact WorldKeeper witness: `NATIVE_SOURCE_KEEPER_CONSUMER_WITNESS_PASS` at
  `49a8620f066ce7ef8972a699020c012f50af9158`. The run used an empty native
  genesis, admitted exact source/evidence, actual Keeper prepare/commit, exact
  replay, stale-parent rejection, a fresh PostgreSQL repository connection,
  source preview and ordinary evidence read. `seeded_evidence=false` and
  `provider_called=false`; candidate DungeonMind and pinned Keeper import paths
  were printed by the witness.
- PostgreSQL migration upgrade to head passed; the new migration ID is kept
  within Alembic's existing `version_num` width.

The initial sandboxed core run reported two environment-only failures (global
uv cache read-only and socket creation denied). Both exact tests passed when
rerun with a writable temporary uv cache and socket permission, and the full
core rerun then passed.

## Acceptance boundary

PRIME accepted this bounded capability at exact head
`0803faf9f84b44148291c68c8dd115f73c68d464`; PR #85 merged at
`7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`. The design's separate Keeper
freshness gap and later product/roadmap gates remain open.
