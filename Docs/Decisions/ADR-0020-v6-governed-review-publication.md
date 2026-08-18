# ADR-0020 — v6 governed review publication

**Status:** Accepted  
**Date:** 2026-08-18  
**Deciders:** implementing agent, per CUTOVER v6 governed review publication dispatch after Buddy PR #619 Review Cycle 1  
**Supersedes:** ADR-0009's implicit boundary that only `dm_union_graph_v3` is materializable  
**Related:** ADR-0007, ADR-0008, ADR-0009, ADR-0018, ADR-0019

## Question

How does DungeonMind commit a real, GM-confirmed child revision on a
`dm_union_graph_v6` world — carrying the confirmed contribution as a durable
`dm_graph_contribution_v2` ledger entry — without weakening the governance
invariants the v1/v3 path enforces, and without a schema migration?

## Context

Buddy's whole-world authority transfer (Buddy PR #619) requires DungeonMind to
become the write authority for the adopted Eldyrwild world. Review Cycle 1
attempted the switch and found the governed write seam could not express it:

1. `dm_contribution_review_intent_v1` binds the candidate to
   `GraphContribution` (v1) and admits only the four assertion kinds
   (`object`, `relationship`, `object_summary`, `object_property`). Buddy's
   kernel vocabulary is `node`, `edge`, `alias`, `attribute`, `evidence_ref`
   over `GraphContributionV2`.
2. The B.2f materializer (`review_materialization.py`) is hard-bound to
   `dm_union_graph_v3`; the adopted world is `dm_union_graph_v6`
   (assertion-scoped relationship endpoint aspects, `KnowledgeAssertionMetadataV1`
   on every record, `EvidenceRefV2` payload ledger).

ADR-0009 built the materializer seam as schema-parameterized but only ever
wired v3. This slice extends that seam rather than replacing it.

The v2 contribution contract (`dm_graph_contribution_v2`) and the v6 snapshot
reader already exist and are durable-proven by the Eldyrwild adoption
(ADR-0019). The `contribution_reviews` table stores a versioned JSON payload
with a `schema_version` column, and its contribution foreign keys reference
`graph_contributions`, which already stores v2 rows — so v2 review states
persist with no migration.

## Decision

1. **New contract family `dm_contribution_review_intent_v2`.** Same governance
   shape as v1 — content-bound `review_intent_sha256` over a distinct digest
   domain separator, exact assertion-verdict coverage, identity
   proposal/verdict pairing, receipt binding — but the candidate is a
   `GraphContributionV2`, `plan_ref.base_graph_schema` must be
   `dm_union_graph_v6`, and the reviewable assertion vocabulary is the five
   Buddy kernel kinds (`node`, `edge`, `alias`, `attribute`, `evidence_ref`).
   Candidate assertions of any other kind are admissible only with a
   `rejected` verdict. Identity proposals must cover exactly the **accepted**
   candidate `node`/`alias` subject targets — a rejected `node`/`alias`
   assertion demands no identity adjudication and keeps its candidate
   identity outcome untouched. Candidate contributions carry no
   `identity_decision_ids` (that seam is unchanged v1 behavior).
2. **New materializer `review_materialization_v6`.** Applies accepted v2
   assertions to a typed `UnionGraphV6Payload`:
   - `node` + `create_new` requires `value.dm_kind` (profile-qualified kind)
     and fails closed on an existing object; `confirm_existing` merges
     aliases and retained evidence only — kind, label, and summary are never
     rewritten by merge.
   - `edge` uses `value.edge_id` or derives
     `edge:{subject}:{predicate}:{target}` (Buddy's convention, reimplemented
     without importing Buddy), requires `value.dm_predicate`, fails closed on
     missing endpoints and on id collisions with different content. A
     same-identity duplicate no-ops only when the materialized assertion
     metadata is genuinely identical (true replay); the record carries
     exactly one assertion identity, so any distinct accepted assertion fails
     closed `relationship_id_collision` rather than disappearing. Endpoint
     aspects are rejected as unsupported.
   - `alias` appends one `AliasAssertionV4Record` with **casefolded** dedup
     (a casefolded duplicate no-ops before evidence registration) and extends
     the object's retained evidence, mirroring Buddy's merge.
   - `attribute` / `evidence_ref` register evidence only; the v6 graph model
     has no property/assertion landing zone for them yet.
   - `value["session_ids"]` materializes into `session_refs` on every record
     the assertion creates (object existence, alias, relationship); a
     malformed non-list value fails closed `unsupported_field_shape`.
   - Evidence lifts `EvidenceRef` (v1) to `EvidenceRefV2`, reusing an
     identical parent record and failing closed on same-id conflicting
     content. Source-identity-only `node`/`edge`/`alias`/`attribute`
     assertions synthesize the contribution-scoped fallback id
     `evidence:{reviewed_contribution}:{graph_object}`, mirroring Buddy;
     `evidence_ref` assertions stay fail-closed
     (`accepted_assertion_missing_graph_evidence`).
   - Mechanics/statblock binding material is excluded from this World Graph
     publication seam: an assertion carrying the `uses_statblock` predicate
     (raw or profile-qualified) or `threat_statblock_binding` /
     `statblock_binding` value keys fails closed
     (`unsupported_assertion_kind`), regardless of assertion kind. The screen
     runs immediately after the accepted gate, before the non-mutating
     identity-outcome skip, so a skipped assertion cannot smuggle binding
     material past the boundary.
   - Accepted assertions whose identity outcome is non-mutating
     (`unresolved`, `ambiguous`, `deferred`, `rejected`) are skipped, matching
     Buddy's merge filter.
   - `assertion_corrections` remove matching alias/summary/property/aspect
     records and whole relationships; targeting an existence record fails
     `correction_target_existence`, and an unresolvable target fails
     `correction_target_unresolvable`. Adopted-era `ka:*` records predate
     contribution receipts, so corrections targeting them fail closed
     `correction_target_unresolvable` with zero mutation; the receipt-aware
     correction slice is explicitly future work.
   - The parent payload must round-trip through `UnionGraphV6Payload`
     byte-identically before any mutation is computed, and the result payload
     revalidates through the pinned profile reader.
3. **Publication dispatches on review-state schema.** `_reload_review`
   reconstructs v1 or v2 by the stored `schema_version`;
   `publish_finalized_review` routes v1 states to the v3 materializer and v2
   states to the v6 materializer. The materialization binding check is
   plan-bound (`graph_schema != plan_ref.base_graph_schema`), so v1 behavior
   is byte-identical. No publication command/receipt contract changes:
   `graph_schema` was already data.
4. **No migration.** Both adapters persist v2 review states through the
   existing versioned payload column and the existing finalize-time
   contribution append (candidate superseded + reviewed active). The reviewed
   `GraphContributionV2` lands in the same ledger the adoption history uses.
5. **New finalize service** `finalize_contribution_review_v2` with the v1
   gates: capability policy under `dungeonmind.finalize_contribution_review_v2`,
   head-CAS preflight, parent digest/schema/profile preflight, then state
   construction that preserves candidate provenance (`source_kind`,
   `unresolved_mentions`, `diagnostics`, `assertion_corrections`) on the
   reviewed contribution.

## Amendments

**2026-08-18 — PR #37 Review Cycle 1 (review 4963405179).** The initial
implementation deviated from the dispatch on seven bounded semantics; all
seven are corrected above and pinned by conformance + owning-boundary
integration tests:

1. Adopted-era `ka:*` corrections fail closed `correction_target_unresolvable`
   (the initial implementation applied the removal).
2. Mechanics/statblock binding material fails closed on any assertion kind
   (the initial implementation gated only `assertion_kind`).
3. Fallback evidence extends to `alias`/`attribute` (initially node/edge
   only); `evidence_ref` stays fail-closed.
4. `value["session_ids"]` materializes into `session_refs` (initially
   discarded).
5. Identity proposal coverage counts accepted `node`/`alias` targets only
   (initially all candidates, forcing adjudication of rejected assertions).
6. Same-identity duplicate edges merge retained evidence/session refs;
   identical content is a true no-op (initially any same-identity duplicate
   no-opped before evidence registration, silently dropping provenance).
   **Superseded by Review Cycle 2 below:** merging retained provenance but
   still lost the second assertion identity, so duplicates now fail closed
   unless the materialized metadata is genuinely identical.
7. Alias dedup is casefolded (initially exact-string).

A cross-PR concern surfaced in the same review is deliberately **not**
addressed here: two reviews may finalize before publication with only one
winning the head CAS, leaving the loser durable-but-unpublished, and Buddy
PR #619's hydration adapter must bind to the published head rather than
replaying every active contribution. That repair belongs to Buddy #619; this
ADR's review lifecycle is unchanged.

**2026-08-18 — PR #37 Review Cycle 2 (review 4963700792).** Two bounded
corrections, both pinned by conformance and owning-boundary integration
tests:

1. The mechanics authority screen now runs immediately after the accepted
   gate, before the non-mutating identity-outcome skip — an accepted
   assertion marked `ambiguous` can no longer carry `statblock_binding`
   material past the boundary.
2. Same-identity duplicate edges no longer merge evidence/session refs. The
   relationship record carries exactly one assertion identity, and replay
   safety is owned by the publication layer, so a duplicate no-ops only when
   the materialized assertion metadata is genuinely identical; any distinct
   accepted assertion identity fails closed `relationship_id_collision`.

## Rejected alternatives

```text
widen the v1 intent to admit v2 candidates
  rejected: mutating a versioned contract in place breaks every stored
  digest binding; a new schema version is the honest seam

teach the v3 materializer v6 records
  rejected: the two payload shapes differ in every record type; one
  materializer with internal conditionals is strictly harder to prove
  than two schema-pure materializers behind a dispatch

migrate contribution_reviews to v2-native columns
  rejected: the versioned JSON payload already carries both schemas;
  a migration adds risk without adding truth

transport/API surface for v2 finalize
  rejected: Buddy integrates in-process; transport is a separate contract

endpoint-aspect authoring through the v2 review path
  rejected: out of scope for the cutover write seam; the materializer
  fails closed on aspect-bearing values until a later slice briefs them
```

## Consequences

- A `dm_union_graph_v6` world accepts governed child revisions through the
  same publication boundary as v3, proven on the sealed Eldyrwild adoption
  (D_A → D_B with parent linkage, replay, and CAS-loser evidence).
- Buddy's `confirm` write path has an expressible DungeonMind target; the
  Buddy-side authority switch (PR #619) can implement the real write.
- ADR-0009's v3-only materialization claim is superseded; its seam design
  (pure function, schema-parameterized result, plan-bound validation) is
  affirmed and reused.
- Product authority remains Buddy; this slice changes no routing.

## Reversal path

```text
stop finalizing v2 reviews (capability policy gate)
leave published v6 revisions and v2 ledger rows in place as durable history
the v1/v3 path is untouched and remains the default for v3 worlds
supersede the v2 contract family with a v3 family if the kernel vocabulary
changes; never reinterpret stored v2 payloads in place
```
