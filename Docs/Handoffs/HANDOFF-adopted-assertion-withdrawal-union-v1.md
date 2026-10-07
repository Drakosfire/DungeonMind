# Handoff — adopted assertion withdrawal through union authority v1

**Status:** ACTIVE — implementation authorized by PRIME  
**Owner:** DungeonMind  
**Base:** `main` at `b81ca415a7e79d4024f3229a09ee5fdefff93eb3` (merged #97)  
**Branch:** `kernel/adopted-assertion-withdrawal-v1`  
**Topology:** one serial, branch-pinned contract + implementation PR. This handoff is portable on the branch; it does not need a separate merge to `main` before implementation.

## Outcome

Add one versioned, append-only, governed operation and receipt for withdrawing exactly one adopted relationship assertion from a new `dm_union_graph_v6` child. Its disposition is **unsupported by the bound source**; it does not mean false, contradicted, negated, or replaced.

This closes a narrow authority gap: the existing v2 review materializer supports per-assertion corrections for ordinary records but deliberately rejects adopted-era `ka:` IDs. Do not remove that guard or route this case through an ordinary contribution correction. Do not use the vNext `RetractAssertion` contract: the live authority is a union-graph revision.

## Authority and pins

The operation accepts identities and expected pins, never a caller-built graph payload or caller-authored evidence as authority. Before mutation, re-resolve and verify through DungeonMind-owned records:

1. The exact persisted existing-world adoption receipt and its fingerprint/version; require the receipt version with an exact membership manifest. Reject receipts that cannot prove exact membership.
2. The receipt’s immutable adopted revision and payload digest, plus the exact current expected parent revision and digest. The expected parent must still be current under the world lock/CAS.
3. Exactly one target relationship assertion in both the adopted revision and current parent, matching the requested assertion ID **and** the complete subject/predicate/object tuple. Reject missing, duplicate, changed, or ambiguous matches.
4. Every target evidence reference and its persisted source artifact, immutable source revision, and span/locator identity. Require the evidence membership to match the assertion and verify source/revision identity from the source repository; request fields alone cannot prove provenance. Do not fetch or mutate source bodies.
5. The parent graph schema and semantic-profile reference/descriptor. The child preserves them exactly.

The application requires the existing scoped COMMIT capability, including exact world and expected-parent pin. The repository is the final authority: it rechecks receipt, current parent, target tuple, and source-lineage bindings inside the same atomic operation boundary. No generic snapshot writer is exposed.

## Operation and receipt behavior

- Add strict versioned command/receipt contracts with stable operation identity, exact adoption/parent pins, target assertion and tuple, resolved evidence/source-span bindings, and the neutral `unsupported_by_bound_source` disposition.
- Provide one application operation that derives the child from the locked exact parent. It removes only the target relationship record; it preserves every other payload field, object, relationship, evidence reference, source artifact/revision, and the immutable parent. It creates no negative assertion.
- Persist the child revision, head event, and operation-specific terminal receipt atomically under the existing world lock and expected-parent CAS. The receipt records the adoption receipt fingerprint and all parent/target/source/child bindings needed for later verification.
- Exact replay of the same operation identity and command returns the same receipt with no additional revision/event. Reuse of that identity with changed input is an idempotency conflict. Receipts are append-only; expose no update/delete path.
- A stale parent, adoption-receipt drift, target tuple mismatch, profile mismatch, evidence/source/revision/span mismatch, or persistence-integrity failure must leave revision/head/event/receipt state unchanged.

Reuse the existing-world union repository and graph publication transaction/lock. Add only the operation’s receipt storage and required migration; do not build a generic correction framework or fabricate a contribution-review record.

## Exact write lease

- `Docs/Handoffs/HANDOFF-adopted-assertion-withdrawal-union-v1.md`
- `src/dungeonmind/contracts/adopted_assertion_withdrawal.py`
- `src/dungeonmind/application/adopted_assertion_withdrawal.py`
- `src/dungeonmind/application/repositories.py`
- `src/dungeonmind/infrastructure/memory/repositories.py`
- `src/dungeonmind/infrastructure/postgres/existing_world_adoption.py`
- `migrations/versions/0008_adopted_assertion_withdrawal.py`
- focused unit, contract, migration-chain, and PostgreSQL integration tests owned by this operation.

If an additional path proves necessary, stop and rebrief before editing. Do not edit existing B.2f correction behavior, the vNext contracts/repositories, Buddy, DungeonMindServer, WorldKeeper, OverMind runtime configuration, source inventory, or the live World.

## Acceptance proof

Use synthetic fixtures only. Prove at the application and repository boundaries:

- A valid operation omits exactly the target assertion in the child; all other relationships/objects and all `evidence_refs` remain byte-equivalent to the parent. Shared span evidence and all three PC-command relationships remain intact; the output contains no negative assertion.
- The parent remains readable and unchanged; the child is a `dm_union_graph_v6` revision with the same semantic profile and a correct digest.
- Exact replay returns the same receipt and creates zero extra rows; changed-command replay conflicts.
- Stale-parent and each receipt, target-tuple, profile, evidence, source-artifact, source-revision, or span mismatch fail before mutation.
- Concurrent same-parent operations permit at most one head advance; the loser is a typed stale-parent result with no orphan receipt/revision/event.
- PostgreSQL proves atomic rollback across child revision, head, event, and withdrawal receipt; successful receipt readback remains valid after a later child advances the head.
- Migration upgrade/downgrade and the full required focused suite pass; no test is skipped as a substitute for the PostgreSQL proof.

## Explicit exclusions

No live Eldyrwyld/`eldyrwild` publication or dry-run write; no provider/corpus experiment; no source body retrieval; no source/evidence deletion; no blanket contribution withdrawal; no false/contradicted/negated assertion; no vNext or KnowledgeSpace migration; no HTTP route, Buddy/DMS/WorldKeeper integration; no new general-purpose correction framework.

The live `rev:680c246047d67f9fe0293ee90526f670` / `ka:rel:edge:node:captain-lysandra-ironveil:commands:faction:town-guards-mireward-gate` case is only a future separately authorized witness. Revalidate every pin at that time; do not bake live IDs or production data into tests.

## Delivery

Commit this handoff before implementation begins. Then implement only the lease above, run and record exact evidence, inspect the cumulative base-to-head diff, commit and push the branch, open one PR, and request independent PRIME review. Do not merge; merge authority remains separate.
