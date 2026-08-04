# ADR-0010 — B.2f-b finalized-review expected-parent CAS publication

**Status:** Accepted (B.2f-b)  
**Date:** 2026-08-03  
**Deciders:** B.2f-b implementation dispatch  
**Extends:** ADR-0007, ADR-0008, and ADR-0009

## Decision

A finalized B.2e review is the publication authority artifact. B.2f-b adds one
trusted application seam:

```python
publish_finalized_review(
    world_id,
    review_id,
    *,
    published_at,
    review_repository,
    world_graph_repository,
    graph_reader,
) -> FinalizedReviewPublication
```

The seam accepts identifiers, a publication timestamp, and existing ports only.
It never accepts caller-supplied review state, contribution, materialization,
graph payload, parent override, operation ID, publication command, or capability
object. It loads the exact durable `ContributionReviewState` by
`(world_id, review_id)`, reload-validates it, reads the current head, requires
that the head equals `record.plan_ref.expected_parent_revision_id`, loads that
exact parent, and invokes the B.2f-a materializer.

The service then constructs exactly one existing `PublishRevisionCommand`:

| Command field | Source |
| --- | --- |
| `world_id` | durable review record, equal to the requested world |
| `parent_revision_id` | `record.plan_ref.expected_parent_revision_id` |
| `expected_parent_revision_id` | the same exact parent ID |
| `operation_ids` | `[record.operation_id]`, preserving singleton order |
| `graph_schema` | B.2f-a materialization |
| `graph_payload` | fresh B.2f-a materialization payload copy |
| `created_at` | caller-supplied `published_at` |

The expected revision ID is computed with the existing
`compute_revision_id` helper over the exact world, parent, ordered operation
list, graph schema, and materialized payload digest. The sole commit point is
`WorldGraphRepository.publish_revision`. The returned `WorldGraphRevision`
must match the complete expected envelope, including revision ID, parent,
created timestamp, operation IDs, schema, payload digest, and published status.
Only then is the ephemeral `FinalizedReviewPublication` returned.

The early head read is a preflight optimization, not a lock. Repository CAS is
authoritative: a writer that advances the head after preflight causes a typed
`StaleParentRevisionError`, with no stale child from this call. A known stale
review is never rebased or replanned.

## Retry and failure boundary

Immediate replay after a known success is stale, not idempotent success. An
explicit rollback to the exact parent may permit the existing repository to
republish the same content-addressed revision; B.2f-b invents no second
identity.

After `publish_revision` returns, the service performs no post-commit read and
issues no second write. If an adapter raises an arbitrary availability or
connection error, B.2f-b makes no claim about whether the commit happened and
does not retry, scan revision history, or infer success. Durable operation
identity, exact replay, and uncertain-outcome recovery belong to B.2f-c.

Missing reviews use the typed `contribution_review_not_found` error. A returned
state that cannot be revalidated or whose durable identity disagrees with the
requested identifiers produces a sanitized `PersistenceIntegrityError`.
Existing head, parent, materialization, CAS, and adapter failures retain their
typed failure semantics. B.2f-b does not mutate review, contribution, or
identity-decision state.

## Rejected alternatives

- Accepting a caller-supplied review state or materialization payload.
- Introducing a second confirmation or publication-time capability policy.
- Replanning or rematerializing against a newer head after staleness.
- Treating a stale replay as already-published success.
- Scanning revision history or reading the head after an uncertain outcome.
- Combining publication with durable review-to-revision identity or recovery.
- Appending `IdentityDecisionRecord` rows in the same or a second transaction.
- Changing graph contracts, repository ports, adapters, migrations, or adding
  API, CLI, agent, UI, or consumer transport.

## Proof

The in-memory owning-boundary suite proves exact Tripod publication, durable
review-only authority, missing-review rejection, known stale preflight,
write-free materialization failure, CAS race rejection, concurrent same-review
one-winner/one-stale behavior, immediate stale replay, rollback replay,
returned-envelope integrity, no post-commit reads, and unknown-outcome
propagation without retry.

The PostgreSQL suite uses the existing migrations and adapters to prove exact
fixture publication, exact payload/digest and caller timestamp preservation,
review byte-equivalence, immediate stale replay, and two independently opened
repository/service callers racing finalized reviews pinned to one parent.

The primary identities are:

```text
world:synthetic-gatewatch
review:cff0162637b428e634e8cccaa9958dc2
reviewop:11111111111111111111111111111111
contrib:65cdb14d13c40e5b8725fd5111509854
confirm:fa0d200c9922caf3c7e925b320cf9dae
rev:f2d5164c176289c5f3df7e68b4f0e46d
payload sha256 75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
rev:6e02bd224f6b5616534f10026c8b9679
```

No durable publication record, retry-as-success, uncertain-outcome recovery,
identity-decision append, public write surface, or external product adoption
is claimed by this decision.
