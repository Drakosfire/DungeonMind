# HANDOFF — B.2f-a Finalized-review Graph Materializer

**Created:** 2026-08-03  
**Status:** IMPLEMENTED — pending review  
**Repository:** `Drakosfire/DungeonMind`  
**Branch:** `founding/pr-b2f-a-finalized-review-graph-materializer`  
**Implementation base:** `5a59f260626a0e901b58e4d033299746d1ead3e9`  
**Predecessor:** PR #11, B.2f-0, merged into `main`  
**Reviewed predecessor head:** `2ef26a4fe0b809ce8dc4dbe8c169655ec9e5c336`  
**Parent decision:** `Docs/Decisions/ADR-0008-b2f-0-accepted-review-materialization-characterization.md`  
**Decision:** `Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md`  
**Named successor:** B.2f-b expected-parent CAS publication

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

## §4 Changed paths

Only the paths authorized by the handoff changed:

```text
src/dungeonmind/application/review_materialization.py
src/dungeonmind/application/__init__.py       # bounded package export
src/dungeonmind/domain/errors.py
src/dungeonmind/domain/__init__.py             # bounded error export
tests/conformance/test_review_materialization.py
tests/fixtures/contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json
Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md
Docs/Handoffs/HANDOFF-b2f-a-finalized-review-graph-materializer.md
Docs/Roadmaps/ROADMAP.md
README.md
```

The two `__init__.py` changes use existing centralized package-export
conventions. No other path is required.

## §5 Evidence

The primary fixture is the complete production output for the real finalized
Tripod Null-Calf review against the Gatewatch v3 parent. The owning test
compares the full payload and independently compares accepted effects against
the merged B.2f-0 characterization.

The focused suite proves:

- exact payload and digest;
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
- output reparse failure;
- input parent immutability.

Primary materialized payload:

```text
SHA-256: 75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
derived relationship IDs:
  rel:7136b2aa4616bd0455f8fde084b5a1c0
  rel:915b93b66a80e03522cbd789eac0cafc
  rel:92889103c270dd357944b277ff126cc1
```

The owning materializer suite has 16 passing tests; the independent B.2f-0
oracle suite has 18 passing tests.

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

The base comparison is pinned to:

```text
5a59f260626a0e901b58e4d033299746d1ead3e9
```

The implementation must remain green against the repository's core and
integration CI jobs. Integration does not need a new database-backed test for
this pure transformation.

## §7 Successor split

The next slice, B.2f-b, owns expected-parent current-head observation and CAS
publication. B.2f-c owns durable publication operation identity and uncertain
outcome recovery. B.2f-d owns transport and consumer integration. None is
implemented or claimed here.
