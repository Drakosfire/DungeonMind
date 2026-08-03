# HANDOFF — B.2f-a Finalized-review Graph Materializer

**Created:** 2026-08-03  
**Status:** ACTIVE — dispatch exactly one implementation capability
**Repository:** `Drakosfire/DungeonMind`
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b2f-a-finalized-review-graph-materializer.md`
**Suggested branch:** `founding/pr-b2f-a-finalized-review-graph-materializer`
**Predecessor:** merged PR #11, B.2f-0 accepted-review materialization characterization
**Parent decision:** `Docs/Decisions/ADR-0008-b2f-0-accepted-review-materialization-characterization.md`  
**Decision:** `Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md`  
**Named successor:** B.2f-b expected-parent CAS publication

## §0 Capability decomposition and stop conditions

B.2f-a is one implementation capability in a deliberately split lane:

```text
B.2f-a  pure finalized-review graph payload materializer
B.2f-b  expected-parent current-head observation and CAS publication
B.2f-c  durable publication operation identity and uncertain-outcome recovery
B.2f-d  service transport and external consumer contract
Buddy   shadow adoption and eventual authority migration
```

Only B.2f-a is dispatched here. The materializer must stop and remain pure if
publication recovery, transport, or a new durable/public format becomes
necessary to prove the payload transformation. It must also stop rather than
interpret temporal semantics that have not stabilized, bind external
mechanics resources, or import D&D-specific policy.

## §1 Mission and merge-ready invariant

Given one finalized B.2e review and its exact pinned `dm_union_graph_v3`
parent, deterministically produce one validated next graph payload and
payload digest that realize the accepted B.2f-0 effects—without constructing a
graph revision, writing a repository, advancing a graph head, appending
identity decisions, or exposing transport.

Merge-ready invariant:

```text
one serialized-valid ContributionReviewState
+ one serialized-valid exact StoredGraphRevision
+ one matching GraphSnapshotReader
→ one byte-equivalent FinalizedReviewGraphMaterialization
  bound to the same review, reviewed contribution, confirmation, operation,
  parent revision, parent payload digest, graph schema, and result payload digest
```

The same exact inputs always produce the same graph payload and digest. A
changed parent, mutated review, unsupported field shape, missing graph
evidence, namespace collision, duplicate/pre-existing relationship triple, or
invalid output fails before a materialization result is returned.

## §2 Delivered boundary

Production seam:

```python
materialize_finalized_review(
    state: ContributionReviewState,
    *,
    parent: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewGraphMaterialization
```

The materializer:

1. reload-validates the finalized review and exact stored parent;
2. checks the parent payload digest, expected parent, world, schema, and
   semantic-profile pin;
3. parses the exact parent payload through the supplied reader;
4. deep-copies and preserves untouched v3 records and list positions;
5. materializes `create_new`, `confirm_existing`, and `reject_candidate`;
6. admits accepted evidence only, with no source-only synthesis;
7. derives deterministic relationship IDs under
   `dm_review_relationship_id_v1`;
8. rejects namespace, triple, endpoint, evidence, and relationship-ID
   collisions;
9. reparses and validates the complete output through the same reader; and
10. returns an ephemeral result bound to all review and parent digests.

Accepted aliases and summaries reuse their accepted source assertion IDs.
Canonical labels have no graph assertion ID. Temporal payloads and full
source/campaign/visibility/epistemic provenance remain in the reviewed
contribution and result binding; no invented graph fields are added.

## §2a Required payload rules

The exact `dm_union_graph_v3` payload transformation is part of this
dispatch—not an invitation to add a new graph schema:

- `create_new` requires an absent target, the proposal's exact kind, and one
  accepted label. The label becomes the canonical node label and its evidence
  becomes core node evidence. Accepted aliases are sorted by source assertion
  ID; one accepted summary is optional.
- `confirm_existing` requires an existing target with the exact proposal kind.
  An accepted label replaces the canonical label and core evidence; without one,
  both are retained. Accepted aliases append after parent aliases, sorted by
  source assertion ID. An accepted summary replaces the single summary slot;
  without one, the parent summary is retained.
- `reject_candidate` creates no node, relationship, or accepted-evidence
  effect. Rejected review history is never graph truth.
- Every accepted graph assertion requires at least one evidence reference.
  Accepted evidence rows are emitted once, in evidence-ID order, and parent
  evidence rows are never garbage-collected.
- Accepted relationships require two resulting endpoints, one accepted
  assertion per triple, a triple absent from the exact parent, and evidence.
  Their IDs are `rel:` plus the first 32 hex characters of the canonical SHA-256
  of the `dm_review_relationship_id_v1` material.
- Parent nodes, relationships, and evidence remain byte-equivalent and in their
  existing list positions. New nodes append by object ID and new relationships
  append by derived relationship ID.
- Accepted alias/summary assertion IDs and accepted evidence IDs must not
  collide with the exact parent namespaces. Conflicting serialized evidence,
  duplicate relationship triples, pre-existing relationship triples, dangling
  endpoints, and derived relationship-ID collisions fail closed.

The returned `FinalizedReviewGraphMaterialization` stores its payload as private
canonical JSON and returns a fresh JSON-compatible deep copy on every
`graph_payload` read. Caller mutation of that copy must never alter the stored
payload or digest, and `copy.deepcopy` of the result must remain supported.

## §3 Explicitly false after this slice

No path in B.2f-a:

- constructs a `WorldGraphRevision` or `PublishRevisionCommand`;
- reads or advances a current graph head;
- calls a repository or writes durable state;
- appends global `IdentityDecisionRecord` rows;
- persists a publication operation or recovery record;
- exposes an API, CLI, agent tool, UI, or consumer receipt;
- imports `dungeonmind_dnd`;
- changes `dm_union_graph_v3`;
- interprets Timeline, mechanics, resources, or D&D policy.

## §4 Dispatch scope and allowed paths

The implementation dispatch is intentionally narrow. The production boundary
may change only these paths:

```text
src/dungeonmind/application/review_materialization.py
src/dungeonmind/domain/errors.py
```

At most one additional package-export file is allowed, solely for the public
application seam:

```text
src/dungeonmind/application/__init__.py
```

The domain package export is intentionally outside this dispatch. Callers may
import the typed error from `dungeonmind.domain.errors`; no
`src/dungeonmind/domain/__init__.py` change is authorized.

The proof and documentation paths are:

```text
tests/conformance/test_review_materialization.py
tests/fixtures/contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json
Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md
Docs/Handoffs/HANDOFF-b2f-a-finalized-review-graph-materializer.md
Docs/Roadmaps/ROADMAP.md
README.md
```

No contract schema, graph reader, repository, migration, service, profile
package, or external repository path is authorized by this handoff.

## §5 Acceptance evidence and proof obligations

The primary fixture is the complete production output for the real finalized
Tripod Null-Calf review against the Gatewatch v3 parent. The owning test
compares the full payload and independently compares exact object fields,
field provenance, relationship triples, relationship evidence, and accepted
evidence rows against the merged B.2f-0 characterization.

The owning conformance suite must prove:

- exact payload and digest;
- copy-on-read result-payload isolation and digest binding;
- deterministic replay and relationship IDs;
- actual B.2d planner output through the B.2e review adapter for
  `confirm_existing`;
- create-new node construction;
- confirm-existing in-place label/summary replacement and alias append;
- reject-candidate exclusion of nodes, edges, and evidence;
- post-validation review mutation rejection;
- changed parent and unsupported schema rejection;
- parent assertion and evidence namespace collisions;
- accepted assertion without graph evidence;
- orphan assertions;
- duplicate and pre-existing relationship triples;
- derived relationship-ID collisions;
- reader input-mutation isolation for both parent and output parses;
- output reparse and output-field/triple/evidence validation failure;
- input parent immutability and byte-equivalent untouched-row preservation at
  original list positions.

The fixture must be generated from the real finalized B.2e state and exact
Gatewatch parent, not hand-authored as an approximation. The independent
characterization remains test-only and must not be imported by production
code.

## §6 Required verification

Run from the repository root:

```bash
uv run pytest -q tests/conformance/test_review_materialization.py
uv run pytest -q tests/conformance/test_review_materialization_characterization.py
uv run pytest -q -m 'not integration'
uv run ruff check .
uv run pyright
git diff --check
```

The implementation must remain green against the repository's core and
integration CI jobs. Integration does not need a new database-backed test for
this pure transformation.

## §7 Successor split

The next slice, B.2f-b, owns expected-parent current-head observation and CAS
publication. B.2f-c owns durable publication operation identity and uncertain
outcome recovery. B.2f-d owns transport and consumer integration. None is
implemented or claimed here.
