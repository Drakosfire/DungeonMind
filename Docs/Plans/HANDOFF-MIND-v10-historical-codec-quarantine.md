# MIND — V10.A historical codec quarantine

Status: ACTIVE. Owner/designer: Elderwyld vNext completion lane. Explicit operator
implementation/review/merge authority covers finishing V9–V11. Serial delivery;
parent Core main f770098ad27b772e6351f2827a2b7bd6628705e8 (accepted V8 PR229).
Existing task-owned Core checkout, branch codex/v10-historical-codec-quarantine.
Buddy V9.B4079 merged e36abef5d75d543b7e8c656d611b93723757b362, exact reviewed
5b422140079b357e064176732b20918a85ba14d5, Cycle1 review5971846921, exact frontend
1411 selected passes/build/canonical/cleanup. Actual5202 activation proved;
new live write and V11 deployed timing remain unproved. No frozen baseline rerun.

## Outcome and invariant

Historical v1–v6 graph decoding belongs to explicit
`dungeonmind.application.compatibility`, not the current `application.vnext` façade.
Move the actual codec and packaged manifest; migrate real callers and remove the
obsolete import path, without a forwarding shim. Preserve exact manifest bytes,
sealed translator function bodies/digests, callable signatures, shared integrity-error
class identity, six-generation semantic/index parity, corruption rejection and
canonical parity artifact. No native historical fallback dispatcher exists today;
do not invent one. Existing root application/classic exports remain for later V10.

Independent preimplementation critique accepted this boundary and requires both
import orders, native façade isolation, actual new public compatibility calls, and
built-wheel resource access outside checkout/CWD. Root application still eagerly
imports classic modules; this slice does not claim total current-path retirement.

## Exclusive bounded write lease and dependencies

- this handoff;
- dedicated Docs/Handoffs/HANDOFF-v8-joint-acceptance-checkpoint.md for truthful
  accepted V8/V9 continuity only;
- src/dungeonmind/application/vnext/__init__.py;
- move src/dungeonmind/application/vnext/legacy_compat.py to
  src/dungeonmind/application/compatibility/legacy_graph.py;
- new src/dungeonmind/application/compatibility/__init__.py;
- move vnext/data/__init__.py and dm_legacy_world_compat_v1.json to compatibility/data;
- pyproject.toml packaged-resource locator only;
- scripts/generate_legacy_compatibility_parity_artifact.py imports only;
- tests/unit/test_vnext_legacy_compatibility.py actual compatibility import migration;
- new tests/unit/test_historical_compatibility_boundary.py.

No runtime selector/dependency rollout, serving/profile/database/migration/source
publication/provenance changes. Existing Buddy/Core immutable serving mirrors stay
pinned. PR158 owns global Steward/roadmap paths; do not edit them. Checked open Core
143/145–150/158 path leases: no overlap with this bounded write set. Existing consumer
classic imports are later serial work, not silently removed by this package move.

## Verification and review map

Inspect the move/import/resource delta first; independently compare all moved
function definitions and manifest bytes against the parent. Run all six historical
codec cases and unchanged parity generator; import-order/absence/signature/error
identity regressions; owning native materialization/read suites; no-heavy-extras
boundary suite; build a wheel and open its manifest outside source checkout.
Run focused lint/types and applicable exact-head Core CI. No destructive state or
classic baseline run is needed. Record exact commands/source/results externally
under the verified existing Projects taskroot; independent cumulative review and
expected-head guarded merge precede acceptance.

## Remaining full-goal obligations

V10.A establishes the historical boundary only. Next serial slices must adopt
explicit consumer imports, retire classic current projection/retrieval/GM-player/
campaign policy, then classic current publication/rollback/contribution/relationship
wiring, retaining justified historical readers and database/migration history.
V11 must measure the accepted deployed system and hand off the next measured
performance question before VNEXT_ROADMAP_COMPLETE can be claimed.

## Resources and retention

Reuse existing task-owned Core checkout and unsynced verification tools; standalone
scratch/build/cache goes beneath /home/drakosfire/Projects/.codex/v7-elderwyld-scope.
Require UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and writable parent before allocation.
Owner Elderwyld completion retains source refs/evidence and active serving resources;
no manual deletion authority or reclaimed-byte claim. Cleanup followup after scoped
acceptance/replacement: inspect process/mount/connection/dirty/unique-commit/data
state before separately approved disposal of reproducible task-owned outputs.
