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
| accepted `alias` | Object alias | Subject target and non-empty value preserved |
| accepted `summary` | Object summary | Subject target and non-empty value preserved |
| accepted `relationship` | Relationship key/effect proposal | Subject, predicate, object, evidence, lineage, scope, temporal, visibility, and epistemic kind preserved |
| rejected assertion | Review history only | Assertion ID is excluded from every graph effect |
| pre-existing relationship key | fail closed | B.2d does not authorize relationship evidence augmentation or silent merge |
| new relationship key | `propose_new_relationship` | Exactly one accepted assertion is required per key |
| plan reference | Parent/schema/profile binding | Exact parent revision, graph schema/payload digest, and semantic-profile pin match |

For `confirm_existing`, each field operation includes the expected parent value
and the resulting value(s). An object has one canonical label slot and one
summary slot; multiple accepted label or summary assertions therefore fail
closed. Aliases are list additions and fail closed when normalized values
duplicate one another or an existing alias.

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
