# HANDOFF — B.2e Finalized Contribution Review Adoption

**Status:** ACTIVE — one-shot finalized review capability
**Created:** 2026-08-01
**Implementation base:** `1a4ee973725d51a188da1b1a7a67a987c85266fe`
**Predecessor:** merged PR #9 — B.2d pinned Threat create-or-connect plan
**Suggested branch:** `founding/pr-b2e-finalized-contribution-review-adoption`

## Mission

Given one ready, content-bound B.2d plan, complete GM assertion and identity
verdicts, an exact confirmation receipt, and a matching `confirm_commit`
policy, atomically persist a reloadable finalized review bundle:

```text
ready B.2d plan
+ complete GM verdicts
+ exact receipt and GM commit policy
→ superseded candidate contribution
→ active reviewed successor contribution
→ finalized review record
```

Exact replay returns byte-equivalent state. A changed payload for one operation
is an idempotency conflict; a second review for one source plan is already
finalized. Every read reconstructs and cross-verifies the record, both
contributions, evidence references, IDs, and fingerprints.

## Included boundary

- Generic versioned review contracts under `src/dungeonmind/contracts`.
- A repository-blind D&D adapter from ready plan to generic intent.
- Explicit `confirm_commit` capability evaluation with exact GM
  world/campaign/revision scope.
- Content-bound `CommitConfirmationReceipt`.
- Current-head and exact-parent preflight.
- Deterministic superseded candidate and active `graph_review` successor.
- Complete accepted/rejected assertion verdicts and candidate identity verdicts.
- Atomic in-memory and PostgreSQL review repositories.
- One Alembic migration for `dungeonmind.contribution_reviews`.
- Exact fixtures and unit/integration proof.

## Explicit non-goals

B.2e does not add mutable drafts, partial saves, cancellation, retraction,
review replacement, target override, fuzzy identity, relationship-evidence
augmentation, API/UI/CLI/agent tooling, graph materialization, publication,
head CAS, or global `IdentityDecisionRecord` append. B.2f owns accepted
materialization and expected-parent publication CAS.

The D&D adapter owns only translation and validation. The kernel service
accepts generic contracts and never imports or parses D&D plan contracts.

## Durable-state rules

The candidate contribution keeps its ID and assertion payload and changes only
`active` → `superseded`. The reviewed successor has a deterministic new ID,
`source_kind=graph_review`, `status=active`, and
`supersedes_contribution_id` pointing to the candidate. Assertion IDs, content,
evidence, source anchors, and endpoints remain unchanged; only acceptance and
node identity outcomes become final. Relationship identity outcomes remain
null. No identity-decision IDs, diagnostics, unresolved mentions, graph
payloads, or publication receipts are stored.

`reject_candidate` rejects every dependent node and relationship assertion.
`create_new` requires an accepted label. An accepted relationship cannot use a
rejected candidate endpoint. All assertions may be rejected; the result
remains a finalized review and B.2f must define any later zero-accepted
publication behavior.

## Files

Key additions:

- `src/dungeonmind/contracts/contribution_review.py`
- `src/dungeonmind/application/contribution_review.py`
- `src/dungeonmind_dnd/application/contribution_review.py`
- `migrations/versions/0002_contribution_reviews.py`
- review fixtures under `tests/fixtures/contribution_reviews/` and
  `tests/fixtures/dungeonmind_dnd/`
- focused contract, service, memory, adapter, and PostgreSQL tests

Existing contribution, identity, graph, B.2d plan, vocabulary, profile
descriptor, lockfile, and graph-publication contracts remain unchanged.

## Verification

```bash
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
uv run alembic heads
DUNGEONMIND_DATABASE_URL=postgresql://... uv run pytest -m integration \
  tests/integration/test_postgres_contribution_review_repository.py
```

Also prove:

- kernel import never loads `dungeonmind_dnd`;
- D&D review adapter loads no optional provider/database dependencies;
- graph head, graph revisions, and identity-decision rows are unchanged;
- no publication command or identity-decision repository is used by the review
  service;
- wheel contains the generic kernel and D&D adapter modules.

## Named successors

- **B.2e.1:** mutable review workspace and explicit replacement lifecycle.
- **B.2f:** accepted contribution materialization and atomic expected-parent
  graph publication.
- **B.3:** Threat mechanics-resource binding after published identity.
