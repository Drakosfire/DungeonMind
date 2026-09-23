# ADR-0025: Durable vNext publication replay and recovery

**Status:** Accepted for V5.3  
**Date:** 2026-09-23

For each `(space_id, publication_id)`, DungeonMind stores one immutable
`KnowledgePublicationReceipt` binding the canonical JSON SHA-256 of one
`PublishKnowledgeRevisionCommand` to one terminal published revision. The
receipt is committed in the same transaction as the revision, head transition,
and publish event.

Receipt lookup is the only recovery authority. Exact retries return the
verified original receipt without changing the head or emitting another event.
Changed commands fail with an idempotency conflict. Recovery never infers
success from the current head, revision existence, timestamps, or history.

Prospective entity references, transport, workers, and legacy migration remain
outside V5.3.
