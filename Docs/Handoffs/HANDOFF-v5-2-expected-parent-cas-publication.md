# HANDOFF — V5.2 Expected-Parent Atomic CAS Publication

**Provenance:** MIND
**Status:** ACTIVE — implementation from merged PR #69
**Repository:** `Drakosfire/DungeonMind`
**Roadmap phase:** V5.2
**Branch:** `kernel/v5-2-expected-parent-cas-publication`
**Base:** `9f006bf77d72faabee8a3eef359b89a3d537b0c1`
**Predecessor:** V5.1 — Generic Governed Materialization
**Successor:** V5.3 — Durable Idempotent Replay / Recovery
**PR topology:** serial

## Predecessor

```text
PR #69
accepted head: daa6de4d8a3f36095deff68614db34f2eaba342e
substantive runtime: cc62079883f34227aa001b7358b6abe192d7f36e
review cycles: 4
final PASS: 5257033813
disposition: V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED
merge: 9f006bf77d72faabee8a3eef359b89a3d537b0c1
frozen V0 aggregate: fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

Do not claim `V5_2_EXPECTED_PARENT_CAS_PUBLICATION_ACCEPTED` in this PR.

## Primary question

> Given one already-governed V5.1 materialization, can DungeonMind durably publish its exact `PublishKnowledgeRevisionCommand` as one immutable native-vNext `KnowledgeRevision` and atomically advance exactly one `KnowledgeHead` under expected-parent compare-and-swap semantics?

## Binding decisions

1. Native authority uses `knowledge_spaces`, `knowledge_revisions`, `knowledge_heads`, and `knowledge_head_events`. It does not reuse World tables, `world_id`, or `lock_world`.
2. Frozen V0 contracts do not change. `created_at` is stored history and is not part of revision identity.
3. Revision identity is `rev:<32 hex>` over canonical material `dm_knowledge_revision_identity_v1`: space, parent, ordered operations, graph schema, payload digest, DomainContractRef, SemanticProfileRef, and MigrationOriginRef.
4. The supported write entrypoint is `publish_governed_materialization(materialization, repository=...)`. Raw command publication stays on the repository port.
5. Repository CAS is authoritative. Stale work is not rebased, retried, or inferred from a later head read.
6. Revision insert, head advance, and one `publish` head event commit atomically. `rollback` is reserved in the schema and is not implemented.
7. Genesis is allowed only when both expected parent and current head are absent.
8. An existing immutable revision with a conflicting envelope fails closed. A thrown availability error is not retried and is not resolved by probing head or revisions.
9. V5.3 owns receipts, exact replay-as-success, and uncertain-outcome recovery.

## What remains false

```text
no durable publication receipt
no exact replay-as-success
no retry-safe unknown-outcome recovery
no public write transport
no DungeonBuddy write adoption
no bridge-genesis migration
no legacy World cutover
no identity-decision supersession ledger
```
