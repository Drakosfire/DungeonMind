# ADR-0024 — Native vNext KnowledgeRevision identity and expected-parent CAS publication

**Status:** Accepted for V5.2 implementation
**Date:** 2026-09-21
**Related:** ADR-0010, ADR-0011, ADR-0012

## Decision

1. Native `knowledge_*` persistence is separate from legacy World tables. `space_id` is not translated into `world_id`.
2. Native revision identity includes `space_id`, parent, ordered operations, graph schema, graph payload digest, DomainContractRef, SemanticProfileRef, and MigrationOriginRef.
3. `created_at` is immutable revision history. It is not content-address identity. A conflicting stored envelope, including a different `created_at`, fails closed.
4. Repository expected-parent CAS is authority. An earlier head observation is not a lock, and stale work is never rebased.
5. Revision insert, head transition, and the publish head event are one atomic transaction.
6. V5.2 provides no publication receipt, exact replay-as-success, or uncertain-outcome recovery.
7. V5.3 remains responsible for exact replay and recovery probes.

## Consequences

A thrown V5.2 publication call may have an unknown commit outcome. Identical automatic retry is not promised safe. External write transport stays out of this slice.
