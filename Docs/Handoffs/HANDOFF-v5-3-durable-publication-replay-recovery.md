# HANDOFF — V5.3 durable publication replay and recovery

**Status:** IMPLEMENTED — verification in progress  
**Base:** `01762848cbdd666b092d4cb26af558ba1468fa4d` (merged PR #71)  
**Successor:** V5.4 — prospective-reference identity allocation + substitution

For one `(space_id, publication_id)`, DungeonMind binds one exact publication
command to one terminal published revision. The receipt, revision, head
transition, and publish event commit atomically. Exact retries and recovery
return the verified receipt even after descendants advance the head; changed
retries and ambiguous recovery fail closed.

Implemented: `KnowledgePublicationReceipt`, receipt-first application
recovery, in-memory and PostgreSQL durable storage, migration 0009, typed
idempotency/integrity/outcome-unknown errors, and focused adversarial tests.

Still false: prospective entity references/allocation, DungeonBuddy or
WorldKeeper write adoption, HTTP transport, bridge-genesis migration, legacy
writer cutover, workers/queues, and storage optimization.

Frozen V0 aggregate remains
`fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`.
