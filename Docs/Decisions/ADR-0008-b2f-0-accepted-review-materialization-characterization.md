# ADR-0008 — B.2f-0 accepted-review materialization characterization

**Status:** Accepted (characterization only)
**Date:** 2026-08-02
**Deciders:** B.2f-0 implementation dispatch
**Extends:** ADR-0007 (finalized contribution review adoption)

## Decision

B.2f-0 adds a test-only, pure characterization of the graph effects implied by
one finalized B.2e review against one exact parent revision. It creates no
production materializer, public or durable schema, repository write,
publication operation, recovery behavior, transport, or Buddy integration.

The characterization consumes:

```text
validated ContributionReviewState
+ exact WorldGraphRevision and parsed dm_union_graph_v3 parent
→ deterministic proposed object/relationship/evidence effects
→ deterministic effect digest
```

The implementation is deliberately under `tests/conformance`. B.2f-a may
replace it with a production materializer only after this mapping is accepted.

## Review-to-graph-effects matrix

| Review input | Characterized effect | Required checks |
| --- | --- | --- |
| `create_new` identity verdict | `create_object` for the pinned target | Target absent from exact parent; accepted label exists exactly once |
| `confirm_existing` identity verdict | `reuse_existing_object` with executable field operations | Target exists in parent with the proposed kind; one accepted label is an explicit `replace` of the canonical label slot, one accepted summary is an explicit `replace` of the canonical summary slot, and accepted aliases are explicit `append` values |
| `reject_candidate` identity verdict | `exclude_from_graph_truth` | No object or dependent relationship effect |
| accepted `label` | Object label | Subject target, label bytes, evidence, lineage, scope, temporal, visibility, epistemic kind preserved |
| accepted `alias` | Object alias | Subject target and non-empty value preserved; reused source assertion/evidence IDs must not collide with the exact parent namespaces |
| accepted `summary` | Object summary | Subject target and non-empty value preserved; reused source assertion/evidence IDs must not collide with the exact parent namespaces |
| accepted `relationship` | Relationship key/effect proposal | Subject, predicate, object, evidence, lineage, scope, temporal, visibility, and epistemic kind preserved |
| rejected assertion | Review history only | Assertion ID is excluded from every graph effect |
| pre-existing relationship key | fail closed | B.2d does not authorize relationship evidence augmentation or silent merge |
| new relationship key | `propose_new_relationship` | Exactly one accepted assertion is required per key |
| plan reference | Parent/schema/profile binding | Exact parent revision, graph schema/payload digest, and semantic-profile pin match |

For `confirm_existing`, each field operation includes the expected parent value
and the resulting value(s), plus an explicit provenance transition:

- Canonical label replacement retires the parent core evidence references and
  uses the accepted source assertion's evidence references for the resulting
  label. The canonical graph field has no graph assertion ID; the accepted
  assertion ID remains source provenance only.
- Alias append retains every parent alias assertion and its evidence, then
  reuses each accepted source assertion ID as the resulting graph alias
  assertion ID and unions the parent and accepted evidence references.
- Summary replacement retires the parent summary assertion and evidence, then
  reuses the accepted source assertion ID and evidence for the resulting
  summary assertion.
- Retained fields keep their parent assertion/evidence identities; omitted
  fields produce no assertion or evidence.
- Reused accepted alias/summary assertion IDs and emitted accepted evidence IDs
  are checked against the exact parent namespaces; any collision fails closed
  before effects are emitted.

An object has one canonical label slot and one summary slot; multiple accepted
label or summary assertions therefore fail closed. Aliases are list additions
and fail closed when normalized values duplicate one another or an existing
alias. Accepted source provenance (source artifact/revision, campaign scope,
temporal scope, visibility, and epistemic kind) is copied into each field
operation.

Temporal scopes are copied as opaque JSON values. No Timeline interpretation is
performed. Relationship IDs are not assigned; a pre-existing or duplicate
accepted relationship triple fails closed rather than silently merging evidence.

## Invariants

- Identical finalized review and exact parent produce byte-equivalent output
  and the same `effect_digest`.
- Changed parent identity, graph payload, graph schema, or semantic-profile pin
  fails closed.
- The parsed snapshot is produced from the exact payload after its digest is
  checked; callers cannot supply an independently invented snapshot.
- Invalid/tampered finalized review state fails before characterization.
- Rejected assertions and their review history never appear in graph effects.
- Parent assertion-ID and evidence-ID collisions fail closed before graph
  effects are emitted.
- Pre-existing and duplicate accepted relationship triples fail closed.
- `durable_writes` is always empty; graph head and identity-decision effects
  are explicitly unchanged.
- No mechanics, external resource binding, Timeline semantics, transport, or
  Buddy import is part of this slice.

## Later decomposition

- **B.2f-a:** pure reviewed-contribution materializer.
- **B.2f-b:** exact-parent CAS publication.
- **B.2f-c:** durable publication operation and uncertain-outcome recovery.
- **B.2f-d:** service transport and external consumer contract.
- **Buddy:** shadow adoption and eventual authority migration.
