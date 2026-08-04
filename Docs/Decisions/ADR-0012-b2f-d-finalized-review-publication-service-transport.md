# ADR-0012 — B.2f-d finalized-review publication service transport

**Status:** Accepted for B.2f-d implementation  
**Date:** 2026-08-04  
**Deciders:** B.2f-d implementation dispatch  
**Extends:** ADR-0011

## Decision

B.2f-d exposes the existing B.2f-c terminal publication seam through a separate
FastAPI service app. The existing read-only Mind Turn host remains unchanged.
The new host exposes only:

```text
GET  /healthz
GET  /readyz
POST /v1/finalized-review-publications
```

The request is the strict
`dm_finalized_review_publication_request_v1` contract containing only
`world_id` and `review_id`. A one-world bearer secret is bound at the transport
edge by digest and is never retained or reflected. The server supplies one
timezone-aware UTC timestamp per authorized invocation. The route delegates once
to `publish_finalized_review` and returns the existing terminal
`dm_finalized_review_publication_v1` record without a transport wrapper.

Fresh success, durable replay, and recovery after a lost response all return
HTTP 200 with the same body shape. Successful responses are `no-store`.
`finalized_review_publication_outcome_unknown` maps to HTTP 503 with
`retry_safe=true` and explicitly tells the caller that retrying the identical
request is safe.

## Authority and boundaries

B.2f-c remains the sole publication and recovery authority. The HTTP layer does
not read the head, inspect reviews or publication rows directly, materialize
graphs, retry, infer success from current-head state, or mutate review and
contribution lifecycle. A current head is not evidence that a historical
publication succeeded.

Readiness checks only database connectivity, required table visibility, and the
configured world binding. It does not require a review, inspect a head, return
graph bytes, or attempt publication.

The checked-in external example is a standard-library-only server-side client.
It sends the exact request twice when `--verify-replay` is selected and compares
canonical JSON. It does not import DungeonMind code, infer success from a head
endpoint, or automatically rebase/retry.

## Rejected alternatives

- Adding a write route to the read-only Mind Turn app.
- Sending `FinalizedReviewPublicationCommand` over HTTP.
- Accepting caller timestamps, operation IDs, expected parents, confirmations,
  graph payloads, or other authority fields.
- Returning 201 for fresh publication and 200 for replay.
- Adding `replayed`, `recovered`, `head_revision_id`, or transport diagnostics.
- Checking current-head equality to decide publication success.
- Adding a GET polling endpoint, pending lifecycle, attempts, workers, queues,
  leases, or automatic retries.
- Installing browser CORS or creating a browser write surface.
- Introducing production OAuth/OIDC/session identity architecture here.
- Adopting a product repository or adding D&D mechanics/resource binding.

## Proof obligations

The transport slice proves strict request validation, digest-based access
binding, sanitized error envelopes, no CORS, OpenAPI separation, server-owned
time, exact replay, same-review convergence, different-review CAS behavior,
response-loss recovery, descendant/rollback replay, readiness, and a real
loopback run of the dependency-free client. PostgreSQL remains the authority for
the integration proofs; no migration or B.2f-c adapter change is part of this
decision.
