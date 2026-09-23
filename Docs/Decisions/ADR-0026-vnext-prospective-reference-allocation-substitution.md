# ADR-0026 — vNext prospective-reference allocation and substitution

**Status:** Accepted for V5.4 implementation; V5.4 itself is not yet accepted  
**Date:** 2026-09-23  
**Authority:** `Docs/Handoffs/HANDOFF-v5-4-prospective-reference-allocation-substitution.md`

## Context

The frozen vNext graph contracts require durable entity and assertion IDs, but
a governed transaction may need to create an entity and refer to that create
result from another item before any durable ID exists. The caller must not
become the durable ID allocator or maintain a second identity ledger.

## Decision

1. Prospective handles are transaction-local caller references, not durable IDs.
2. DungeonMind deterministically allocates entity and assertion IDs from
   `(space_id, publication_id, client_op_id, result_kind)` using a versioned,
   type-separated identity schema.
3. Allocated IDs are provisional until atomic publication commits.
4. `result_of` resolves only prospective entity creates in V5.4.
5. Create-new never performs similarity lookup, identity reconciliation, or
   substitution of an existing object.
6. Prospective contracts are additive; the frozen V0 `Entity`, `Assertion`,
   `KnowledgeContribution`, command, and receipt contracts remain unchanged.
7. A pure resolver produces an ordinary canonical `KnowledgeContribution`,
   after which the accepted V5.1 materializer performs structural and
   domain/profile validation.
8. The durable prospective result mapping is separate from the V5.3 receipt.
9. The result mapping commits atomically with the V5.3 receipt, revision, head,
   and publish event.
10. V5.3 remains the only publication replay/recovery authority.
11. WorldKeeper WK-3 is unblocked only after Steward acceptance of the canonical
    prospective-create/dependent-reference witness.

## Consequences

The Kernel can calculate stable provisional IDs without holding a database
transaction open during graph materialization. Callers cannot treat those IDs
as existing until the V5.4 result is returned or recovered. Exact replay can
return the original mapping without scanning graph history, while changed
prospective intent conflicts under the existing publication identity.

Source/evidence prospective creation, assertion-result entity endpoints,
transport, identity reconciliation, bridge migration, and consumer runtime
integration remain out of scope.
