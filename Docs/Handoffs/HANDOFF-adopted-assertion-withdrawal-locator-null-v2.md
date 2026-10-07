# HANDOFF — adopted assertion withdrawal with locator-null evidence v2

**Created:** 2026-10-07  
**Status:** BLOCKED — pinned for PRIME activation; no implementation lease  
**Repository / branch:** Drakosfire/DungeonMind / `codex/adopted-withdrawal-null-locator-v2-handoff`  
**Base:** `main` at `5d4e98963991995bdc280e57df52b8d0fe8de79e`  
**Topology:** serial; one implementation PR only after PRIME activation and re-anchor  
**Predecessor:** V1 merged as PR #98 at `dcfba328d14e9cb4d8fbb2051f5f2621ed15ae11`; accepted implementation head `21e5302a1bace472439d67ffe0790e713a885e0d`. The V1 handoff still says “not merged”; its completion state must be synchronized in the V2 implementation PR.  
**One-line mission:** Add a strict V2 of the existing governed withdrawal for the single case where its immutable evidence has no source locator, without weakening V1 or creating a locator resolver.

This document pins design and a prospective write set only. It does not authorize implementation, migration execution, or any live-world operation. PRIME must activate it after a fresh re-anchor and bounded lease check.

---

## §1 Outcome

Add versioned V2 command/receipt support for withdrawing exactly one adopted relationship assertion when the evidence record’s `source_locator` is `null`. V2 must bind that absence explicitly and accept it only when the adoption-pinned evidence and exact current parent contain the same locator-null evidence row, with matching evidence, span, source artifact, source revision, assertion, tuple, and durable V4 adoption membership. It publishes the same kind of append-only union-graph child and receipt as V1; it does not create a negative assertion or alter evidence. V1’s required non-null locator behavior remains unchanged.

The future live target is not implementation authority. Any live operation, receipt change, or migration remains separately unauthorized.

## §2 Authority and anchors

Read and follow, in order:

1. Current `AGENTS.md`, especially its re-anchor, write-lease, one-slice, serial-topology, and live-authority rules.
2. `Docs/Architecture/AUTHORITY.md` §§1–4, 8: checked-in authority wins; source/evidence validity is current; V3 M0 and V4 M1 membership are distinct; only governed durable operations create graph truth.
3. `Docs/Architecture/ARCHITECTURE.md` §§2–3 and 5: DungeonMind owns governed library operations and evidence integrity; source bodies are not graph authority.
4. `Docs/Handoffs/HANDOFF-adopted-assertion-withdrawal-union-v1.md`, the V1 contracts/application/repository, and `migrations/versions/0013_adopted_assertion_withdrawal.py`. Preserve their accepted V1 semantics. V1 requires a non-null locator and migration 0013 established its append-only receipt table.
5. At activation, re-fetch `main`, open PRs, and the exact V1 merge/review state. This handoff’s anchors do not supersede then-current repository authority.

No chat, preview, or locally inferred graph is authority for a live write.

## §3 Scope

**In scope**

- Add `AdoptedAssertionWithdrawalCommandV2` and `AdoptedAssertionWithdrawalReceiptV2`; preserve V1 contracts and behavior.
- Permit only an explicit `source_locator: null` in V2. It is not a wildcard and must be present in the command.
- Reuse the existing governed withdrawal boundary: exact adoption receipt with V4 membership manifest, exact parent pin/digest and CAS, unique relationship/assertion/tuple, one exact evidence reference, capability, append-only receipt, exact replay, and atomic child/head/event/receipt behavior.
- Add Alembic revision `0014_adopted_withdrawal_v2`, with `down_revision = "0013_adopted_withdrawal_v1"`. Keep migration 0013 immutable. Preserve V1 rows and enforce the version/locator invariant in the database: V1 rows have a non-null locator; V2 rows have a null locator. Downgrade must refuse while V2 receipts exist and must retain 0013’s append-only guarantees.
- In the same implementation PR, synchronize the merged V1 handoff’s status and exact PR #98 merge anchor. This is backward-looking predecessor maintenance, not a standalone documentation PR.

**Out of scope / falsification**

- No generic receipt promotion, V5, or classification-repair implementation. The existing V3→V4 classification-repair path stays separate and unchanged; MIND owns its assigned dry-run applicability check. V2 must not manufacture or promote a V4 receipt.
- No source-span-to-locator resolver, source-body I/O, or substitution from `SourceRevision.locator`.
- No weakening of V1; no arbitrary null acceptance; no multi-evidence selection; no change to ordinary correction behavior.
- No Buddy, DungeonMindServer, WorldKeeper, API/product integration, re-adoption, graph rewrite, or live-world action.

**Prospective implementation write lease — inactive until PRIME activation**

- `Docs/Handoffs/HANDOFF-adopted-assertion-withdrawal-locator-null-v2.md`
- `Docs/Handoffs/HANDOFF-adopted-assertion-withdrawal-union-v1.md` (V1 predecessor state sync)
- `src/dungeonmind/contracts/adopted_assertion_withdrawal.py`
- `src/dungeonmind/application/adopted_assertion_withdrawal.py`
- `src/dungeonmind/application/repositories.py`
- `src/dungeonmind/infrastructure/memory/repositories.py`
- `src/dungeonmind/infrastructure/postgres/existing_world_adoption.py`
- `migrations/versions/0014_adopted_withdrawal_v2.py`
- `tests/integration/conftest.py`
- `tests/integration/test_migrations.py`
- `tests/integration/test_postgres_adopted_assertion_withdrawal.py`
- `tests/unit/test_adopted_assertion_withdrawal.py`

No other path is leased. If a proof requires another path, stop and return to PRIME before editing. The V2 implementation PR carries the V1 completion sync; do not create a documentation-only PR for it.

## §4 Invariants that bind this slice

- **V1 remains strict:** its locator remains required and non-null; existing V1 receipts still reconstruct and verify.
- **V2 absence is explicit:** the V2 command carries `source_locator: null`; both the immutable adopted payload and the exact current parent must contain that same locator-null evidence record. Any non-null value, omission, source/evidence drift, or ambiguous binding fails closed.
- **No inferred provenance:** bind the exact `source_span_ref_id`, artifact ID, and immutable revision ID from the evidence row and verify the persisted artifact/revision and adoption membership. Do not invent a locator, resolve one from a span ID, or use the source-revision body-storage locator as a span locator.
- **Same governed authority:** require the exact durable V4 receipt and membership manifest, GM COMMIT capability, target tuple and profile checks, expected-parent pin/digest, repository-side revalidation under the existing atomic boundary, and append-only/idempotent receipt behavior.
- **One neutral disposition:** remove only the exact target relationship from a derived child; do not assert false, contradicted, negated, or replaced. All other graph fields, evidence, source records, and the immutable parent remain unchanged.
- **No partial mutation:** every mismatch, stale parent, replay conflict, or persistence failure leaves no orphan revision, head advance, event, or receipt.
- **Preservation count is three:** synthetic acceptance data must contain all three retained PC-command edges (the Caelynn/Karsemine/Stafl edges identified in the source review), not merely “the other two.” Do not embed live IDs or production payloads in tests.
- **No live action:** synthetic tests only. The separate MIND dry-run is not V2 authority and does not authorize persistence.

## §5 Work plan

1. Re-anchor and confirm PRIME activated this exact handoff, `main` still has the pinned predecessor, the V1 handoff sync is accurate, and the serial write lease is uncontested.
2. Add strict V2 contracts and request hashing. Keep the V1 public/internal shape unchanged.
3. Add V2 materialization and repository flow that verify locator-null identity in both adoption and parent evidence, preserve all non-target payload records, and reuse the existing governed atomic publication boundary.
4. Add migration 0014 after 0013. Couple schema version to locator nullability; preserve existing V1 receipt reconstruction and append-only triggers. Reject downgrade if V2 receipts exist.
5. Add application/memory/PostgreSQL, exact-replay, rollback, concurrency, and migration witnesses. Include three retained PC-command edges in the positive synthetic witness.
6. Run the focused and required repository verification. Open only the single serial implementation PR authorized by PRIME; do not merge.

## §6 Acceptance gates

- `uv run pytest -q tests/unit/test_adopted_assertion_withdrawal.py`
- With the repository’s required PostgreSQL integration service enabled: `uv run pytest -q tests/integration/test_migrations.py tests/integration/test_postgres_adopted_assertion_withdrawal.py`
- `uv run ruff check src/dungeonmind/contracts/adopted_assertion_withdrawal.py src/dungeonmind/application/adopted_assertion_withdrawal.py src/dungeonmind/application/repositories.py src/dungeonmind/infrastructure/memory/repositories.py src/dungeonmind/infrastructure/postgres/existing_world_adoption.py migrations/versions/0014_adopted_withdrawal_v2.py tests/unit/test_adopted_assertion_withdrawal.py tests/integration/test_migrations.py tests/integration/test_postgres_adopted_assertion_withdrawal.py`
- `uv run pyright` plus the project’s PostgreSQL integration typing/CI job.
- Required positive witness: exactly the target relationship is absent; all other fields/evidence are preserved; the three PC-command edges survive; parent remains immutable; no negative assertion is added; child and receipt digests/readback are correct.
- Required negative witnesses: V1 still rejects null; V2 rejects non-null or mismatched locator state, absent/different span/source bindings, missing V4 membership, stale parent, tuple/profile/evidence drift, ambiguous targets, and changed-command replay. Failures leave no durable partial state.
- PostgreSQL proves atomic rollback and successful exact replay; migration upgrade/downgrade is exercised, with downgrade refused after a V2 receipt exists. No skip substitutes for the required database proof.
- No live-world, provider, source-body, or durable receipt writes.

The exact CI service command/environment must be taken from current checked-in workflows at activation; do not guess credentials or claim an integration pass from a skipped local suite.

## §7 Stop conditions

Stop and return to PRIME/steward if:

- the exact base, V1 merge, open-PR topology, or activation status changed;
- V1 semantics would need weakening or 0013 would need editing;
- the operation needs a new locator resolver, source-body read, or a second independent capability;
- exact V4 membership is unavailable for a future live target. The existing V4 classification repair remains a separate MIND-owned path; do not promote a receipt inside this withdrawal;
- a migration cannot preserve V1 receipt validity and append-only constraints;
- any path outside the prospective write lease is needed;
- the work would write to the live world, source store, or durable receipt outside isolated tests.

A new defect found during this serial slice is fixed in this PR only if it violates this V2 invariant and fits the activated lease; otherwise return it to PRIME for re-decomposition. Do not open a repair/successor PR.

## §8 Handback requirements

Report the implementation repository, branch, exact base/head, PR and status; migration revision; exact verification commands/results; V1 predecessor sync; decisions and rejected alternatives; and explicit remaining falsehoods. State clearly that no live-world action occurred and that code capability does not equal live-operation authorization.

