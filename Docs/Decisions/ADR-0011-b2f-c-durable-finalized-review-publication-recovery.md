# ADR-0011 — B.2f-c durable finalized-review publication and recovery

**Status:** Accepted (B.2f-c)  
**Date:** 2026-08-03  
**Deciders:** B.2f-c implementation dispatch  
**Extends:** ADR-0007, ADR-0009, and ADR-0010

## Decision

B.2f-c promotes the successful B.2f-b review-to-revision binding into one
versioned terminal `dm_finalized_review_publication_v1` record. The record is
written atomically with the immutable graph revision and world-head CAS by a
new `FinalizedReviewPublicationRepository` unit of work.

The application seam first asks that repository for `(world_id, review_id)`.
When a record exists, the repository reconstructs and cross-verifies the
finalized review and immutable revision, and the application returns that
original record without loading the review, parent, reader, or current head.
When no record exists, the application loads the exact finalized review and
parent, invokes B.2f-a once, builds one
`dm_finalized_review_publication_command_v1`, and invokes the publication
repository once.

The repository:

1. cross-verifies the command against the exact durable finalized review;
2. returns an exact existing publication record without mutation;
3. adopts only the exact deterministic B.2f-b revision when it exists without
   a record, preserving that revision's original `created_at` and current
   head;
4. otherwise requires the pinned parent to remain the current head and commits
   the revision, head transition, head event, and terminal publication record in
   one transaction/unit of work.

The record is historical publication identity, not current-head state. Later
descendants and explicit rollback do not invalidate it. Exact replay ignores a
new requested timestamp and returns the original `published_at`; it never
rematerializes or republishes a completed operation.

## Recovery boundary

The application performs one exact `get_for_review` recovery probe after a
publication repository call raises. A recovered record is success. A known
typed non-availability failure with no record is re-raised. An unexpected or
availability failure with no usable recovery probe becomes the sanitized
`finalized_review_publication_outcome_unknown` error with `retry_safe=true`.
No failed, pending, running, retrying, lease, worker, queue, or attempt record
is persisted.

## Authority

- The finalized review remains governance authority for the reviewed intent,
  verdicts, confirmation, operation, and expected parent.
- The immutable published graph revision remains graph truth.
- The publication record is durable correspondence and commit receipt between
  those two authorities.
- The current world head is current graph authority, never proof that a
  historical publication did or did not occur.

## Rejected alternatives

- Writing the publication record after graph publication.
- Writing the record before graph publication.
- Requiring the published revision to remain the current head.
- Rematerializing or scanning arbitrary history during replay/recovery.
- Republish-after-rollback once a terminal record exists.
- Pending lifecycle, worker, queue, lease, retry scheduler, or outbox.
- Review/contribution lifecycle mutation or identity-ledger append.
- Second confirmation, publication-time capability evaluation, or transport.

## Proof obligations

The owning suites prove the primary Tripod Null-Calf record and canonical
fingerprint, durable-first replay with a broken reader, timestamp preservation,
same-review idempotent concurrency, different-review CAS authority, rollback
and descendant history, bounded predecessor adoption, atomic rollback on
injected failure, response-loss recovery, sanitized unknown outcome, complete
record/revision reconstruction, and PostgreSQL migration/table constraints.
