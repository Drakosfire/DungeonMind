# HANDOFF — B.2f-0 Accepted-review Materialization Characterization

**Status:** ACTIVE — characterization only
**Created:** 2026-08-02
**Repository:** `Drakosfire/DungeonMind`
**Suggested branch:** `founding/pr-b2f-0-accepted-review-materialization-characterization`
**Predecessor:** B.2e finalized contribution review adoption
**Decision:** `Docs/Decisions/ADR-0008-b2f-0-accepted-review-materialization-characterization.md`

## Mission

Given one finalized B.2e review and its exact pinned parent revision, produce a
deterministic executable specification of the graph effects that accepted
review content would propose. This slice must not materialize production graph
objects, write a repository, publish a revision, implement recovery, expose
transport, or import DungeonMindBuddy.

## Primary proof

Use the real Tripod Null-Calf finalized review and Gatewatch `dm_union_graph_v3`
parent fixtures:

```text
exact parent revision
+ finalized B.2e review state
→ expected identity/object effects
→ expected accepted aliases and summaries
→ expected relationships and duplicate/pre-existing behavior
→ accepted evidence and source lineage
→ rejected assertions excluded from graph truth
→ deterministic proposed-effect digest
```

## Scope

In scope:

- Pure test-only characterization under `tests/conformance`.
- The raw parent payload is hashed first and parsed by the supplied graph
  reader; no independently supplied parsed snapshot is accepted.
- `create_new`, `confirm_existing`, and `reject_candidate` disposition mapping.
- Accepted `label`, `alias`, `summary`, and `relationship` field preservation.
- Existing-object reuse versus proposed creation, with existing-object output
  represented as executable field operations rather than ambiguous field lists:
  canonical label and summary assertions replace their single parent slots,
  while aliases append to the parent alias list.
- Field operations explicitly characterize provenance transitions: label
  replacement retires parent core evidence, alias append retains parent
  assertion/evidence identities and adds accepted assertion identities,
  summary replacement retires the parent summary assertion/evidence, and
  retained fields preserve their parent provenance.
- The positive `confirm_existing` proof uses an exact same-kind candidate-term
  match produced by the B.2d planner before characterization.
- Multiple accepted canonical label/summary assertions and normalized alias
  collisions fail closed.
- Duplicate and pre-existing relationship triples fail closed because B.2d
  does not authorize evidence augmentation or silent merging.
- Evidence references, source artifact/revision lineage, campaign scope,
  opaque temporal scope, visibility, and epistemic kind.
- Exact review operation, intent digest, confirmation, parent, graph-schema,
  graph-payload, and semantic-profile pins.
- Determinism, tamper rejection, changed-parent rejection, rejected-assertion
  exclusion, pre-existing relationship rejection, duplicate relationship
  rejection, and zero-write proof.

Out of scope:

- Production materializer or any durable/public materialization schema.
- Repository writes, graph publication, head CAS, uncertain-outcome recovery,
  transport, API/UI/tooling, external consumers, or Buddy integration.
- Timeline interpretation.
- Statblock/mechanics/resource bindings.
- Target override, fuzzy identity, merge/split, or relationship-evidence
  augmentation.

## Stop conditions

Stop and hand back if temporal payload requires semantic interpretation,
mechanics representation depends on unresolved Statblock contracts, publication
recovery is needed to prove the characterization, or D&D policy leaks into the
generic characterization.

## Deliverables

- `tests/conformance/review_materialization_characterization.py`
- `tests/conformance/test_review_materialization_characterization.py`
- `tests/fixtures/contribution_reviews/tripod-null-calf-review-effect-spec-v1.json`
- This handoff and ADR-0008.

The primary fixture is derived by executing the characterization against the
checked-in finalized review and parent fixtures; it is not hand-authored.
Additional confirm-existing, reject-candidate, and opaque-temporal matrix
variants are valid states derived from that finalized fixture in the
conformance tests.

## Later decomposition

- **B.2f-a:** pure reviewed-contribution materializer.
- **B.2f-b:** expected-parent CAS publication.
- **B.2f-c:** durable publication and uncertain-outcome recovery.
- **B.2f-d:** service transport and external consumer contract.
- **Buddy:** shadow adoption and eventual authority migration.
