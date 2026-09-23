---
pr_body_template: |
  ## Handoff pointer
  - Repository: Drakosfire/DungeonMind
  - Direction: DESIGN → CODE
  - Roadmap slice: V5.3 — durable publication replay / recovery
  - Handoff: Docs/Handoffs/HANDOFF-v5-3-durable-publication-replay-recovery.md
  - Predecessor: PR #71 — KERNEL: V5.2 native expected-parent CAS publication

  The checked-in handoff, cumulative diff, nano commits, and independently
  rerun verification are the review contract. The PR description is transport
  metadata only.
---

# HANDOFF — V5.3 durable publication replay and recovery

**Created:** 2026-09-22
**Status:** ACTIVE — Review Cycle 2 HOLD repair on exact head `103651aa870eb51dc7a97955f0d5d9ff5add6c40`
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-v5-3-durable-publication-replay-recovery.md`
**Repository:** `Drakosfire/DungeonMind`
**Roadmap phase:** `V5.3`
**Suggested branch:** `kernel/v5-3-durable-publication-replay-recovery`
**Suggested PR title:** `KERNEL: V5.3 durable publication replay and recovery`
**Predecessor:** PR #71 — `KERNEL: V5.2 native expected-parent CAS publication`
**Predecessor status:** ACCEPTED / merged
**Accepted PR #71 head:** `a8f78cf079c34e148badde95a346cee9befc2549`
**Accepted substantive runtime:** `78cb341b6fb3f1f7ab05a4d4d1a8770ce64bd089`
**Merged DungeonMind main:** `01762848cbdd666b092d4cb26af558ba1468fa4d`
**Frozen V0 aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`
**Named successor:** `V5.4 — prospective-reference identity allocation + substitution`

> **Dispatch gate:** Do not dispatch from the currently observed PR #71 head. PR #71 must first receive final Steward acceptance, merge, and reconcile with then-current `main`. Before implementation begins, replace predecessor placeholders below with the exact accepted substantive head, final reviewed head, merge SHA, migration head, and final V5.2 contract shape.
>
> If final PR #71 changes the publication port, durable table shape, revision identity, failure semantics, or application entrypoint materially from the assumptions here, stop and reconcile this handoff before coding.

## §1 Mission and merge-ready invariant

**Mission:** A caller can publish one already-governed native-vNext materialization under one stable caller-supplied publication identity and later recover the exact terminal result after retries or a lost response, without republishing, inferring success from the current head, or adding a second recovery authority.

**Merge-ready invariant:** For one `(space_id, publication_id)`, DungeonMind durably binds exactly one publication command to exactly one terminal published revision. Fresh success writes the revision, head transition, publish event, and terminal publication receipt atomically. Exact retries and later recovery return that same verified receipt/revision even after the head has advanced. A changed retry fails closed. An unavailable or ambiguous post-attempt recovery reports outcome-unknown without guessing.

### Pre-dispatch critique

| Question | Answer |
|---|---|
| Can one invariant govern every claimed observable path? | Yes. Every path is governed by one stable publication identity bound to one exact command and one terminal durable result. |
| Most dangerous adversarial sequence? | Commit revision + head + receipt → response fails → descendant advances head → original caller retries/recoveries by publication ID. |
| Does the evidence plan detect it? | Yes. In-memory and PostgreSQL tests inject post-commit response loss and prove receipt-first recovery without head inference or a second publish event. |
| Easiest owning boundary to under-test? | PostgreSQL transactionality: revision/head/event/receipt must commit or roll back together under independent connections. |
| Split trigger? | PR #71 cannot expose one atomic storage boundary capable of including a terminal receipt without redesigning revision persistence, or its final accepted contract materially differs from this design. |

## §2 Context, authority, and boundaries

Read before coding:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
3. `Docs/Roadmaps/ROADMAP.md`
4. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
5. final accepted `Docs/Handoffs/HANDOFF-v5-2-expected-parent-cas-publication.md`
6. final PR #71 Steward acceptance review
7. this handoff
8. `CONTRIBUTING.md`
9. current V5.2 application/repository tests

### Fill before dispatch

```text
PR #71 final accepted head:
  a8f78cf079c34e148badde95a346cee9befc2549

PR #71 accepted substantive runtime head:
  78cb341b6fb3f1f7ab05a4d4d1a8770ce64bd089

PR #71 review cycles:
  3

PR #71 final PASS review:
  Steward Review Cycle 3 — PASS, review 5286826897

PR #71 disposition:
  V5_2_EXPECTED_PARENT_CAS_PUBLICATION_ACCEPTED

PR #71 merge:
  01762848cbdd666b092d4cb26af558ba1468fa4d

branch base for V5.3:
  01762848cbdd666b092d4cb26af558ba1468fa4d

current Alembic head:
  0008_vnext_knowledge_authority
```

At handoff creation, PR #71 is not accepted and its branch predates later `main` changes. Do not branch V5.3 from `4c8e728...`.

### Accepted predecessor contract assumed

V5.2 is expected to provide:

```text
GovernedMaterializationResult
  → exact PublishKnowledgeRevisionCommand
  → immutable native KnowledgeRevision
  → expected-parent CAS
  → KnowledgeHead transition
  → one publish KnowledgeHeadEvent
```

and preserve:

```text
revision identity is deterministic from exact command semantic identity
created_at is durable history, not revision identity
stale parent fails with zero durable authority mutation
revision + head + event are atomic
no retry/recovery promise yet
```

### Cross-repository pressure

WorldKeeper requires a DungeonMind-owned durable publication identity reconstructible from a caller-held prepared ID and usable for exact retry/lost-response recovery.

V5.3 closes only that durable idempotency/recovery half.

V5.3 does not close the WorldKeeper prospective-reference blocker because current vNext materialization still requires already-durable:

```text
Entity.entity_id
Assertion.subject_entity_id
EntityRefValue.entity_id
```

That remains V5.4.

### What remains false after V5.3

```text
no prospective entity references in KnowledgeContribution
no DungeonMind allocation of entity IDs from transaction-local create handles
no substitution of prospective refs into dependent assertions
no prospective/client-op -> durable entity mapping
no DungeonBuddy/WorldKeeper write adoption
no public HTTP transport
no bridge-genesis migration
no legacy World writer cutover
no identity-decision supersession ledger
```

## §3 Observable paths and adversarial sequences

| Path | Current V5.2 | Required V5.3 | Owning boundary |
|---|---|---|---|
| Fresh publication | revision/head/event CAS; response may be ambiguous | atomically add terminal receipt | publication repository transaction |
| Exact retry, same ID + same command | no durable replay contract | return original result; no second event/head mutation | receipt-first replay |
| Same ID + changed command | no idempotency contract | idempotency conflict; zero mutation | repository |
| Retry after head advanced | ordinarily stale | existing receipt wins; historical result returned | replay |
| Lost response after commit | outcome unknown | one exact receipt probe; receipt means success | application + repository |
| Publish/recovery unavailable | unknown | typed outcome-unknown; never infer from head | application |
| Known stale parent, no receipt | typed stale | preserve typed stale and zero receipt | repository |
| Corrupt receipt/revision | n/a | persistence integrity failure | reconstruction/recovery |
| Missing receipt lookup | n/a | exact miss; no head/history inference | recovery read |

Required adversarial sequences:

- publish commits → response throws → recovery probe returns exact success;
- publish A → publish descendant B → retry A → original A receipt, no head rewind;
- same publication ID + same command concurrently → one receipt/result;
- same publication ID + different commands concurrently → one winner, one idempotency conflict;
- different publication IDs + same expected parent concurrently → one CAS winner, one stale loser with no receipt;
- revision insert → injected pre-commit failure → no receipt/revision/head/event;
- commit succeeds → recovery unavailable → outcome_unknown with retry-safe identity;
- outcome_unknown → later same-ID retry → exact receipt if committed, otherwise normal one-time publish;
- receipt exists but exact revision is missing/corrupt → fail closed.

## §4 Files in scope

The exact migration filename is deferred until predecessor merge because PR #71 and current `main` do not yet share one accepted migration head.

| Action | Path | Purpose |
|---|---|---|
| Create | `Docs/Handoffs/HANDOFF-v5-3-durable-publication-replay-recovery.md` | canonical authority |
| Modify | `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md` | record V5.2 acceptance and activate V5.3 |
| Modify | `Docs/Roadmaps/ROADMAP.md` | V5.2 accepted / V5.3 active / V5.4 successor |
| Create | `Docs/Decisions/ADR-0025-vnext-durable-publication-replay-recovery.md` | durable receipt/idempotency decision |
| Create | `src/dungeonmind/contracts/vnext/publication.py` | terminal durable receipt contract |
| Modify | `src/dungeonmind/contracts/vnext/__init__.py` | export if repository convention requires |
| Modify | `src/dungeonmind/application/vnext/publication.py` | receipt-first publish/replay/recovery |
| Modify | `src/dungeonmind/application/vnext/ports.py` | durable publication repository/read capability |
| Modify | `src/dungeonmind/application/vnext/errors.py` | idempotency/integrity/outcome-unknown errors |
| Modify | `src/dungeonmind/application/vnext/__init__.py` | semantic application exports |
| Modify | `src/dungeonmind/infrastructure/memory/vnext_knowledge.py` | atomic receipt + revision/head/event |
| Modify | `src/dungeonmind/infrastructure/postgres/vnext_knowledge.py` | atomic durable receipt + revision/head/event |
| Create | `migrations/versions/<next>_vnext_knowledge_publications.py` | terminal receipt storage |
| Modify | `tests/unit/test_vnext_cas_publication.py` | adapt V5.2 proof where V5.3 intentionally supersedes behavior |
| Create | `tests/unit/test_vnext_publication_recovery.py` | in-memory replay/recovery/adversarial proof |
| Create | `tests/integration/test_postgres_vnext_knowledge_publication_recovery.py` | PG atomicity/concurrency/recovery proof |
| Modify | `tests/integration/test_migrations.py` | migration round-trip |
| Modify if required | `tests/integration/conftest.py` | only if existing fixture cannot exercise the new table |

Bounded discovery exception:

```text
Directory:
  tests/

Maximum additional paths:
  2

Allowed path kinds:
  existing vNext publication test/helper files only

Decision rule:
  only if final accepted PR #71 renamed or split an owning test/helper.
```

Any additional runtime, contract, infrastructure, migration, or documentation path is a stop.

### Review-cycle rebrief — approved test-surface expansion

The implementation discovered that the accepted V5.2 → V5.3 stewardship transition
left stale phase assertions in four existing vNext read-test modules, while the
PostgreSQL publication proof belongs in the existing integration cohort rather
than a newly named recovery module. The Steward rebrief therefore authorizes
these five additional test paths for this PR:

```text
tests/integration/test_postgres_vnext_knowledge_publication.py
tests/unit/test_vnext_entity_reads.py
tests/unit/test_vnext_evidence_reads.py
tests/unit/test_vnext_neighborhood.py
tests/unit/test_vnext_search.py
```

This is a bounded test-only expansion. It does not authorize new runtime,
contract, migration, or V5.4 scope.

## §5 Explicitly out of scope

- `src/dungeonmind/contracts/vnext/contribution.py` — no prospective refs;
- `src/dungeonmind/contracts/vnext/domain.py` — no Entity/Assertion identity change;
- `src/dungeonmind/contracts/vnext/knowledge.py` — frozen V0 contracts unchanged;
- `src/dungeonmind/application/vnext/materialization.py` — V5.1 meaning unchanged;
- legacy `review_publication*` runtime — evidence only;
- DungeonBuddy / WorldKeeper repositories — consumer integration later;
- HTTP/service transport;
- prospective reference allocation/substitution — V5.4;
- receipt backfill/adoption for arbitrary V5.2 history;
- pending/running/retrying jobs, workers, queues, outboxes;
- automatic rebase;
- head-based success inference;
- full history scans;
- performance/storage redesign.

## §6 Implementation contract

### Stable publication identity

Caller supplies one opaque non-blank `publication_id`.

Identity scope:

```text
(space_id, publication_id)
```

DungeonMind does not derive it from product semantics.

A future WorldKeeper caller may use:

```text
publication_id = prepared_change_id
```

or a deterministic namespaced derivative. That derivation remains outside DungeonMind.

`publication_id` is distinct from revision IDs, operation IDs, entity IDs, and assertion IDs.

### Terminal durable receipt

Add one versioned contract equivalent to:

```text
KnowledgePublicationReceipt
  schema_version = dm_knowledge_publication_receipt_v1
  space_id
  publication_id
  command_sha256
  expected_parent_revision_id
  published_revision_id
  graph_payload_sha256
  status = published
```

`command_sha256` is:

```text
canonical_sha256(
  PublishKnowledgeRevisionCommand.model_dump(mode="json")
)
```

It binds space, parent, ordered operation IDs, graph schema/payload, DomainContractRef, SemanticProfileRef, MigrationOriginRef, and created_at.

Do not add generic metadata bags, retry counters, mutable status, product fields, actor fields, or prospective mappings.

A storage-only row fingerprint is allowed for corruption detection; it is not semantic identity.

### Application surface

Preferred conceptual surface:

```text
publish_governed_materialization(
    materialization,
    publication_id,
    repository,
) -> KnowledgePublicationReceipt

get_publication_receipt(
    space_id,
    publication_id,
    repository,
) -> KnowledgePublicationReceipt | None
```

Exact names are implementation latitude.

`get_publication_receipt` must:

1. read only `(space_id, publication_id)`;
2. validate stored receipt/fingerprint;
3. load exact `published_revision_id`;
4. verify revision envelope + payload;
5. reconstruct the exact publish command from durable revision + payload;
6. require reconstructed command digest == receipt command digest;
7. return the receipt.

It must not require that revision to remain current.

It must never infer success from current head, revision existence without receipt, operation IDs, timestamps, payload similarity, or history scans.

### Atomic repository unit

One transaction/lock owns:

```text
publication receipt lookup
command binding check
expected-parent CAS
immutable revision insert/reconciliation
head transition
publish head event
terminal publication receipt insert
```

Fresh success commits:

```text
KnowledgeRevision
KnowledgeHead
KnowledgeHeadEvent(kind=publish)
KnowledgePublicationReceipt
```

Failure commits none.

### Exact replay

Receipt hit + exact command binding:

```text
verify exact stored revision
→ return original receipt
→ no head mutation
→ no new event
→ no revision rewrite
```

Replay happens before current-head CAS.

Same publication ID with changed command:

```text
typed idempotency conflict
zero mutation
```

### Fresh publication

No receipt:

```text
require current head == expected parent
→ preserve V5.2 CAS
→ publish deterministic revision
→ advance head once
→ emit one publish event
→ insert one receipt
→ commit atomically
```

Different publication IDs do not make stale work replayable.

### Existing revision without receipt

Do not infer completed publication merely because the deterministic revision exists.

No receipt adoption/backfill is authorized in V5.3. If real accepted V5.2 durable operations require that migration, stop and rebrief.

### Lost-response recovery

After repository publish throws:

```text
perform one exact get_publication(space_id, publication_id) probe
```

Valid receipt → return success.

No receipt + known deterministic DungeonMind failure whose repository contract guarantees zero commit → re-raise typed failure.

Unavailable/ambiguous attempt or recovery →:

```text
KnowledgePublicationOutcomeUnknownError
  space_id
  publication_id
  expected_published_revision_id
  retry_safe = true
```

Do not automatically republish inside the same call.

A later same-ID retry is the recovery mechanism.

### Commit model

```text
Commit point:
  transaction commit containing receipt + revision/head/event.

Before commit:
  no V5.3 authority change is durable.

After commit:
  terminal receipt is authoritative even if caller received no response.

Post-commit failure:
  exact receipt probe returns success when available;
  otherwise outcome_unknown with the same retry-safe publication identity.
```

## §6A State/fallback matrix

| Path | Success | Miss | Unavailable | Integrity failure | Stale | Retry |
|---|---|---|---|---|---|---|
| publish | terminal receipt | n/a | outcome_unknown when ambiguity remains | fail closed | typed stale, no receipt | same ID/same command returns original |
| recovery read | verified receipt | exact miss | propagate availability | fail closed | n/a | repeatable |
| same ID / changed command | n/a | n/a | n/a | idempotency conflict | n/a | never accepted |
| revision exists / receipt absent | no inferred success | explicit absence/integrity behavior | normal dependency behavior | fail closed | possible stale on fresh publish | no fallback |

Fallback sources: none. Current head is never a recovery fallback.

## §6B Identity matrix

| Situation | Rule | Ambiguity | Fallback |
|---|---|---|---|
| `(space_id, publication_id)` | one terminal command/result | mismatch is conflict | none |
| revision ID | deterministic child identity, not idempotency key | fail if corrupt | none |
| operation IDs | semantic operation identity only | not publication identity | none |
| aliases/labels/normalized keys | prohibited | n/a | none |
| same publication after head advance | receipt remains authoritative | no head requirement | none |
| publication ID reused for changed command | idempotency conflict | fail closed | none |

## §6C Persistence/replay matrix

| Operation | Durable representation | Round trip | Replay | Migration | Rollback |
|---|---|---|---|---|---|
| fresh publish | receipt + V5.2 revision/head/event | receipt verifies exact command/revision | first commit wins | new table only | failed transaction leaves prior authority |
| exact replay | existing receipt | exact original result | zero new event | no backfill assumed | later head move does not erase receipt |
| changed replay | existing receipt unchanged | n/a | conflict | n/a | zero mutation |
| recovery lookup | existing receipt | exact revision cross-check | repeatable | n/a | read-only |

Migration rules:

- add terminal receipt storage keyed by `(space_id, publication_id)`;
- reference exact native published revision where practical;
- no mutable lifecycle;
- no backfill;
- clean upgrade/downgrade;
- resolve actual predecessor Alembic head after #71 merge.

## §6D Predecessor mapping

| V5.2 source | V5.3 use | Transformation | Proof |
|---|---|---|---|
| sealed materialization command | exact publication content | canonical command SHA | unit contract |
| space ID | receipt scope | exact copy | receipt test |
| expected parent | CAS + receipt binding | exact copy | stale/replay tests |
| operation IDs | revision identity | preserve; never publication key | identity test |
| expected revision ID | receipt child ID | accepted V5.2 computation | binding test |
| graph digest | receipt graph digest | exact | corruption test |
| stale-parent error | fresh failure | preserve | unit + PG |
| revision/head/event transaction | larger transaction | add receipt to same atomic boundary | rollback/concurrency |
| repository exception | recovery pressure | one exact receipt probe | response-loss |

## §7 Evidence required to merge

| Guarantee | Boundary | Evidence |
|---|---|---|
| receipt/revision/head/event atomicity | PostgreSQL repository | injected failure leaves no partial V5.3 state |
| exact replay | repository + application | same ID/same command gives original receipt, no new event |
| changed retry conflict | repository | same ID/different command fails with zero mutation |
| response-loss recovery | application | post-commit throw + receipt probe returns success |
| outcome-unknown honesty | application | publish/probe unavailable returns typed unknown |
| replay after descendant | application/repository | publish A, publish B, retry A → A receipt |
| same-ID concurrency | PostgreSQL independent connections | same command converges to one receipt |
| changed same-ID concurrency | PostgreSQL independent connections | one winner, one conflict |
| different-ID same-parent race | PostgreSQL independent connections | one success, one stale |
| corruption | reconstruction | tampered receipt/revision rejected |
| exact miss | application | no head/history inference |
| V0 freeze | contract fixture | aggregate digest exact |
| V5.4 remains false | diff inspection | contribution/domain/materialization contracts unchanged |

Run at minimum:

```bash
uv run ruff check .
uv run pyright

uv run pytest -q tests/unit/test_vnext_cas_publication.py
uv run pytest -q tests/unit/test_vnext_publication_recovery.py
uv run pytest -q -m 'not integration'

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind   uv run pytest -q tests/integration/test_postgres_vnext_knowledge_publication_recovery.py -o addopts=''

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind   uv run pytest -q tests/integration/test_migrations.py -o addopts=''

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind   uv run pytest -q -m integration -o addopts=''

uv run alembic heads
git diff --check
git diff --stat <base>...HEAD -- <§4 paths>
git diff --name-only <base>...HEAD
```

Frozen V0 digest must remain:

```text
fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

Minimal live proof: not applicable. V5.3 is internal durable authority; PostgreSQL response-loss/replay proof is the correct owning evidence. Do not invent a route or product integration.

For any base failure, compare exact base/head results and report inherited debt honestly.

## §8 Nano-commit contract

Recommended story:

```text
1. STEWARDSHIP: accept V5.2 and activate V5.3
   - exact #71 acceptance/merge truth
   - canonical handoff
   - roadmap/stewardship only

2. KERNEL: define terminal vNext publication receipt
   - ADR
   - receipt contract
   - errors/port shape
   - frozen V0 unchanged

3. KERNEL: add atomic durable publication replay
   - in-memory + PostgreSQL unit-of-work
   - migration
   - exact replay/conflict

4. KERNEL: recover uncertain publication outcomes
   - receipt-first application replay
   - one post-throw recovery probe
   - outcome_unknown

5. KERNEL: prove V5.3 concurrency and recovery
   - focused unit/integration/adversarial proof
```

No V5.4 work may enter these commits.

## §9 Acceptance rubric

- [ ] Final accepted/merged PR #71 facts are recorded before runtime implementation.
- [ ] One `(space_id, publication_id)` binds one exact command and terminal receipt.
- [ ] Fresh publish commits receipt + revision + head + publish event atomically.
- [ ] Same ID + same command replays success with zero new event.
- [ ] Same ID + changed command fails closed with zero mutation.
- [ ] Replay succeeds after a descendant becomes current.
- [ ] Lost post-commit response is recovered by receipt lookup, not head inference.
- [ ] Ambiguous recovery returns typed outcome-unknown with retry-safe identity.
- [ ] Same-ID and different-ID concurrency are proven with independent PG connections.
- [ ] Receipt/revision corruption fails closed.
- [ ] Missing receipt never becomes inferred success.
- [ ] Frozen V0 aggregate remains exact.
- [ ] No prospective-reference contract/implementation leaked in.
- [ ] No path outside §4/bounded exception changed.
- [ ] Base/head failures and waivers are reported honestly.
- [ ] Canonical handoff governed implementation; no chat copy substituted.

Final disposition:

```text
V5_3_DURABLE_PUBLICATION_REPLAY_RECOVERY_ACCEPTED
```

## §10 Stop conditions

Stop and rebrief if:

- final PR #71 materially changes the assumed V5.2 contract;
- #71 cannot reconcile with later `main` persistence work narrowly;
- receipt cannot share the revision/head/event atomic boundary;
- frozen V0 contracts must change;
- recovery requires scans/current-head/timestamp/payload inference;
- real V5.2 durable publications without receipts require backfill semantics;
- a pending/running/retry job lifecycle is required;
- transport is required to prove the capability;
- prospective references/entity-ID allocation are required;
- a second independently useful capability appears;
- any runtime/contract path outside §4 is required.

## §11 Required review handback

Return:

1. exact PR URL, branch, base SHA, reviewed head SHA;
2. final PR #71 accepted head, merge SHA, final PASS reference;
3. §1 mission/invariant exactly;
4. nano-commit list;
5. actual changed paths and focused diff stat;
6. exact receipt contract fields;
7. exact repository transaction shape;
8. all §7 commands/results with provenance;
9. concurrency outcomes;
10. post-commit response-loss outcome;
11. replay-after-descendant outcome;
12. migration head and upgrade/downgrade result;
13. frozen V0 digest result;
14. baseline failures/waivers;
15. paths outside §4;
16. stop conditions;
17. confirmation V5.4 remains unimplemented;
18. confirmation no parallel chat-only handoff replaced this artifact.

## §12 Named successor — V5.4 prospective-reference publication

V5.3 deliberately does not make WorldKeeper ready.

After V5.3 acceptance:

```text
V5.4 — prospective-reference identity allocation + substitution
```

Primary question:

> Can DungeonMind accept one governed transaction containing create-new entity results referenced by dependent assertions before durable IDs exist, allocate those durable entity IDs under DungeonMind authority, substitute them consistently throughout the transaction, publish the complete result through the V5.3 recoverable atomic publication path, and return a durable prospective/client-operation → durable-result mapping?

Current vNext pressure:

```text
ProposeEntity contains Entity(entity_id=durable ID)
Assertion contains durable subject/entity-ref IDs
V5.1 therefore begins after durable identity already exists
```

Do not solve that in V5.3.

V5.4 must determine the smallest DungeonMind-owned prospective transaction contract without making WorldKeeper an ID allocator and without casually rewriting the frozen V0 contract bundle.

Until V5.4 is accepted:

```text
WorldKeeper WK-3 implementation remains BLOCKED
on DungeonMind prospective-reference atomic publication.
```

## §13 Current implementation handback — Review Cycle 2 HOLD

```text
repository: Drakosfire/DungeonMind
branch: kernel/v5-3-durable-publication-replay-recovery
base: 01762848cbdd666b092d4cb26af558ba1468fa4d
reviewed head: 103651aa870eb51dc7a97955f0d5d9ff5add6c40
PR: #74
Review Cycle 1: HOLD — review 5292176272
Review Cycle 2: HOLD — review 5292793905
```

Cycle 1 blockers were repaired in commit `103651a`; Cycle 2 leaves this
narrower repair contract:

1. Persistence-integrity corruption must propagate as
   `PersistenceIntegrityError`, never be converted into `outcome_unknown`.
2. PostgreSQL proof must cover same-ID concurrent replay, same-ID conflicting
   command race, receipt/revision/head/event rollback, and replay after a
   descendant.
3. The response-loss cohort must assert one receipt for one publication, and
   exact-head integration CI must pass.
4. Canonical stewardship fields must remain current, including the PR #71
   merge SHA and the V5.3 primary question.
5. The approved five-path test-surface rebrief above must remain recorded.

Repair acceptance requires exact receipt cross-verification of publication ID,
space, expected parent, command digest, payload digest, and published revision.
The repair must not claim V5.3 acceptance until PostgreSQL evidence and CI are
independently rerun on the repaired exact head. V5.4 remains entirely out of
scope.
