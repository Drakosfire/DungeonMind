# ADR-0009 — B.2f-a finalized-review graph materializer

**Status:** Accepted  
**Date:** 2026-08-03  
**Deciders:** B.2f-a implementation dispatch  
**Extends:** ADR-0008 and ADR-0007

## Decision

B.2f-a adds one generic, pure application seam:

```text
serialized-valid ContributionReviewState
+ serialized-valid exact StoredGraphRevision
+ matching GraphSnapshotReader
→ validated dm_union_graph_v3 payload
→ canonical payload SHA-256
→ ephemeral FinalizedReviewGraphMaterialization
```

The materializer revalidates both serialized inputs, verifies the review's
expected-parent and semantic-profile pins, parses the exact parent payload,
deep-copies that payload, realizes accepted review effects, reparses the
candidate output through the supplied reader, and returns a result bound to
the review, reviewed contribution, confirmation, operation, parent, schema,
and payload digest. The returned JSON-compatible payload is recursively
immutable, so callers cannot alter graph bytes while retaining the original
digest.

The materializer does not:

- construct a `WorldGraphRevision` or `PublishRevisionCommand`;
- read or advance a graph head;
- call a repository or write durable state;
- append identity decisions;
- expose transport or consumer integration;
- import `dungeonmind_dnd`;
- interpret campaign, temporal, visibility, epistemic, Timeline, or mechanics
  semantics.

## Payload transformation rules

Only `dm_union_graph_v3` is materializable in this slice. Parent nodes,
relationships, and evidence rows remain in their existing order. Touched
existing nodes are replaced in place; newly created nodes are appended by
object ID. Newly accepted evidence is appended once per evidence ID in sorted
order. Newly created relationships are appended in derived relationship-ID
order.

`create_new` requires an absent target and exactly one accepted label. It
creates a v3 node with the proposal kind and target ID, accepted canonical
label evidence, sorted accepted aliases, and an optional accepted summary.

`confirm_existing` requires an existing target with the exact proposal kind.
An accepted label replaces the canonical label and core evidence; an absent
label retains both. Accepted aliases append assertion records after all parent
aliases, sorted by source assertion ID. An accepted summary replaces the
single summary assertion; an absent summary retains the parent summary.
Parent evidence rows are never garbage-collected.

`reject_candidate` produces no node or dependent relationship effect.
Rejected assertions and rejected-only evidence remain review history and do
not enter graph truth.

Every accepted graph assertion must carry at least one evidence reference.
Accepted alias and summary source assertion IDs become graph assertion IDs and
must not collide with any parent alias or summary assertion ID. Accepted
evidence IDs must not collide with the exact parent evidence namespace.
Conflicting serialized evidence for one accepted ID fails closed.

Accepted relationships require both endpoints after node effects, one accepted
assertion per triple, a triple absent from the exact parent, and evidence.
They are never merged with or used to augment an existing relationship.

Relationship IDs are derived only inside the materializer:

```text
material = {
  schema: "dm_review_relationship_id_v1",
  world_id,
  review_id,
  reviewed_contribution_id,
  expected_parent_revision_id,
  source_assertion_id,
  subject_object_id,
  predicate,
  object_object_id,
}
relationship_id = "rel:" + canonical_sha256(material)[:32]
```

Parent/new relationship-ID collisions fail closed.

## Failure contract

`ContributionMaterializationError` has stable code
`contribution_materialization_error`. Its `details["reason"]` is the
machine-readable failure boundary. Implemented reasons include:

`state_reload_validation`, `parent_reload_validation`,
`parent_binding_mismatch`, `unsupported_graph_schema`,
`orphan_accepted_assertion`, `accepted_assertion_missing_graph_evidence`,
`parent_assertion_id_collision`, `parent_evidence_id_collision`,
`duplicate_relationship_triple`, `preexisting_relationship_triple`,
`relationship_id_collision`, and `output_graph_validation`.

Failure messages and chained exceptions never include source prose, labels,
summaries, locators, or malformed payloads.

## Proof

The owning conformance suite compares the complete production payload with
the checked-in Tripod Null-Calf materialized graph fixture and independently
compares exact object fields, field provenance, relationship triples,
relationship evidence, and accepted evidence rows with the B.2f-0
characterization. It also proves:

- exact replay and deterministic relationship IDs;
- recursive result-payload immutability and digest binding;
- actual B.2d planner → B.2e review → materializer `confirm_existing`;
- `create_new`, `confirm_existing`, and `reject_candidate`;
- rejected assertion/evidence exclusion;
- post-validation review mutation and changed-parent rejection;
- parent assertion/evidence namespace collisions;
- missing accepted graph evidence;
- duplicate and pre-existing relationship rejection;
- relationship-ID collision rejection;
- output reparse and output-field/triple/evidence validation failure;
- parent payload immutability and untouched-row preservation.

Publication, CAS, persistence, recovery, identity-decision append, and
transport remain separate B.2f-b/c/d capabilities.
