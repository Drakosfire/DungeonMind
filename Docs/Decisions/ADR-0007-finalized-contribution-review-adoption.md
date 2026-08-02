# ADR-0007 — Finalized contribution review adoption

**Status:** Accepted (PR B.2e)
**Date:** 2026-08-01
**Deciders:** B.2e implementation dispatch
**Extends:** ADR-0006 (pinned profile contribution planning)

## Decision

B.2e is a one-shot finalized review capability. A ready B.2d plan is translated
by the D&D package into a generic `ContributionReviewIntent`. A durable commit
requires:

- a complete accepted/rejected verdict for every candidate assertion;
- one identity verdict for every planned candidate, with no target override;
- a `confirm_commit` capability policy with GM admissibility and exact
  world/campaign/revision scope; and
- a `CommitConfirmationReceipt` bound to the exact intent digest, reviewer,
  expected parent, and review time.

The kernel preflights the current head against the pinned expected parent and
verifies the exact parent revision envelope. It then atomically stores:

1. the original candidate contribution with `status=superseded`;
2. a deterministic active `graph_review` successor whose assertions preserve
   the candidate IDs, content, evidence, and source anchors while changing only
   final acceptance and node identity outcomes; and
3. a finalized review record containing provenance, receipt identity, complete
   verdicts, reviewer, timestamps, and contribution digests.

The review repository is idempotent for an exact replay, rejects a changed
payload for the same operation, and allows only one finalized review for a
source plan. Reads reconstruct and cross-verify all three records and their
fingerprints. In-memory and PostgreSQL adapters implement the same port.

Review verdicts are durable governance facts, not graph truth. B.2e does not
append `IdentityDecisionRecord`, materialize a graph payload, construct a
`PublishRevisionCommand`, advance a graph head, or expose a review API/UI/tool.
B.2f remains responsible for accepted-assertion materialization and atomic
expected-parent publication.

## Rejected alternatives

- Mutating the candidate contribution in place.
- Persisting verdicts only in diagnostics or a mutable draft session.
- Treating identity verdicts as fake merge/alias decision records.
- Allowing a profile package to access repositories or capability policy.
- Accepting partial verdict sets, player-scoped policy, or an unpinned commit.
- Combining review persistence with graph publication.
- Adding cancellation, re-review, target override, relationship-evidence
  augmentation, or product/API surfaces.

## Authority

The source plan reference and digest bind what was reviewed; the candidate
contribution binds proposed claim bytes; assertion and identity verdicts bind
reviewer disposition; the capability policy and receipt bind commit authority;
and the expected parent binds review context. A finalized review is
publication-eligible input, not canonical graph truth. Only a published graph
revision is graph authority.
