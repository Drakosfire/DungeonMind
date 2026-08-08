# ADR-0014 — Assertion-scoped World Graph (`dm_union_graph_v4`)

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** implementing agent, per operator dispatch
(`world/assertion-scoped-graph-v4`)
**Supersedes:** none
**Related:** ADR-0001 (datastore), ADR-0002 (lifecycle ownership), ADR-0004
(semantic profile boundary), ADR-0013 (D&D world-object mechanics re-anchor),
`contracts/knowledge_assertion.py`, `application/graph_snapshot_v4.py`,
`application/graph_scope.py`, `contracts/fictional_time.py`

## Question

Where does *knowledge state* live in a stored World Graph? Through v3, scope is
derived entirely from admitted evidence provenance: an assertion has no direct
campaign, audience, epistemic, canon, session, or temporal field. That works
while every distinction the runtime needs happens to line up with a source
artifact's visibility and campaign. It stops working as soon as one object must
carry knowledge that is true for one campaign and unknown in another, visible to
the GM and hidden from players, canonical in one claim and speculative in the
next — all sourced from the same artifact.

## Context

Three pressures converge:

1. **Grain.** V1 hides a whole object when any attached evidence fails. V2/V3
   recovered alias and summary grain but left object existence, properties (which
   do not exist yet), and relationships coarse. Nothing below object level can be
   independently campaign-scoped.
2. **Overloaded provenance.** Using source visibility as the only audience
   control means "who may know this" cannot vary between two claims that cite the
   same note. Campaign scope has the same problem, and campaign scope must never
   be allowed to fork object identity.
3. **Implicit temporal and session semantics.** DungeonMindBuddy's practice of
   treating "the session this came up in" as a proxy for "when this happened in
   the fiction" is a category error the kernel must refuse to inherit. Fictional
   time already exists as its own contract family
   (`dm_fictional_time_claim_bundle_v1`); a graph assertion needs to *reference*
   it, not re-derive it.

Closed invariants already in force: published graph schemas and durable contracts
are immutable and versioned; readers dispatch by exact `graph_schema`; identity is
opaque and never a label, path, or locator; the kernel never imports a
game-system profile package; scope filtering fails closed.

## Decision

1. **V4 is purely additive.** `dm_union_graph_v1/v2/v3` payload bytes, readers,
   admission behavior, and public dumps are unchanged. V4 is a new schema with its
   own reader (`UnionGraphV4SnapshotReader`) reached through
   `VersionedUnionGraphSnapshotReader` dispatch. No stored revision is rewritten
   and no older reader learns a new rule.
2. **Knowledge state is one shared contract, carried per assertion.**
   `dm_knowledge_assertion_metadata_v1` (`KnowledgeAssertionMetadataV1`) carries
   `assertion_id`, `campaign_scope`, `visibility`, `epistemic_kind`,
   `canon_state`, `evidence_ref_ids`, `session_refs`, and `temporal_scope`. Every
   field is required; `visibility`, `epistemic_kind`, and `canon_state` have no
   defaults, so an omitted audience or standing fails closed rather than
   defaulting to the most permissive value.
3. **The admissibility grain is the assertion, not the object.** Object
   existence, each alias, the summary, each property, and each relationship are
   independently durable assertions and are independently admitted or omitted.
4. **`campaign_scope` is required-but-nullable and never touches identity.** The
   key must be present; `None` means world-universal knowledge; a blank string
   fails closed. A world-scoped read (`campaign_id is None`) sees only
   world-universal assertions, and no read ever sees another campaign's
   assertions. An object's `object_id` never changes because an assertion about it
   is campaign-scoped — campaign scope partitions *knowledge*, not *things*.
5. **`assertion_id` is globally unique across every assertion family** — object
   existence, alias, summary, property, and relationship — within one payload. An
   id identifies exactly one durable claim, so exclusion diagnostics and future
   review flows can name an assertion without qualifying which family it came
   from.
6. **The epistemic vocabulary is versioned, not remapped.** `EpistemicKindV2`
   admits `asserted | inferred | speculative | fact | source_derived_candidate`.
   `fact` is **not** an alias for `asserted` and `source_derived_candidate` is
   **not** an alias for `inferred`; the kernel never equates them and never
   collapses one into the other. The historical
   `contracts.vocabulary.EpistemicKind` keeps its three members and its meaning
   for v1–v3 records; it is neither narrowed nor mutated.
7. **Temporal knowledge state is explicit and three-valued.**
   `TemporalScopeKind` is `unknown | world_timeless | fictional_time_ref`.
   `unknown` ("we have not established when this holds") is a different claim
   from `world_timeless` ("this holds independent of fictional time") and the two
   are never coerced into each other. `fictional_time_ref` requires an exact
   typed `FictionalTimeAnchorRefV1` (`dm_fictional_time_anchor_ref_v1`) naming
   `bundle_id` + `campaign_id` + `anchor_id` inside the existing
   `dm_fictional_time_claim_bundle_v1` authority; the other two kinds forbid a
   ref. Opaque strings are rejected. The target is always an **anchor**, never a
   claim, state, or bundle identity hidden in free text. Because FT bundles are
   campaign-owned and every read operates against one explicit campaign scope,
   `fictional_time_ref` additionally requires a **non-null** assertion
   `campaign_scope` that **equals** `fictional_time_ref.campaign_id`. World-
   universal assertions (`campaign_scope is null`) may use `unknown` or
   `world_timeless` only; they must not point into a campaign-owned chronology.
   A future world-universal fictional-time contract can lift that restriction
   deliberately; FT v1 does not pre-authorize it. Later resolution (not this
   schema) must verify the named bundle's world/schema/revision/digest pin and
   that `anchor_id` exists in that bundle. The kernel stores the typed
   reference and adds no competing chronology or query logic beside
   `contracts/fictional_time.py`.
8. **Session references are not fictional time.** `session_refs` records the
   real-world sessions an assertion surfaced in. There is no code path from
   `session_refs` to `temporal_scope`, in either direction, and none may be added
   without a new ADR.
9. **No implicit winner.** Multiple property assertions may share a
   `property_term`, and multiple alias assertions may carry the same alias text.
   The reader retains every one of them in payload order — no first-wins, no
   latest-wins, no merge. Only the projected `aliases` list is de-duplicated for
   index hygiene; the underlying assertions stay distinct. Resolving disagreement
   is a product/review decision the kernel deliberately does not make.
10. **Property values must be JSON-compatible.** `str`, finite `int`/`float`,
    `bool`, `null`, and lists/objects (string keys) recursively composed of those.
    Anything else — a `datetime`, a set, `NaN`/`Infinity`, a non-string object key
    — fails closed. A stored payload must round-trip through canonical JSON
    unchanged.
11. **V4 keeps v3's profile pinning and extends term qualification.** A required
    `semantic_profile` (`dm_semantic_profile_ref_v1`) is resolved and
    digest-verified through the `SemanticProfileRegistry` port, then every object
    `kind`, relationship `predicate`, **and property `property_term`** must be a
    qualified `namespace:local` token whose namespace the pinned descriptor
    admits. Terms stay opaque; the kernel admits or rejects and never interprets.
    No game-system vocabulary enters the kernel: the proof fixtures pin
    `test.kernel` / `kernel-profile-v1` (namespace `test`) and assert no D&D
    strings appear.
12. **The payload shape is strict and fails closed.** V4 validates against one
    `extra="forbid"` top-level model: `world_id`, `semantic_profile`, `objects`,
    `relationships`, `evidence_refs`. V4 uses `objects` where v1–v3 use `nodes`,
    so a v1–v3 payload can never be silently read as v4 (and vice versa), and
    unknown top-level keys are rejected. Evidence records keep the v1–v3
    `dm_evidence_ref_v1` shape under the existing `evidence_refs` key. Every
    assertion requires at least one `evidence_ref_id` **on the shared metadata
    contract itself** (`Field(min_length=1)` / nonempty validation on
    `KnowledgeAssertionMetadataV1`); the graph reader additionally requires each
    listed id to resolve inside the payload evidence ledger. Relationship
    endpoints are named
    `source_object_id` / `target_object_id` in the payload and map onto the
    existing `subject_object_id` / `object_object_id` view fields, so traversal,
    one-hop expansion, and scope code are shared rather than forked.
13. **Scoped reads gate on assertion scope first, then on unchanged evidence
    provenance.** Campaign and visibility mismatches are excluded **silently**
    (`out_of_scope`), never emitting an identifier the caller is not entitled to.
    Only after an assertion passes its own scope gate does the existing
    evidence → artifact → revision provenance chain run, unchanged and not
    broadened. Hidden object existence removes the object and everything hanging
    off it (aliases, summary, properties, relationships, indexes, traversal);
    a hidden alias/summary/property leaves the object standing without that
    field; a hidden relationship is not traversable.
14. **Assertion metadata never reaches a public dump.** The metadata lives on
    excluded view fields (`existence_assertion_metadata`,
    `admitted_property_assertions`, per-assertion `assertion_metadata`), so
    `GraphObjectView` / `GraphRelationshipView` dumps used for agent context and
    responses are byte-identical to what v1–v3 produced.
15. **Explicitly out of scope for this slice.** No `canon_state`-based read
    filtering (canon standing is recorded, not yet enforced); no `SourceArtifact`
    redesign; no adoption/bootstrap seam for existing v1–v3 worlds; no
    product/authoring API for creating assertions; no D&D vocabulary additions;
    no Mind Turn product wiring beyond schema dispatch. Each is a named future
    lane, not a silent gap.

## Consequences

- New contracts: `dm_temporal_scope_ref_v1`,
  `dm_fictional_time_anchor_ref_v1`, and
  `dm_knowledge_assertion_metadata_v1`, exported from `dungeonmind.contracts`
  alongside `TemporalScopeKind`, `FictionalTimeAnchorRefV1`, and `EpistemicKindV2`.
- New application module `application/graph_snapshot_v4.py` holding the v4
  payload records and reader; `graph_snapshot.py` gains `GRAPH_SCHEMA_V4`, the
  additive excluded view fields, and dispatch. The v4 reader is imported inside
  `VersionedUnionGraphSnapshotReader.__init__` because it depends on the view
  types defined in `graph_snapshot`; both modules stay in the same layer.
- `graph_scope.project_scoped_snapshot` gains a v4 branch plus a
  `assertion_metadata_in_scope` gate applied to relationships. For v1–v3 the gate
  is a no-op (metadata is `None`), so their regression suites are untouched.
- Because assertion metadata is required and un-defaulted, there is no migration
  path that "upgrades" a v1–v3 payload to v4 by relabeling `graph_schema`. Any
  future adoption must construct explicit assertions — which is the point.
- Recording `canon_state` without filtering on it means a `retracted` assertion
  is still readable in a v4 scoped read today. That is deliberate (the read
  policy is not yet decided) and must be closed before v4 carries retractions in
  production.

## Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Add assertion metadata to v2/v3 | Reject | Published schemas are immutable |
| Derive audience/campaign from evidence only (status quo) | Reject for v4 | Two claims citing one artifact cannot differ |
| Extend the historical `EpistemicKind` enum in place | Reject | Silently changes the meaning of stored v1–v3 records |
| Map `fact` → `asserted`, `source_derived_candidate` → `inferred` | Reject | Manufactures equivalences no producer asked for |
| Treat `unknown` temporal scope as `world_timeless` | Reject | Conflates "not established" with "timeless" |
| Opaque string `fictional_time_ref` | Reject | Ambiguous among anchor/claim/state/bundle; bypasses the accepted FT identity model |
| World-universal assertion + campaign-owned FT anchor | Reject | Campaign B would admit knowledge whose meaning points into Campaign A's chronology |
| Derive `temporal_scope` from `session_refs` | Reject | Real-world session order is not fictional chronology |
| First-wins / latest-wins for a repeated `property_term` | Reject | Kernel would silently resolve a disagreement it cannot adjudicate |
| Let `campaign_scope` participate in object identity | Reject | Forks one thing into per-campaign objects |
| Free-form property values | Reject | Breaks canonical-JSON round-trip and content addressing |
| Reuse the `nodes` key for v4 objects | Reject | Would let a v1–v3 payload half-parse as v4 |
| Filter reads on `canon_state` now | Defer | Read policy undecided; recording it is enough for this slice |
| Adoption seam for existing v1–v3 worlds | Defer | Needs a real world to adopt and an authoring path |

## Reversal path

V4 is an additive schema. Every v1–v3 revision remains readable byte-for-byte by
its own reader, so abandoning v4 means ceasing to publish it — nothing to
migrate back. Within v4, the assertion metadata contract can be superseded by
`dm_knowledge_assertion_metadata_v2` under a `dm_union_graph_v5` schema without
touching v1–v4 bytes; the versioned-supersession discipline is the reversal
mechanism. The one genuinely hard-to-reverse commitment is decision 4 (campaign
scope never affects identity): reversing it would fork stored `object_id`s and is
therefore treated as closed.
