# V7 — Elderwyld fresh-native scope amendment

Status: scope amendment merged in Core #166; evidence checkpoint pending acceptance. The operator confirmed current primary
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

## Replacement checkpoint evidence — 2026-11-13

MIND owns this serial evidence-only follow-up on Core `ac4cacb`, ahead of
V8. Scope is this handoff only, avoiding the indexes touched by Core #158.
Independent review is required; this record does not activate V8.

| Obligation | Read-only result | Limit |
| --- | --- | --- |
| Serving identity | Local Buddy Graph view selected managed `elderwyld` and returned native head `rev:9a457bfed6bc517af83a7a719644970c`. World listing reported active binding version 3; a read of the native authority matched that exact head in space `elderwyld`. | The observed Graph route is native; other mounted routes still require attribution. The listener checkout observed at `823ee37f` and installed Core distribution pin `855f23bd` are disk observations, not a process image attestation. |
| Lineage | A head-anchored recursive parent walk found 280 revisions through genesis `rev:3582a950abf652f2cab29aa54552ed6a`, including the refresh child above. All 280 revisions matched publication receipts with matching expected parent and graph payload digest. | Receipt/revision metadata reconciliation, not full historical payload replay. |
| Source coverage | The refresh ledger and timeline census match on 47 distinct sessions (17 C1, 30 C2). Each session had a unique native admission match using its reviewable run's artifact identity and frozen source component digest, and each matched revision had evidence at the pinned head. | One matched revision per session is not proof that every run or candidate was admitted. |
| Exact citation witness | At least one representative per session: 17 from retained exact readback at this head, 30 from additional Core native text opens at source epoch 179, matching the admitted artifact and revision. No unavailable results in those 30; head unchanged after the reads. | Not exhaustive citation verification or GM/player parity. The Graph canvas reports a partial projection: 3,005 objects loaded and 3,828 assertions omitted. V8 must verify required behavior despite projection limits. |

The retained exact readback (SHA-256
`9ac2ab62d63901f70415967bd4eada3666e384dcba578d55a5d6d829a2ba491f`)
records 243 available, matching citation records. That larger citation count
does not increase the number of sessions with independently checked witnesses.
Raw source bodies, credentials and private records are not part of this change.

**Outstanding:** Buddy deployment evidence must tie the loaded build and Core
package to the serving route; MIND owns independent verification of the native
pin. The source and Buddy product owners must disposition the remaining
candidate scope: the retained ledger records 10 chronology review witnesses,
37 unverified review dispositions, and all 47 full-candidate publication
dispositions unverified. This does not mean unpublished. The accepted scope
must identify any required candidates and explicitly record exclusions or
unsupported inputs before V7 is accepted. No ingestion rerun, archive restore,
live write or cutover is part of this slice.
