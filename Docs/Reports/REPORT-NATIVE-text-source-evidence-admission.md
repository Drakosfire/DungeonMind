# Native text-source and evidence admission — implementation evidence

**Disposition:** implementation complete; PRIME exact-head review pending
**PR:** pending
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

This does not establish mutable source lifecycle, source freshness across Keeper
prepare/commit, Buddy saved-document authenticity, DEMO adoption, J3, or V7.
No Keeper, Buddy, dependency manifest, frozen source/evidence contract or
historical migration was changed. Migration `0011_native_source_v1` adds the new
native authority tables after `0010_vnext_prospective_results`.

## Owning-boundary evidence

- Core: `2046 passed, 11 skipped, 253 deselected` via
  `PYTHONPATH=src UV_CACHE_DIR=/tmp/dm-uv-cache pytest -m 'not integration'`.
- PostgreSQL integration: `252 passed, 12 skipped, 2046 deselected` via
  `PYTHONPATH=src DUNGEONMIND_DATABASE_URL=... pytest -m integration` against
  disposable `pgvector/pgvector:0.8.6-pg16`; no required source-admission or
  migration proof skipped.
- Focused source admission/migration rerun: `9 passed` on PostgreSQL, including
  injected rollback stages, same-ID concurrent replay, distinct-ID parent race,
  and replay after a descendant.
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

These are implementation proofs, not PRIME acceptance. The implementation PR
must receive an independent exact-head PRIME review. Until that review and
authorized merge are recorded, the handoff remains active and the roadmap must
not claim the capability accepted. The design's separate Keeper freshness gap
and later product/roadmap gates remain open.
