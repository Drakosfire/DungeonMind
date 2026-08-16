# ADR-0019 — Atomic existing-world adoption boundary

**Status:** Accepted  
**Date:** 2026-08-15  
**Deciders:** implementing agent, per CUTOVER existing-world adoption dispatch after DungeonMind PR #31  
**Supersedes:** none  
**Related:** ADR-0002, ADR-0007, ADR-0010, ADR-0011, ADR-0015, ADR-0018

## Question

How does DungeonMind bootstrap one already-materialized world into an empty
namespace so a later Eldyrwild bundle has a durable, replay-safe landing
boundary, without fabricating a finalized contribution review or committing
partial source/history/graph state?

## Context

PR #31 made dual-sense relationship endpoint aspects representable as
`dm_union_graph_v6`. That closed representation. It did not adopt any live
world.

B.2f already proves the needed *publication* properties: one unit of work,
terminal receipt identity, durable-first exact replay, and one recovery probe
after an uncertain attempt. A historical world migration is not a user review
and must not mint `ContributionReviewState`, confirmation receipts, or B.2f
materialization rows to borrow those properties.

Public source, contribution, identity, and graph repositories each open their
own transaction. Calling them in sequence would allow source/history to commit
while the first revision/head or receipt does not. That is unacceptable for a
one-time whole-world migration.

The bundle is a migration authority artifact supplied to an explicit
application seam. A SHA of the consumed bytes proves identity of that
artifact; it does not prove the producer was authorized. The bundle must not
carry a self-asserted `bundle_sha256`. Transport/authorization is deferred.

This decision does not construct or apply the real Eldyrwild bundle. The named
successor is a Buddy-side producer that emits one revision-bound v6 bundle this
boundary can consume.

## Decision

1. **Publish `dm_existing_world_adoption_bundle_v1`.** The bundle carries
   source provenance, a `dm_union_graph_v6` payload, `SourceArtifactV2` rows,
   `SourceRevision` rows, `GraphContribution` history, and
   `dm_identity_decision_v1` history. v1 admits only `dm_union_graph_v6`.
2. **Canonical bytes are the identity.** UTF-8 JSON, `sort_keys=True`,
   tight separators, `ensure_ascii=False`, one trailing newline. Durable lists
   are sorted by id (authority refs by `(schema, identifier, sha256)`). Raw
   input must equal canonical reserialization or the seam refuses before
   mutation. The application hashes the consumed raw bytes itself.
3. **One terminal receipt per world.** `dm_existing_world_adoption_receipt_v1`
   is historical correspondence between bundle bytes, imported durable
   source/history rows, and the published first revision. It is not
   current-head state. Descendants and explicit rollback do not invalidate it.
   Exact replay ignores a new `adopted_at` and returns the original receipt.
4. **One atomic unit of work.** Under the existing world lock, the adapter
   verifies a pristine target (no head, graph revisions, contributions,
   identity decisions, source artifacts, or adoption receipt; a `worlds`
   registry row alone is allowed), then inserts source artifacts, revisions,
   contributions, identity decisions, publishes the first revision/head via
   the existing in-transaction graph helper, and writes the receipt — or rolls
   every family back. Public `put_*` / `append` methods are not called from
   inside the PostgreSQL unit of work.
5. **First revision identity uses the existing helper.**
   `parent_revision_id = None`, `expected_parent_revision_id = None`,
   `operation_ids = [adoption_id]`. Callers do not supply a revision id or
   graph digest separately from parsed bundle bytes.
6. **Durable-first replay and one recovery probe.** The application asks
   `get_for_world` before parsing/materializing. A matching SHA returns the
   original receipt without invoking the graph reader or the mutation path. A
   different SHA is an idempotency conflict. After a thrown mutation attempt,
   exactly one `get_for_world` probe runs: matching receipt is success; a
   known non-availability `DungeonMindError` with no receipt is re-raised;
   availability/unexpected failure with no usable recovery is
   `existing_world_adoption_outcome_unknown` with `retry_safe=true`. Success
   is never inferred from `get_head` or revision scans.
7. **Validation is persistence integrity, not Eldyrwild conformance.** Unique
   durable ids, world binding, source/revision/contribution/evidence closure,
   and v6 parse all refuse before mutation. This boundary does not replay
   imported contributions into the graph. The successor producer proves
   semantic conversion.

## Rejected alternatives

```text
fabricate a finalized review to reuse B.2f
  rejected: a historical world is not a user review

call public source/contribution/identity/graph repositories in sequence
  rejected: permits partial durable state

self-asserted bundle_sha256 on the bundle
  rejected: caller cannot supply the digest that attests the bytes

generic Buddy-history replay engine
  rejected: conversion proof belongs to the successor producer

API/CLI/browser transport in this PR
  rejected: the bundle is an entire world authority plane; authorization
  is a separate contract

real Eldyrwild bundle or sibling Buddy checkout
  rejected: DungeonMind must not import Buddy or claim live histories
```

## Consequences

DungeonMind can atomically adopt one explicit, versioned, already-materialized
world migration bundle into an otherwise empty world. Eldyrwild is not adopted.
Buddy relationship STOPs and product-authority cutover stay uncleared.

## Reversal path

```text
stop writing existing-world adoption receipts
leave published revisions/history in place as ordinary durable records
supersede with a later bundle/receipt version if the contract changes
never reinterpret existing receipt bytes in place
```
