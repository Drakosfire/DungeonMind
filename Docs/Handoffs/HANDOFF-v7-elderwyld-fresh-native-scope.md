# V7 — Elderwyld fresh-native scope amendment

Status: proposed for independent review. The operator confirmed current primary
Buddy Elderwyld as the scope and directed that fresh ingestion replace the
retired World, without an old-name bridge. This record proposes how to apply
that decision; it is not a V7 acceptance record or a runtime write lease.

## Decision

For this deployment, supersede the exact-ID bridge path in
[the original V7 handoff](HANDOFF-v7-bridge-genesis-migration.md). Do not mark
its gates passed, construct a bridge into a populated space, revive the old
name, or restore archives as a prerequisite. Leave historical artifacts and
other deployments outside this decision.

## Evidence and limits

- [Buddy #1858](https://github.com/Drakosfire/DungeonMindBuddy/pull/1858)
  settled the consolidation to canonical managed/native `elderwyld` and
  retired historical `eldyrwild`. Its empty adoption was classic
  `dm_union_graph_v6`, revision `rev:d3015ae21f9ae0d2d3a125b505087b8e`.
  It is not the native genesis.
- The retained later native publication receipt records space `elderwyld`,
  parent `rev:01e4f9ad8d4fce8f35e7db5ae9937c53`, and child
  `rev:aa301cb2706ebefb90ebfbe6bcb283c2`. This proves a publication at
  that pin, not the current head, completeness, or route selection.
- The original D_A fixture remains historical design evidence only.

## Replacement checkpoint before V8

Buddy's deployment owner must attest the managed World binding and actual
runtime package/route pins. MIND must reconcile the native genesis and head
lineage and publication receipts. Source owners and Buddy must reconcile
the agreed fresh-ingestion inventory to admitted source revisions and exact
citations, recording unsupported, missing, or intentionally excluded inputs
without treating unknown as absent. Use approved read-only evidence or an
explicitly authorized isolated proof. No restore, new export, provider run,
data write, or serving switch follows from this document.

V8 joint semantics and performance, V9 verified serving authority and rollback,
V10 current-path retirement, and V11 serving baseline remain separate gates.
Historical pins in the agreed serving scope still require explicit disposition;
the retired World is not a current fallback.

## Delivery

Serial decision slice, MIND-owned at Core base `363c376`; documentation only.
Verify pinned evidence and relative links; obtain independent architecture
review and separate merge approval. The standalone path avoids the mutable
roadmap and stewardship files already touched by Core #158. Reconcile those
indexes after the decision and any overlapping changes settle.
