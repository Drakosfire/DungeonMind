# HANDOFF — B.2f-c Durable Finalized-review Publication Identity and Recovery

**Created:** 2026-08-03  
**Status:** IMPLEMENTED — awaiting review  
**Repository:** `Drakosfire/DungeonMind`  
**Suggested branch:** `founding/pr-b2f-c-durable-finalized-review-publication-recovery`  
**Implementation base:** `dab32722cccece620942af75d42a5f7876b14509`  
**Predecessor:** merged PR #13 — B.2f-b expected-parent CAS publication  
**Parent decisions:** ADR-0007, ADR-0009, ADR-0010  
**Decision:** `Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md`  
**Named successor:** B.2f-d transport and external consumer contract

## §0 Mission and decomposition

Promote the successful B.2f-b review-to-revision binding into one terminal
durable publication record written atomically with the graph revision and head
transition, so exact retries and uncertain outcomes resolve to the original
publication without replanning, rematerializing a completed operation,
requiring the published revision to remain the current head, or introducing a
pending-job lifecycle, worker, transport, identity-ledger append, or product
adoption.

Included:

- versioned `FinalizedReviewPublication` and internal publication command;
- one atomic publication repository port;
- in-memory and PostgreSQL unit-of-work adapters;
- exact replay by review/operation identity;
- bounded adoption of the exact deterministic B.2f-b revision;
- one recovery probe after a thrown publication attempt;
- sanitized outcome-unknown failure when recovery is unavailable;
- migration, conformance, integration, architecture, ADR, roadmap, and README
  updates.

Explicitly excluded:

- pending/running/failed/retrying records, attempts, leases, workers, queues,
  schedulers, retries, or outboxes;
- arbitrary history scans, fuzzy success inference, replan/rebase, or
  rematerialization of a completed record;
- current-head restoration or republish after rollback;
- review/contribution lifecycle mutation, identity-ledger append, second
  confirmation, authorization changes, transport, or product adoption.

## §1 Merge-ready invariant

```text
world_id + review_id
→ exact durable publication record already exists
     → reconstruct and cross-verify its review + revision
     → return the original record without materialization or graph mutation

or

world_id + review_id
→ load exact durable finalized review
→ load exact pinned parent
→ B.2f-a materialization
→ deterministic expected revision identity
→ atomic publication repository:
     reconcile exact existing publication/revision
     or require current head == review parent
     and commit revision + head + publication record together
→ return one durable FinalizedReviewPublication
```

The same review operation has zero or one terminal publication record and one
published revision identity. A changed retry timestamp never changes the
original record. A completed publication remains completed after descendants or
explicit rollback.

## §2 Primary fixture binding

```text
world_id:                       world:synthetic-gatewatch
review_id:                      review:cff0162637b428e634e8cccaa9958dc2
reviewed_contribution_id:       contrib:65cdb14d13c40e5b8725fd5111509854
review_intent_sha256:           0a3cdd6f704a22a5d954c028b20c17220074442bfb2c70e1367afda3493174ce
confirmation_id:                confirm:fa0d200c9922caf3c7e925b320cf9dae
operation_id:                   reviewop:11111111111111111111111111111111
expected_parent_revision_id:    rev:f2d5164c176289c5f3df7e68b4f0e46d
published_revision_id:           rev:6e02bd224f6b5616534f10026c8b9679
graph_payload_sha256:            75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
published_at:                   2026-08-03T23:00:00Z
publication_sha256:             3e7a632142c41066d3866c8682290fdc8e57b8f08b3324689c2964f6b045958c
```

The durable record schema is
`dm_finalized_review_publication_v1`, with terminal `status="published"`.
It contains no mutable status, retry counter, error, worker, or transport
fields.

## §3 Application and repository boundaries

`publish_finalized_review` accepts only identifiers, timestamp, existing
review/graph/publication ports, and a graph reader. It performs:

```text
publication_repository.get_for_review(world_id, review_id)
→ exact record: return it immediately
→ no record: review reload → exact parent read → B.2f-a → one command
→ publication_repository.publish(command)
→ one exact recovery probe only if publish throws
```

The application no longer reads the current head or calls
`WorldGraphRepository.publish_revision` directly. The publication repository
cross-verifies the finalized review before graph mutation and owns revision
insert, head CAS, head event, and record persistence in one unit of work.

## §4 Failure contract

- Missing review: `ContributionReviewNotFoundError`.
- Invalid review/record/revision: sanitized `PersistenceIntegrityError`.
- Stale current head: `StaleParentRevisionError`, with no child or record.
- Existing exact revision without record: bounded record adoption, no head event.
- Known typed publication failure without a record: re-raise the typed failure.
- Unexpected or unavailable publication/recovery failure:
  `FinalizedReviewPublicationOutcomeUnknownError` containing only safe retry
  identity and `retry_safe=true`.
- Exact replay after any known/unknown committed outcome returns the original
  record before review, parent, reader, head, or graph mutation.

## §5 Strict changed-path allowlist

```text
src/dungeonmind/contracts/review_publication.py
src/dungeonmind/contracts/__init__.py
src/dungeonmind/application/repositories.py
src/dungeonmind/application/review_publication.py
src/dungeonmind/application/__init__.py
src/dungeonmind/domain/errors.py
src/dungeonmind/infrastructure/memory/repositories.py
src/dungeonmind/infrastructure/memory/__init__.py
src/dungeonmind/infrastructure/postgres/review_publication.py
src/dungeonmind/infrastructure/postgres/graph.py
src/dungeonmind/infrastructure/postgres/__init__.py
migrations/versions/0003_finalized_review_publications.py
tests/conformance/test_review_publication.py
tests/integration/test_postgres_review_publication.py
tests/integration/conftest.py
tests/integration/test_migrations.py
Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md
Docs/Handoffs/HANDOFF-b2f-c-durable-finalized-review-publication-recovery.md
Docs/Architecture/ARCHITECTURE.md
Docs/Architecture/AUTHORITY.md
Docs/Roadmaps/ROADMAP.md
README.md
```

No transport, API, CLI, agent, UI, profile, graph-schema, identity-ledger, or
product-surface path is authorized.

## §6 Verification commands

```bash
uv run pytest -q tests/conformance/test_review_publication.py
uv run pytest -q tests/conformance/test_review_materialization.py
uv run pytest -q tests/conformance/test_review_materialization_characterization.py
uv run pytest -q -m 'not integration'

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -q tests/integration/test_postgres_review_publication.py -o addopts=''

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -q -m integration -o addopts=''

uv run ruff check .
uv run pyright
git diff --check
```

## Implementation handback

- Branch: `founding/pr-b2f-c-durable-finalized-review-publication-recovery`
- Base SHA: `dab32722cccece620942af75d42a5f7876b14509`
- Implementation head: working tree; no commit created by this handoff
- Pull request: pending
- CI run: pending

Implemented proof and source changes include:

- versioned command/publication contracts with strict digest, timestamp,
  revision-identity, and extra-field validation;
- application durable-first replay and one sanitized response-loss probe;
- shared in-memory `RLock` and PostgreSQL transaction-local graph publication
  helpers;
- atomic publication adapters with review, parent, revision, record, and
  command cross-verification;
- world-scoped in-memory rollback that cannot erase another world's concurrent
  graph/head/publication state, with a deterministic cross-world regression;
- exact predecessor adoption without head mutation, same-review replay, and
  expected-parent CAS preservation for different reviews;
- `0003_finalized_review_pubs` migration and architecture/authority
  documentation.

Verification completed:

- `uv run pytest -q tests/conformance/test_review_publication.py` — 20 passed;
- `uv run pytest -q -m 'not integration'` — passed;
- `uv run ruff check .` — passed;
- `uv run pyright` — 0 errors, 0 warnings;
- `uv run alembic heads` — `0003_finalized_review_pubs`;
- `git diff --check` — passed.

PostgreSQL integration tests were collected successfully but could not run in
this environment because `localhost:54329` refused the connection and the
Docker daemon was unavailable.

This handback records the exact pass counts, migration result, PostgreSQL
environment limitation, response-loss and adoption proofs, changed-path
allowlist, and still-false B.2f-d transport, identity-ledger, and
external-adoption capabilities. It does not claim transport, pending jobs,
exactly-once execution beyond the terminal record, or current-head authority.
