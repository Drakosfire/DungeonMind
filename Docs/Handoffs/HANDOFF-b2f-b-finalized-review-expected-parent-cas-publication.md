# HANDOFF — B.2f-b Finalized-review Expected-parent CAS Publication

**Created:** 2026-08-03  
**Status:** ACTIVE — dispatch exactly one implementation capability  
**Repository:** `Drakosfire/DungeonMind`  
**Suggested branch:** `founding/pr-b2f-b-finalized-review-expected-parent-cas-publication`  
**Implementation base:** `8a955881603b2c5798b41825b461340367d3368e`  
**Predecessor:** merged PR #12 — B.2f-a finalized-review graph payload materializer  
**Parent decisions:** ADR-0007 and ADR-0009  
**Decision:** `Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md`  
**Named successor:** B.2f-c durable publication identity and uncertain-outcome recovery

## §0 Capability decomposition

B.2f-a produces one deterministic, validated next graph payload but deliberately
performs no repository work. This slice owns only the first authoritative
graph-head mutation from one already-finalized review:

```text
B.2f-b  load durable finalized review + exact-parent CAS publication
B.2f-c  durable publication identity + exact replay + uncertain-outcome recovery
B.2f-d  service transport + external consumer contract
```

Include only:

- loading one exact durable review by `(world_id, review_id)`;
- rejecting caller-supplied review state, materialization, payload, parent, or
  operation identity;
- observing the current head and requiring the exact finalized-review parent;
- loading that exact parent and invoking B.2f-a;
- constructing one existing `PublishRevisionCommand`;
- publishing through the existing `WorldGraphRepository.publish_revision`;
- returning one ephemeral review-to-revision binding after envelope validation.

Reject second confirmation, retry recovery, durable publication identity,
transport, identity-ledger append, graph-contract changes, adapter work,
migrations, replan/rebase, and product adoption.

## §1 Mission and merge-ready invariant

A trusted kernel caller can publish one exact durable finalized review so that its deterministic B.2f-a payload becomes one immutable child revision and the world head advances atomically only from the review’s pinned parent.

Merge-ready invariant:

```text
exact world_id + review_id
→ load one durable finalized ContributionReviewState
→ current head == review.expected_parent_revision_id
→ load that exact StoredGraphRevision
→ B.2f-a materialization
→ PublishRevisionCommand with:
     parent == expected_parent == review parent
     operation_ids == [review.operation_id]
     schema/payload == materialization result
→ atomic WorldGraphRepository CAS
→ one exact FinalizedReviewPublication result
```

The published revision is the content-addressed revision implied by:

```text
world_id
+ expected parent revision ID
+ ordered operation IDs [review.operation_id]
+ dm_union_graph_v3
+ B.2f-a materialized payload SHA-256
```

A missing review, invalid durable review, absent head, changed head,
missing/corrupt parent, materialization failure, CAS race, immutable revision
conflict, repository integrity failure, or returned-envelope mismatch must
never trigger silent replanning, parent substitution, operation-ID
substitution, a second publication attempt, a post-commit read, or a success
result.

Primary fixture result:

```text
World:                 world:synthetic-gatewatch
Review:                review:cff0162637b428e634e8cccaa9958dc2
Review operation:      reviewop:11111111111111111111111111111111
Reviewed contribution: contrib:65cdb14d13c40e5b8725fd5111509854
Confirmation:          confirm:fa0d200c9922caf3c7e925b320cf9dae
Expected parent:       rev:f2d5164c176289c5f3df7e68b4f0e46d
Materialized payload:  75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
Published revision:    rev:6e02bd224f6b5616534f10026c8b9679
```

The revision ID is independent of `created_at`; the returned envelope must
preserve the exact caller-supplied `published_at` as `created_at`.

## §2 Authority and repository-state gate

Authority precedence is the checked-in repository state, ADRs, architecture,
contracts, repository ports, and this handoff. The implementation base is
`8a955881603b2c5798b41825b461340367d3368e`. Before editing, verify the base
against `origin/main` and stop if another PR owns finalized-review publication,
review-to-revision mapping, publication replay, uncertain-outcome recovery, or
second confirmation.

The publication store is the existing `WorldGraphRepository` port and its
memory/PostgreSQL adapters. The exact input authority is one finalized review
loaded from `ContributionReviewRepository.get(world_id, review_id)`. A
finalized review is governance authority but is not graph truth until
publication. `WorldGraphRepository.publish_revision` owns immutable revision
insert plus head CAS. `compute_revision_id` preserves ordered operation IDs;
B.2f-b supplies exactly `[review.operation_id]`.

No code under `src/dungeonmind` may import `dungeonmind_dnd`.

## §3 Application contract

Create this application seam:

```python
publish_finalized_review(
    world_id: str,
    review_id: str,
    *,
    published_at: datetime,
    review_repository: ContributionReviewRepository,
    world_graph_repository: WorldGraphRepository,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewPublication
```

The flow is:

```text
world_id + review_id
→ review_repository.get(world_id, review_id)
→ reload/cross-validate durable ContributionReviewState
→ head = world_graph_repository.get_head(world_id)
→ require head == review.plan_ref.expected_parent_revision_id
→ parent = world_graph_repository.get_revision(world_id, expected_parent)
→ materialize_finalized_review(review, parent, graph_reader)
→ construct exact PublishRevisionCommand
→ compute expected revision ID
→ world_graph_repository.publish_revision(command)
→ verify returned envelope
→ FinalizedReviewPublication
```

`ContributionReviewNotFoundError` uses code
`contribution_review_not_found` and may expose only `world_id` and `review_id`.
Invalid state returned by a repository is a sanitized
`PersistenceIntegrityError` with reason `finalized_review_reload_validation`.
Repository availability failures propagate without a recovery claim.

The command mapping is exact:

| Field | Source |
| --- | --- |
| `world_id` | durable review record, equal to requested world |
| `parent_revision_id` | `record.plan_ref.expected_parent_revision_id` |
| `expected_parent_revision_id` | same exact parent ID |
| `operation_ids` | `[record.operation_id]` |
| `graph_schema` | B.2f-a materialization |
| `graph_payload` | fresh B.2f-a payload copy |
| `created_at` | caller `published_at` |

The result is an internal frozen dataclass with exactly:

```python
@dataclass(frozen=True)
class FinalizedReviewPublication:
    world_id: str
    review_id: str
    reviewed_contribution_id: str
    review_intent_sha256: str
    confirmation_id: str
    operation_id: str
    expected_parent_revision_id: str
    published_revision_id: str
    graph_schema: str
    graph_payload_sha256: str
    published_at: datetime
```

It contains no graph payload and is not persisted.

The early head read is only a preflight. The CAS remains authoritative. After
`publish_revision` returns, validate only its returned envelope and return.
Do not call `get_head`, `get_revision`, `review_repository.get`, or any
revision-history query after the commit point. Do not retry after any adapter
exception. Immediate replay after known success is stale, not success. An
explicit rollback to the exact parent may republish the same existing
content-addressed revision.

## §4 Failure and adversarial paths

Required outcomes:

| Path | Required outcome |
| --- | --- |
| missing review | typed `ContributionReviewNotFoundError`, no graph write |
| invalid stored review | sanitized `PersistenceIntegrityError`, no graph write |
| missing head | existing `HeadNotFoundError`, no materialization |
| stale preflight | existing `StaleParentRevisionError`, no parent read or write |
| missing parent | existing `RevisionNotFoundError`, no write |
| materialization failure | typed B.2f-a failure, zero publish calls |
| CAS race | typed `StaleParentRevisionError`, no stale child |
| returned envelope mismatch | sanitized `PersistenceIntegrityError`, no retry/read |
| adapter availability/unknown outcome | propagate, no recovery or success inference |
| immediate replay | stale failure, no “already published” result |

No path may replan against a newer head, substitute a parent, accept caller
state, append identity decisions, mutate review/contribution state, or issue a
second graph transaction.

## §5 Strict changed-path allowlist

```text
src/dungeonmind/application/review_publication.py
src/dungeonmind/application/__init__.py
src/dungeonmind/domain/errors.py
tests/conformance/test_review_publication.py
tests/integration/test_postgres_review_publication.py
Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md
Docs/Handoffs/HANDOFF-b2f-b-finalized-review-expected-parent-cas-publication.md
Docs/Roadmaps/ROADMAP.md
README.md
```

No other path is authorized. In particular, do not modify contracts,
repository ports, memory adapters, PostgreSQL adapters, migrations,
`src/dungeonmind/domain/__init__.py`, `src/dungeonmind_dnd`, or integration
fixture plumbing.

## §6 Explicitly false after this slice

No B.2f-b path:

- accepts caller-supplied review state, contribution, materialization, payload,
  parent override, operation ID, command, or capability object;
- creates or edits a review;
- asks for a second confirmation or capability policy;
- replans candidates or changes identity verdicts;
- materializes against any parent other than the finalized review's exact
  parent;
- retries publication automatically;
- treats stale head as “already published”;
- searches revision history to infer an uncertain outcome;
- persists a publication operation, receipt, or review-to-revision mapping;
- appends `IdentityDecisionRecord` rows;
- changes contribution/review lifecycle state;
- exposes API, CLI, agent, UI, or consumer contracts;
- imports `dungeonmind_dnd` from the kernel;
- changes `dm_union_graph_v3`, graph contracts, repository ports, adapters, or
  migrations.

## §7 Required proof

The in-memory owning-boundary suite must prove exact fixture publication,
durable-review-only authority, missing-review rejection, review
byte-equivalence, exact command mapping, known stale preflight,
write-free materialization failure, CAS race, concurrent same-review
one-winner/one-stale behavior, immediate stale replay, rollback replay,
returned-envelope integrity, no post-commit reads, and unknown-outcome
propagation without retry.

The PostgreSQL suite must use the existing migrations and adapters, separate
repository/database instances for race callers, and prove exact Tripod
publication, exact stored payload/digest, caller timestamp preservation,
review byte-equivalence, immediate stale replay, and two finalized reviews
pinned to one parent producing one CAS winner and one stale loser.

Sanitized error assertions must exclude sentinel labels, summaries, locators,
source prose, malformed payloads, and raw model errors from message, repr,
details, and formatted chained traceback at new wrapping boundaries.

## §8 Verification commands

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

If a required command fails on the base, run the same command on the head,
record the exact baseline failure, and do not call the gate green.

## §9 Documentation requirements

ADR-0010 must record the finalized review as authority, identifier-only input,
exact command mapping with singleton operation ID, early preflight versus CAS,
the sole commit point, immediate stale replay, no post-commit reads, and
B.2f-c ownership of durable identity and recovery. It must reject caller state,
second confirmation, auto-replan, history inference, and combined recovery or
transport.

The roadmap must show:

```text
durable finalized review ID
+ exact current parent
+ B.2f-a materialization
→ one PublishRevisionCommand
→ atomic expected-parent CAS
→ immutable child revision + advanced head
→ ephemeral review/revision binding
```

README must state that DungeonMind can publish one already-finalized review
through the existing graph repository CAS, but still lacks durable publication
operation/recovery and a public write surface.

## §10 Required implementation handback

The final handback must include the exact branch, base SHA, head SHA, and PR
URL; this §1 mission and invariant copied exactly; the complete changed-path
list; exact fixture identities and published revision; singleton command
mapping evidence; in-memory success/stale/race/replay/rollback/fake-envelope
results; PostgreSQL exact/concurrency results with separate connections;
byte-equivalent review proof; no-post-commit-read proof; full command results,
pass counts, and CI run; baseline failures or an explicit statement that none
existed; and the still-false B.2f-c/B.2f-d/identity-append/external-adoption
list.

Do not claim idempotent publication, exactly-once execution across an unknown
outcome, response-loss recovery, a durable review-to-revision receipt, a public
write API, publication-time capability evaluation, or identity-ledger
completeness.

## §11 Nano-commit recommendation

Keep the implementation reviewable as:

```text
feat: add durable-review CAS publication
test: prove finalized-review publication and stale races
docs: record B.2f-b publication boundary
```

Do not combine adapter cleanup, schema work, unrelated test refactors, or
B.2f-c scaffolding.

## Implementation handback

- Branch: `founding/pr-b2f-b-finalized-review-expected-parent-cas-publication`
- Base SHA: `8a955881603b2c5798b41825b461340367d3368e`
- Implementation head before this handback-only documentation commit:
  `ab28e82c22b8191dc8034afec0b0671a593e5c5d`
- Pull request: https://github.com/Drakosfire/DungeonMind/pull/13

The mission and merge-ready invariant are:

> A trusted kernel caller can publish one exact durable finalized review so that
> its deterministic B.2f-a payload becomes one immutable child revision and the
> world head advances atomically only from the review’s pinned parent.

```text
exact world_id + review_id
→ load one durable finalized ContributionReviewState
→ current head == review.expected_parent_revision_id
→ load that exact StoredGraphRevision
→ B.2f-a materialization
→ PublishRevisionCommand with:
     parent == expected_parent == review parent
     operation_ids == [review.operation_id]
     schema/payload == materialization result
→ atomic WorldGraphRepository CAS
→ one exact FinalizedReviewPublication result
```

Primary fixture proof:

```text
world_id:                 world:synthetic-gatewatch
review_id:                review:cff0162637b428e634e8cccaa9958dc2
operation_id:             reviewop:11111111111111111111111111111111
reviewed_contribution_id: contrib:65cdb14d13c40e5b8725fd5111509854
confirmation_id:          confirm:fa0d200c9922caf3c7e925b320cf9dae
parent_revision_id:       rev:f2d5164c176289c5f3df7e68b4f0e46d
graph_payload_sha256:     75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
published_revision_id:    rev:6e02bd224f6b5616534f10026c8b9679
```

Command mapping is exact: `operation_ids == [record.operation_id]`, with
`parent_revision_id == expected_parent_revision_id == record.plan_ref.expected_parent_revision_id`,
`graph_schema == "dm_union_graph_v3"`, the fresh B.2f-a payload, and
`created_at == published_at`. The returned envelope is checked before creating
the ephemeral result.

In-memory owning-boundary results:

- `tests/conformance/test_review_publication.py`: 15 passed.
- Exact publication stored the expected payload and revision, advanced the
  head, and preserved the durable review byte-for-byte.
- Missing, corrupt, stale, missing-head, missing-parent, materialization,
  CAS-race, immediate-replay, mismatched-envelope, and unknown-outcome paths
  were exercised without fallback or a second publish.
- Same-review concurrency produced exactly one success and one stale loser.
- Explicit rollback replayed the same content-addressed revision.
- Success and envelope-failure spies proved one head read, one parent read,
  one `publish_revision` call, and no post-commit repository read.

PostgreSQL owning-boundary results:

- The integration job passed exact Tripod publication, immediate stale replay,
  and two independently connected callers racing reviews pinned to one parent.
- The race uses separate `PostgresRepositoryBundle` instances and therefore
  separate database connections/transactions.
- CI run
  [30870007389](https://github.com/Drakosfire/DungeonMind/actions/runs/30870007389)
  passed both [core](https://github.com/Drakosfire/DungeonMind/actions/runs/30870007389/job/91869890666)
  and [integration](https://github.com/Drakosfire/DungeonMind/actions/runs/30870007389/job/91869890689).

Verification:

```text
uv run pytest -q tests/conformance/test_review_publication.py          15 passed
uv run pytest -q tests/conformance/test_review_materialization.py      21 passed
uv run pytest -q tests/conformance/test_review_materialization_characterization.py
                                                                        18 passed
uv run pytest -q -m 'not integration'                                  552 passed
uv run ruff check .                                                     passed
uv run pyright                                                          0 errors
git diff --check                                                        passed
```

The local PostgreSQL command was attempted with the specified DSN but could
not start migration because `localhost:54329` refused the connection; Docker
was unavailable because no daemon was running. This is an environment
baseline limitation, not a claimed integration result. The first PR core
check also exposed that the new integration module imported optional `psycopg`
during non-integration collection; runtime-only PostgreSQL imports fixed that
regression, and the final CI run above is green.

Changed paths are exactly the §5 allowlist:

```text
src/dungeonmind/application/review_publication.py
src/dungeonmind/application/__init__.py
src/dungeonmind/domain/errors.py
tests/conformance/test_review_publication.py
tests/integration/test_postgres_review_publication.py
Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md
Docs/Handoffs/HANDOFF-b2f-b-finalized-review-expected-parent-cas-publication.md
Docs/Roadmaps/ROADMAP.md
README.md
```

Still false after B.2f-b: durable publication identity, exact retry-as-success,
uncertain-outcome recovery, publication receipts, public API/CLI/agent/UI
transport, publication-time capability evaluation, global identity-decision
append, contribution/review lifecycle mutation, and DungeonBuddy/product
adoption. B.2f-c owns durable mapping, exact replay, and recovery; B.2f-d owns
external write surfaces.
