# HANDOFF — V3 lazy exact and complete entity reads

**Created:** 2026-09-15  
**Status:** ACTIVE — predecessor merge and Steward transition are checked in; V3 implementation may be dispatched from current `main`  
**Repository / handoff branch:** `Drakosfire/DungeonMind` / `handoff/v3-lazy-exact-complete-entity-reads`  
**Suggested implementation branch:** `kernel/v3-lazy-exact-complete-entity-reads`  
**Predecessor:** PR #60 — `KERNEL: V2 KnowledgeReadContext + candidate admission`  
**Accepted predecessor head:** `121419e9d0823533306d6a9ca6586c769d82f6b0`  
**Predecessor final Steward review:** `5217813591`  
**Predecessor logical review cycles:** `5`  
**Predecessor disposition:** `V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED`  
**Predecessor merge:** `8af28bf359fa2044dbda23e674653edc9ebe3e6d`  
**Handoff merge:** `d409a2000e4608208cb8cfeed0c6907f3568abe2` — PR #61  
**Current `main` at activation sync:** `d409a2000e4608208cb8cfeed0c6907f3568abe2`  
**Handoff branch base:** exact accepted V2 head `121419e9d0823533306d6a9ca6586c769d82f6b0`  
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**Roadmap phase:** V3 — lazy exact / complete entity reads — ACTIVE  
**Successor:** V4 — neighborhood + evidence + anchor + deterministic indexed search  
**One-line mission:** Turn the accepted V1 revision-local indexes and V2 candidate-admission seam into exact-ID entity reads whose structural and provenance work is proportional to the selected entity and its support, while preserving complete one-hop truth, fail-closed admission, source freshness, and current World-runtime behavior.

---

## §0 Dispatch gate — predecessor merge and Steward transition

This handoff was authored before PR #60 merged. The activation facts below are now checked in and must not be re-invented.

**Do not dispatch V3 implementation from the historical PRE-DISPATCH handoff branch.**

Dispatch V3 only when all of the following are true on `main`:

```text
ACTIVE
+ durably checked into main
+ Steward records V2 COMPLETE / V3 ACTIVE
+ implementation branch is created from then-current main after this activation sync
```

Recorded predecessor / activation facts:

```text
last merged V2 implementation PR:
  PR #60 — KERNEL: V2 KnowledgeReadContext + candidate admission

actual merge SHA:
  8af28bf359fa2044dbda23e674653edc9ebe3e6d

accepted implementation head:
  121419e9d0823533306d6a9ca6586c769d82f6b0

logical review cycles:
  5

final PASS review:
  5217813591

final disposition:
  V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED

V3 handoff merge (PR #61):
  d409a2000e4608208cb8cfeed0c6907f3568abe2

current main at activation sync:
  d409a2000e4608208cb8cfeed0c6907f3568abe2
```

V2 accepted structural characterization:

```text
artifact:
  Docs/Benchmarks/vnext_candidate_admission_10k_v1.json

artifact exact substantive head:
  b88a7b6ebc03f5a227d599222e3f25075566382d

parsed semantic digest:
  552ecc3eb8f2af6de1969e6793ef286b02ed4af264eaa9313ee9ff283a02a4ac

single candidate:
  assertions evaluated: 1
  evidence ids resolved: 1
  artifact ids requested: 1
  revision ids requested: 1
  provenance snapshots: 1
  elapsed characterization: ~2.79 ms

batch 10:
  assertions evaluated: 10
  artifact ids requested: 10
  revision ids requested: 10
  provenance snapshots: 1
  elapsed characterization: ~12.71 ms

batch 100:
  assertions evaluated: 100
  artifact ids requested: 100
  revision ids requested: 100
  provenance snapshots: 1
  elapsed characterization: ~117.37 ms

structural gate:
  PASS — candidate-local source/provenance work
```

Steward phase after the activation sync:

```text
V0 COMPLETE — VNEXT_CONTRACT_FROZEN
V1 COMPLETE — V1_IMMUTABLE_NORMALIZATION_COMPLETE
V2 COMPLETE — V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED
V3 ACTIVE
```

The Steward must also make explicit that all of the following remain false:

- no native vNext `get_entity` is accepted yet;
- no native vNext `get_complete_entity` is accepted yet;
- no V4 neighborhood/evidence/anchor/search API is active;
- no vNext KnowledgeSpace/head storage runtime exists;
- no native vNext governed write path exists;
- no bridge-genesis migration exists;
- no current public World read cutover has occurred;
- no historical-reader quarantine/deletion is authorized;
- no DungeonBuddy runtime repin/cutover has occurred.

### Review gate

If `main` does not record the PR #60 merge SHA, accepted V2 head, 5 review cycles, review `5217813591`, and `V2 COMPLETE` / `V3 ACTIVE` on the Steward handoff, return the implementation PR for bookkeeping repair before accepting V3.

The Steward transition for V2→V3 is this activation sync, not a first implementation commit. Do not require the V3 implementation PR to rewrite Steward again unless a later merge/review fact changes.

After V3 eventually merges, the V4 successor must again update the Steward handoff first with the actual V3 merge SHA, accepted head, review-cycle count, benchmark artifact, V3 disposition, and `V4 ACTIVE`.

---

## §1 Outcome

A successful V3 leaves DungeonMind with two generic exact-ID application reads over one already-pinned `KnowledgeReadContext`:

```text
get_entity(entity_id)
get_complete_entity(entity_id)
```

Exact names may differ, but the semantics below are binding.

The operation shape becomes:

```text
exact ParsedKnowledgeRevision
→ exact revision-local entity/assertion/adjacency indexes
→ bounded structural candidate IDs
→ one V2 candidate-admission evaluation
→ candidate-local coherent provenance
→ immutable deterministic entity result
```

No bounded entity read may require:

```text
full-space projection
full assertion scan
full evidence scan
full source snapshot
head resolution
search fallback
client-side fragment union
```

The successful PR answers:

> **Can exact and complete entity truth be assembled from one exact `ParsedKnowledgeRevision` using only revision-local lookup/adjacency indexes plus the accepted V2 admission seam, with work proportional to the selected entity and its direct support rather than the whole KnowledgeSpace?**

Only successful final disposition:

```text
V3_LAZY_EXACT_COMPLETE_ENTITY_READS_ACCEPTED
```

Until that exact disposition is recorded by Steward review, V4 remains blocked from merge.

---

## §2 Authority and required reading

Read in this order before editing code.

### 2.1 Binding architecture

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
6. `CONTRIBUTING.md`

### 2.2 V1 immutable serving model

Read:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/records.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/frozen_json.py
src/dungeonmind/application/vnext/legacy_compat.py
```

Binding V1 structures include:

```text
entities_by_id
assertions_by_id
assertions_by_subject
entity_ref_outgoing
entity_ref_incoming
entity_ref_outgoing_assertions
entity_ref_incoming_assertions
entity_adjacency
assertion_evidence
evidence_by_id
```

V3 should consume these indexes. Do not re-derive them by walking the full revision.

Accepted V1 neighbor-entity indexes remain:

```text
entity_ref_outgoing[E]  → neighbor entity IDs
entity_ref_incoming[E]  → neighbor entity IDs
entity_adjacency[E]     → neighbor entity IDs
```

Those neighbor-entity indexes are not the complete-read candidate set. V3 complete reads consume the assertion-level entity-ref indexes:

```text
entity_ref_outgoing_assertions[E] → outgoing entity-ref assertion IDs
entity_ref_incoming_assertions[E] → incoming entity-ref assertion IDs
```

Do not rediscover incoming assertion IDs by scanning an incoming neighbor's `assertions_by_subject` list.

### 2.3 V2 admission seam

Read the exact accepted PR #60 implementation at the merged equivalent of accepted head `121419e9...`:

```text
src/dungeonmind/application/vnext/read_context.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/provenance.py
src/dungeonmind/application/vnext/ports.py
src/dungeonmind/application/vnext/errors.py
tests/unit/test_vnext_knowledge_read_context.py
Docs/Benchmarks/vnext_candidate_admission_10k_v1.json
```

V3 must reuse the accepted semantics:

- exact revision/request/domain/profile pinning;
- generic standing/scope/visibility/domain-declaration/profile checks;
- candidate-local evidence/source dependency discovery;
- one coherent pinned source view;
- source freshness across new contexts;
- pure domain-policy narrowing only;
- no revision-only cache of admission/source verdicts.

V3 is not permission to fork a second authorization/provenance path.

### 2.4 Historical complete-object evidence

Read for product/correctness lessons, **not** as an API to copy:

```text
Docs/Handoffs/HANDOFF-complete-selected-object-one-hop-read.md
```

It established two binding lessons that survive genericization:

1. a selected object/entity can require all admitted touching one-hop relationships plus opposite endpoints;
2. ordinary retrieval caps such as 12 / 24 / 32 / 32 cannot silently define truth labeled `complete`.

Do not import World-specific request/DTO semantics from that historical operation into the vNext Kernel.

---

## §3 Primary question and write lease

### Primary question

> **Can exact and complete entity truth be assembled from one exact `ParsedKnowledgeRevision` using only revision-local lookup/adjacency indexes plus the accepted V2 admission seam, with work proportional to the selected entity and its direct support rather than the whole KnowledgeSpace?**

### Expected write lease

Primary production surface:

```text
src/dungeonmind/application/vnext/
  entity_reads.py            # preferred illustrative name
  read_context.py            # only bounded internal extension if V3 needs to reuse the V2 provenance snapshot
  admission.py               # only bounded result/work-accounting extension if necessary
  errors.py                  # bounded exact-read errors
  __init__.py                # narrow exports
```

Tests:

```text
tests/unit/test_vnext_entity_reads.py
```

Fixtures may extend existing native vNext fixtures under:

```text
tests/fixtures/vnext/
```

Benchmark:

```text
benchmarks/vnext_entity_reads_10k.py
Docs/Benchmarks/vnext_entity_reads_10k_v1.json
```

Bounded discovery may add at most two additional application-layer files if immutable result records/work accounting are cleaner separately.

Expected zero changes to:

```text
src/dungeonmind/contracts/vnext/*
current World public read path
legacy v1-v6 readers
legacy compatibility mapping semantics
publication/write repositories
PostgreSQL schema/migrations
DungeonBuddy
```

If a V0 contract change appears necessary, stop and rebrief.

---

## §4 In scope

1. Exact `entity_id` lookup against one `ParsedKnowledgeRevision`.
2. A generic exact entity read returning the selected structural identity plus all admitted assertions whose subject is that entity.
3. A generic complete entity read returning:
   - selected structural entity;
   - all admitted subject assertions;
   - all admitted incoming/outgoing entity-ref assertions touching the selected entity;
   - every required opposite endpoint entity for those admitted touching assertions;
   - all direct admitted-assertion evidence/support metadata required to interpret those returned assertions;
   - explicit completeness.
4. Reuse of one exact `KnowledgeReadContext` supplied by the caller.
5. One candidate-admission evaluation per entity-read operation unless measured evidence proves a semantically equivalent narrower mechanism.
6. One coherent targeted source/provenance snapshot per entity-read operation where the selected candidate support requires source state.
7. Safe internal reuse of the V2 provenance snapshot so V3 does not perform a second incoherent or unnecessarily duplicated source-authority read.
8. Deterministic immutable result records and deterministic ordering.
9. Deterministic result semantic digest.
10. Explicit exact miss semantics; no search/alias fallback.
11. Native organizational-memory fixture proof.
12. Buddy-shaped opaque scope/visibility proof without importing Buddy.
13. Low-degree exact entity witness.
14. Entity with zero admitted assertions witness.
15. >24 admitted touching entity-ref assertion witness.
16. >32 evidence/support locator witness where practical, proving old product caps are not completeness.
17. Incoming, outgoing, and self-loop relationship witnesses.
18. Source-authority freshness across newly constructed contexts.
19. Same-context source coherence.
20. 10k structural/performance characterization proving the read does not scale with unrelated space size.

---

## §5 Explicitly out of scope

Do **not** implement in V3:

```text
mutable head resolution
KnowledgeSpace repository/storage runtime
ProjectionSnapshot fabrication
full-space vNext projection
neighborhood depth API
standalone evidence lookup API
standalone anchor-resolution API
search / lexical query API
alias search or identity reconciliation UI
pagination of a result labeled complete
arbitrary result caps defining complete truth
native vNext writes/publication
PostgreSQL vNext authority schema
bridge-genesis migration
DungeonBuddy production domain policy
DungeonBuddy repin or product cutover
current World reader replacement
historical-reader quarantine/deletion
vector retrieval
new distributed cache
new graph database
```

V4 owns neighborhood, standalone evidence/anchor reads, and deterministic indexed search.

V3 may return evidence/locator data already directly required by returned assertions. That is not permission to add V4 public lookup APIs.

---

## §6 Binding read semantics

### 6.1 The caller supplies an already-pinned `KnowledgeReadContext`

Preferred service shape is conceptually:

```python
service.get_entity(context, entity_id)
service.get_complete_entity(context, entity_id)
```

The entity-read service does not itself resolve a mutable head, fetch a revision, or choose domain/profile descriptors.

The accepted V2 context already binds:

```text
space_id
exact revision
request scope selector
audience labels
standing selector
focus/domain context
exact domain contract
exact semantic profile
pure domain policy
coherent source authority view
```

Do not duplicate those checks in a second independent implementation. A small defensive assertion that result identity matches context identity is fine; a second authorization engine is not.

### 6.2 Exact entity identity only

`entity_id` is an opaque stable ID.

Read shape:

```text
parsed.entities_by_id[entity_id]
```

No fallback to:

```text
alias
label
substring
lexical token
nearest match
search
```

A structural miss is a miss.

### 6.3 Entity structural identity is not an assertion

The frozen vNext contract defines:

```text
Entity(entity_id)
```

with no generic entity-level scope or visibility metadata.

Therefore V3 must not fabricate entity-level authorization by inspecting arbitrary assertions.

Binding V3 posture:

- if the exact opaque `entity_id` does not exist structurally, return exact miss;
- if it exists structurally, the minimal entity identity may be returned;
- assertion admission remains assertion-scoped;
- an existing entity may therefore be returned with zero admitted assertions;
- returning the minimal entity identity does **not** assert any domain fact about it.

This is intentionally different from inventing a magic `exists` predicate.

If accepted product/security semantics require the mere existence of an entity ID itself to be audience-protected, stop. That would expose a missing contract/architecture decision because the frozen `Entity` contract has no entity visibility field and V2 only admits assertions.

Do not silently infer entity visibility from:

```text
whether any assertion is visible
which predicate happens to mean existence in one domain
classification assertions
aliases
source visibility
```

### 6.4 `get_entity` candidate set

For selected entity `E`:

```text
entity = parsed.entities_by_id[E]
candidate_assertion_ids = parsed.assertions_by_subject[E]
```

Then call the accepted V2 admission seam over that exact candidate set.

Return:

```text
selected entity E
all admitted subject assertions for E
all direct evidence/support metadata for those admitted assertions
exact read identity/completeness/work accounting
```

`get_entity` does **not** include incoming assertions whose subject is another entity merely because they reference `E`.

It also does not recursively expand endpoint assertions.

### 6.5 `get_complete_entity` candidate set

For selected entity `E`, derive candidates from revision-local indexes only:

```text
subject IDs            = assertions_by_subject[E]
outgoing assertion IDs = entity_ref_outgoing_assertions[E]
incoming assertion IDs = entity_ref_incoming_assertions[E]

candidate IDs = deterministic deduplicated union(
  subject IDs,
  outgoing assertion IDs,
  incoming assertion IDs,
)
```

`entity_ref_incoming[E]` and `entity_ref_outgoing[E]` remain neighbor-entity indexes. They must not be treated as assertion IDs and must not be used to scan a neighbor's full subject assertion list.

The union is important because outgoing entity-ref assertions are normally also subject assertions and must not be evaluated/returned twice.

Do not discover incoming references by scanning every assertion value.

Pass the whole deduplicated candidate set through one V2 admission evaluation.

The complete result contains every **admitted** candidate assertion. Kernel/domain-excluded assertions are intentionally absent and do not make the result partial.

### 6.6 Touching entity-ref semantics

A touching relationship is any admitted assertion whose value is an entity reference and where:

```text
assertion.subject_entity_id == selected_entity_id
OR
assertion.value.entity_id == selected_entity_id
```

Direction is preserved exactly.

Do not normalize both directions into an undirected edge DTO.

For every returned touching entity-ref assertion, include the opposite endpoint as the minimal structural entity identity.

Rules:

- outgoing assertion `E -> X`: endpoint is `X`;
- incoming assertion `X -> E`: endpoint is `X`;
- self-loop `E -> E`: do not duplicate `E` into related endpoints;
- endpoint IDs must resolve structurally in the exact parsed revision;
- V1 referential-integrity guarantees should make a missing endpoint impossible; if observed, fail closed as structural corruption rather than silently emitting a dangling edge.

### 6.7 Do not expand endpoint truth

`get_complete_entity(E)` is complete for the selected entity's one-hop touching assertion closure.

It is **not** a depth-1 neighborhood projection of all endpoint facts.

Return only minimal opposite endpoint identities needed to interpret touching entity-ref assertions.

Do not automatically include:

```text
endpoint subject assertions
endpoint aliases
endpoint evidence unrelated to the touching assertion
endpoint classifications
second-hop relationships
```

Those belong to V4 neighborhood or separate exact reads.

This rule is important for both semantics and cost shape.

### 6.8 IdentityAlias is not silently added to the read

`IdentityAlias` is separate Kernel identity machinery and does not pass through the accepted V2 assertion-admission seam.

V3 exact-ID reads therefore do not automatically return all native identity aliases.

Legacy scoped/visibility-sensitive aliases that required preservation already survive the compatibility codec as assertions and will follow assertion admission normally.

If V3 requires a new generic alias-admission policy to satisfy a product contract, stop and rebrief rather than assuming all aliases are public.

### 6.9 Complete means complete under the request

Completeness is relative to:

```text
one exact ParsedKnowledgeRevision
+ one exact KnowledgeReadContext
+ the selected entity's complete structural V3 candidate closure
+ V2 Kernel/domain admission
```

A `complete` result means:

1. all structurally relevant V3 candidate assertion IDs were enumerated from the exact revision indexes;
2. every candidate was evaluated by the accepted V2 admission path;
3. every admitted candidate assertion required by the operation is present exactly once;
4. every opposite endpoint required by an admitted touching entity-ref assertion is present;
5. every direct returned-assertion evidence/support record promised by the V3 result contract is present;
6. no ordinary result cap truncated any of the above.

Excluded assertions do not make the result partial. They are excluded truth under the current request.

Do not conflate:

```text
complete admitted result
```

with:

```text
all structurally stored assertions regardless of authorization
```

### 6.10 Partial/incomplete behavior

Prefer implementations with no arbitrary complete-entity cap.

If a real integrity/resource condition can prevent full assembly, it must not silently return `complete`.

Acceptable choices:

- fail the operation closed with a dedicated deterministic error; or
- return explicit `partial` / `incomplete` with a closed reason vocabulary and actual counts.

Do not invent arbitrary relationship/evidence limits merely to create a partial path.

If partial is introduced, tests must prove:

- it cannot be mistaken for complete;
- reason is deterministic and non-sensitive;
- no hidden source diagnostics leak;
- ordinary application defaults do not trigger it.

### 6.11 No fake `ProjectionSnapshot`

The frozen `ProjectionSnapshot` includes mutable-head and clock-derived fields such as:

```text
head_revision_id
is_head
projected_at
```

V3 has no KnowledgeSpace/head resolver and must not fabricate these fields.

Prefer an application-level immutable read identity such as:

```text
space_id
revision_id
domain_contract_ref
semantic_profile_ref
request/result digest
```

Exact naming is implementation latitude.

A future head-aware public adapter may construct a `ProjectionSnapshot` once V7/V8-era runtime authority exists.

---

## §7 Evidence/provenance result semantics

### 7.1 Admission loads candidate support; output filters to admitted truth

V2 may load provenance needed to decide all candidates, including candidates that later fail scope/visibility/domain policy.

V3 must not expose source/evidence metadata merely because V2 loaded it.

Public/entity-read output is filtered to support referenced by **returned admitted assertions only**.

For each returned assertion:

```text
assertion_id
→ parsed.assertion_evidence[assertion_id]
→ exact ParsedEvidenceRef records
→ validated artifact/revision identity from the same coherent V2 source view
```

Do not expose sources that are used only by excluded assertions.

### 7.2 Reuse the same coherent V2 provenance view

Ideal V3 shape:

```text
candidate IDs
→ V2 admission evaluation
   returns/retains sealed provenance snapshot internally
→ V3 filters that same snapshot to admitted assertion support
→ result
```

If the current accepted `KnowledgeReadContext.admit_candidates()` does not expose the internal sealed snapshot needed for result assembly, a **bounded internal V2 extension** is permitted, for example an internal evaluation record containing:

```text
CandidateAdmissionResult
+ KnowledgeProvenanceSnapshot
```

provided that:

- existing public `admit_candidates()` behavior remains unchanged;
- the snapshot remains deeply immutable;
- domain policy semantics do not change;
- request/source identity checks remain exact;
- V3 never returns the unfiltered whole candidate snapshot directly to callers.

A second targeted lookup against the same pinned coherent source view may be acceptable only if the implementation proves it observes the same authority epoch and its extra cost is explicitly counted. Prefer reuse over duplicate work.

Multiple ordinary live source reads without a shared coherence boundary are not acceptable.

### 7.3 What counts as V3 evidence/anchor material

V3 must return all direct support metadata promised for its returned assertions from the existing vNext evidence model, including locator-bearing fields already present on `EvidenceRefV3` / normalized evidence records.

That can include exact fields such as:

```text
source_artifact_id
source_revision_id
evidence_role
locator
uri
source_locator
line_ref
source_span_ref_id
domain_metadata
```

and validated source artifact/revision identity as needed by the result DTO.

Do not add a standalone `resolve_source_anchor()` API in V3. V4 owns generic evidence/anchor lookup operations and supporter traversal.

If product-complete entity truth requires an anchor abstraction that cannot be represented from returned assertion evidence plus the already validated source snapshot, stop and identify the missing V4-level contract instead of smuggling a new anchor subsystem into V3.

### 7.4 Source freshness is unchanged

V3 may reuse the immutable parsed revision across requests.

It may not reuse a source-admission/result verdict by revision alone.

Required proof:

```text
context A created at source authority state A
source authority changes
context A remains coherent to A
context B created from same ParsedKnowledgeRevision observes source authority state B
```

No entity-read cache may erase that distinction.

---

## §8 Result contract direction

Do not modify the frozen V0 wire bundle merely to expose V3 application results.

Prefer immutable application-layer DTOs/records.

Illustrative shape only:

```python
@dataclass(frozen=True, slots=True)
class EntityReadIdentity:
    space_id: str
    revision_id: str
    domain_contract_ref: ...
    semantic_profile_ref: ...

@dataclass(frozen=True, slots=True)
class EntityReadCompleteness:
    status: Literal["complete", "partial"]
    reason: str | None = None
    # complete requires reason is None
    # partial requires a closed reason from {support_unavailable, result_truncated}


@dataclass(frozen=True, slots=True)
class EntityReadWorkCounts:
    entity_lookups: int
    subject_assertion_candidates: int
    incoming_entity_ref_candidates: int  # incoming assertion IDs, not neighbor entity IDs
    outgoing_entity_ref_candidates: int  # outgoing assertion IDs, not neighbor entity IDs
    deduped_candidate_assertions: int
    endpoint_entity_lookups: int
    evidence_ids_returned: int
    artifact_ids_requested: int
    revision_ids_requested: int
    provenance_snapshot_calls: int

@dataclass(frozen=True, slots=True)
class EntityLookupResult:
    identity: EntityReadIdentity
    found: bool
    entity: ... | None
    assertions: tuple[...]
    evidence: tuple[...]
    completeness: EntityReadCompleteness
    work: EntityReadWorkCounts
    result_digest: str

@dataclass(frozen=True, slots=True)
class CompleteEntityLookupResult(EntityLookupResult):
    related_entities: tuple[...]
```

Names and exact factoring are not binding.

Binding requirements are:

- immutable externally reachable state;
- exact identity;
- deterministic ordering;
- deterministic content digest;
- explicit completeness;
- actual structural work accounting;
- no mutable internal parsed/provenance backing leaked to callers.

### Digest rule

The result digest must bind semantic returned content, not benchmark timings.

At minimum bind:

```text
space_id
revision_id
entity_id
found
returned assertion semantic content or exact assertion IDs under the exact immutable revision
related endpoint IDs
returned evidence/support identity and locator content
completeness status/reason
```

If the result includes mutable source metadata whose content may change while the knowledge revision remains fixed, include the **returned** source artifact/revision fields in the result digest (`source_artifact_id`, `status`, `current_revision_id`, `source_classification`, `authority`, and returned revision `content_sha256`). Do not bind the fingerprint of the whole candidate provenance snapshot. Hidden/excluded candidate provenance must not change a visible result digest.

Work counts and elapsed timing should not affect the semantic digest.

---

## §9 Structural cost model — review must be obvious from code

### 9.1 `get_entity`

Target structural work:

```text
1 exact entity lookup
+ len(assertions_by_subject[E]) candidate IDs
+ candidate evidence dependencies
+ candidate-local source records
+ admission/result assembly
```

Unrelated entities/assertions/evidence/sources must not be visited merely because they are in the same revision.

### 9.2 `get_complete_entity`

Target structural work:

```text
1 exact entity lookup
+ subject assertion IDs
+ incoming entity-ref assertion IDs
+ outgoing entity-ref assertion IDs
+ deterministic deduplication
+ candidate-local evidence/source records
+ endpoint lookups for admitted touching entity-ref assertions
+ admission/result assembly
```

No full `assertions_by_id` iteration is allowed as the normal implementation.

No full `entities_by_id` iteration is allowed as the normal implementation.

No full `evidence_by_id` iteration is allowed as the normal implementation.

No full source-store snapshot is allowed.

### 9.3 Candidate discovery before admission

Do not admit the whole revision and then select the entity.

The order is binding:

```text
structural candidate discovery
→ candidate admission
→ result assembly
```

not:

```text
full admission/projection
→ slice entity
```

### 9.4 Endpoint lookups happen after touching assertion admission

Do not resolve endpoints for hidden/excluded touching assertions merely because they were structural candidates.

Preferred order:

```text
structural touching candidate IDs
→ admission
→ admitted touching assertions
→ opposite endpoint IDs
→ exact endpoint lookups
```

This prevents unnecessary work and accidental endpoint-identity exposure through the result.

---

## §10 Required semantic fixtures and witnesses

### 10.1 Organizational-memory native fixture

Use the existing non-TTRPG organizational-memory domain as the primary genericity witness.

Required cases:

- exact known entity;
- exact missing entity;
- entity with multiple literal/term/entity-ref subject assertions;
- incoming entity-ref from another entity;
- domain policy exclusion;
- source visibility/lifecycle exclusion;
- source change between contexts.

### 10.2 Buddy-shaped opaque fixture

Use only generic opaque terms already established by V2, such as:

```text
dungeonbuddy.scope:campaign
dungeonbuddy.visibility:player
dungeonbuddy.visibility:gm
```

Required proof:

- PLAYER-shaped audience excludes GM-only assertion;
- GM-shaped audience includes both player and GM assertions when otherwise admissible;
- exact campaign request excludes another-campaign touching assertion;
- wildcard campaign scope can admit touching assertions from multiple campaigns;
- a hidden touching relationship does not leak its opposite endpoint through `related_entities`.

Do not import DungeonBuddy code.

### 10.3 High-degree complete entity

Fixture must include one selected entity with **more than 24 admitted touching entity-ref assertions**.

Required proof:

```text
completeness = complete
all admitted touching assertions returned
all opposite endpoints returned
no arbitrary 24-edge cap
```

Prefer at least 30–40 touching entity-ref assertions so the witness cannot accidentally sit on a historical cap boundary.

### 10.4 High-support witness

Include an entity whose returned admitted assertions collectively reference **more than 32 distinct evidence refs / locator-bearing support records** where practical.

Required proof:

- all direct returned-assertion evidence promised by V3 is present;
- no inherited 32-anchor/evidence cap defines completeness.

If the native vNext evidence model cannot express the old anchor concept one-to-one, document exactly which locator-bearing evidence fields constitute the V3 support witness and do not claim standalone V4 anchor resolution.

### 10.5 Zero-admitted-assertion entity

Create a structural entity that exists but has either:

- no assertions; or
- only assertions excluded by the request.

Prove the chosen binding contract:

```text
found = true
entity identity returned
assertions = []
```

This prevents later code from accidentally inventing entity visibility by "at least one visible assertion."

If this result is judged unsafe during review, stop and rebrief the frozen entity contract rather than changing this fixture until it passes.

---

## §11 Acceptance matrix

The exact test count is not authority. These semantic obligations are.

### A. Dispatch / authority

1. PR #60 is actually merged before V3 implementation starts.
2. V3 implementation branch is based on current `main` after that merge.
3. First V3 commit updates the Steward handoff with the real PR #60 merge SHA.
4. Steward records accepted V2 head `121419e9...`, 5 review cycles, review `5217813591`, and V2 disposition.
5. Steward records V2 benchmark artifact and structural gate.
6. Steward phase reads V2 complete / V3 active.
7. Frozen V0 aggregate remains exactly `fd04a904...`.
8. V1 semantic/compatibility digests remain stable unless an explicitly unrelated generated timing artifact changes.

### B. Exact entity read

9. Exact structural entity hit returns the selected entity.
10. Exact structural miss returns miss and performs no lexical/alias/search fallback.
11. Structurally existing entity with zero assertions returns found + empty assertion set.
12. Structurally existing entity with all assertions excluded still returns the chosen minimal structural identity + empty admitted assertion set.
13. `get_entity` candidates come only from `assertions_by_subject[entity_id]`.
14. `get_entity` does not include incoming assertions from other subjects.
15. Every subject candidate is evaluated through V2 admission.
16. Kernel-excluded assertions do not return.
17. Domain-policy-excluded assertions do not return.
18. Missing/inactive/hidden source support excludes the affected assertion according to V2 semantics.
19. Exact read result ordering is deterministic.
20. Exact read semantic digest is deterministic for the same exact authority state.

### C. Complete entity candidate discovery

21. Subject assertion IDs are included.
22. Outgoing entity-ref assertion IDs are included.
23. Incoming entity-ref assertion IDs are included.
24. Candidate IDs are deterministically deduplicated.
25. An outgoing assertion present in both subject/outgoing indexes is evaluated exactly once.
26. No full assertion scan is required to discover incoming references.
27. Self-loop touching assertion is returned once.
28. Incoming direction remains incoming; subject/value are not swapped.
29. Outgoing direction remains outgoing.
30. Non-entity-ref subject assertions remain part of the selected entity's complete subject truth.

### D. Endpoint semantics

31. Every admitted touching entity-ref assertion has its opposite endpoint entity returned.
32. Excluded touching assertions do not cause opposite endpoint disclosure in result.
33. Endpoint lookup uses exact `entities_by_id` identity.
34. No endpoint lexical/alias fallback.
35. Self-loop does not duplicate selected entity in related endpoints.
36. Related endpoints are deterministically ordered/deduplicated.
37. Endpoint subject assertions are not recursively expanded.
38. A structurally dangling admitted entity-ref is fail-closed corruption, never a `complete` dangling result.

### E. Completeness

39. Low-degree complete entity reports complete.
40. >24 touching-assertion entity returns all admitted touching assertions and reports complete.
41. Ordinary historical/product relationship caps do not affect V3 completeness.
42. All required related endpoint entities are present for a complete result.
43. Excluded assertions do not make completeness partial.
44. If a partial/incomplete result type exists, it has deterministic explicit reason and cannot be confused with complete.
45. No pagination/truncation occurs behind `complete`.
46. No client-side fragment union is required to recover selected-entity truth promised by the contract.

### F. Evidence / provenance

47. Returned assertion evidence is derived only from returned admitted assertions.
48. Evidence loaded solely for excluded candidates is not exposed in the result.
49. Exact evidence identity is preserved.
50. Exact source artifact/revision identity is preserved where returned.
51. Locator-bearing evidence metadata survives unchanged.
52. >32 direct support records are not silently truncated where the fixture exercises them.
53. One entity-read operation uses one coherent source authority epoch.
54. Prefer one provenance snapshot; any second targeted snapshot is same-epoch, explicit, counted, and justified.
55. New context observes changed source authority with same parsed revision reused.
56. Existing context remains coherent to its pinned authority view.
57. No entity-read result/admission cache is keyed by revision alone.

### G. Domain/genericity

58. Organizational-memory fixture uses the same entity-read engine as Buddy-shaped fixture.
59. No `dungeonmind_dnd` import enters generic vNext application code.
60. No GM/PLAYER/campaign enums enter generic Kernel code.
61. PLAYER-shaped labels exclude GM-only assertion.
62. GM-shaped labels admit otherwise-valid player + GM assertions.
63. Exact campaign scope excludes another-campaign touching assertion.
64. Wildcard campaign scope admits all otherwise-valid campaign-scoped touching assertions.
65. Hidden/excluded touching relation does not leak endpoint identity through V3 result.
66. Focus/domain context does not silently become generic authorization.

### H. Immutability / integrity

67. Returned result state cannot mutate parsed authority.
68. Returned result state cannot mutate the pinned provenance snapshot.
69. Caller mutation of a returned DTO cannot poison a subsequent read.
70. Parsed revision mutation guards remain intact.
71. V2 sealed context/provenance mutation guards remain intact.
72. Unknown candidate/structural integrity conditions fail closed.
73. Result digest changes when semantic returned source/provenance state changes.
74. Result digest does not change merely because timing/work counters differ.

### I. Structural work / performance

75. `get_entity` work count is proportional to selected subject assertions/support.
76. `get_complete_entity` work count is proportional to selected subject + touching assertions/support/endpoints.
77. Unrelated assertion count may grow dramatically without candidate count growing for the same low-degree selected entity.
78. Unrelated source count may grow dramatically without source IDs requested growing for the same selected entity.
79. Full-space projection call count is zero.
80. Full assertion scan count is zero or proven absent by instrumentation/source guard.
81. Full evidence scan count is zero or proven absent by instrumentation/source guard.
82. Full source snapshot count is zero.
83. Relevant 10k lane records p50/p95, result digest, counts, and work shape.
84. Performance interpretation occurs only after semantic witness/digest passes.

### J. Regression / scope

85. Existing V2 candidate-admission tests remain green.
86. Existing V1 parsed revision tests remain green.
87. Existing v1-v6 compatibility parity tests remain green.
88. Frozen vNext contract generator remains exact.
89. Current World retrieval/projection behavior is unchanged.
90. No write/publication path changes.
91. No storage migration.
92. No V4 public neighborhood/evidence/anchor/search API lands early.

---

## §12 Performance characterization

V3 is the first phase where wall-clock point-read latency matters directly, but structural work remains the primary acceptance signal.

Create:

```text
Docs/Benchmarks/vnext_entity_reads_10k_v1.json
```

with deterministic workload generation and explicit exact base/head identities.

### Required 10k workload

Use a native vNext synthetic revision large enough to demonstrate unrelated-space scaling, for example:

```text
>= 10,000 assertions
multiple thousands of entities
candidate-local evidence/source support
one low-degree selected entity
one medium-degree selected entity
one >24-edge selected entity
```

Record at minimum for both `get_entity` and `get_complete_entity`:

```text
workload digest
parsed semantic digest
result semantic digest
selected entity ID
selected degree / subject assertion count
returned assertion count
returned related endpoint count
returned evidence/support count
candidate assertion count
assertions evaluated
policy evaluations
evidence IDs resolved
artifact IDs requested
revision IDs requested
provenance snapshot calls
endpoint lookups
p50
p95
peak memory where practical
```

### Structural scaling witness

Run the same low-degree entity shape against at least two space sizes if practical, e.g.:

```text
1k assertions
10k assertions
```

or a 10k revision with thousands of irrelevant decoy assertions/sources.

The acceptance claim is:

> unrelated space growth does not increase candidate/source work for the same selected entity shape.

A single fast timing without structural counters is insufficient.

### Directional latency target

The roadmap's target remains:

```text
10k exact entity p95 < 25 ms
```

Treat this as a directional target, not permission to weaken semantics.

If semantically correct V3 materially misses it, record the measured phase/work breakdown and identify the next low-level bottleneck. Do not introduce a storage rewrite in this PR.

100k exact entity p95 < 50 ms remains a roadmap target, but V3 acceptance does not require a fabricated 100k claim. Run 100k only if practical and report resource limits honestly.

### High-degree truth over target chasing

A >24-edge / >32-support complete result may naturally cost more than a low-degree entity. Do not truncate it to hit the low-degree latency target.

Record degree/support counts next to timing.

---

## §13 Implementation guidance

### 13.1 Prefer a small service over widening `KnowledgeReadContext`

`KnowledgeReadContext` owns pinned authority + candidate admission.

Prefer a separate V3 read service/module that orchestrates structural discovery and result assembly.

Only extend `KnowledgeReadContext` when the extension is needed to safely reuse its already-coherent provenance evaluation.

Do not turn the context into a giant retrieval facade ahead of V4.

### 13.2 Preserve V2 `admit_candidates()` behavior

If introducing an internal richer evaluation method, prefer:

```text
existing admit_candidates(ids)
  delegates to internal evaluation
  returns same CandidateAdmissionResult contract

V3 service
  calls internal evaluation
  receives admission result + sealed provenance snapshot
```

Existing V2 tests/digests must remain semantically stable.

### 13.3 Result DTOs must not expose mutable Pydantic backing

Use frozen application records or defensive fresh public copies with direct poison tests.

The V1/V2 lesson is binding:

> `frozen=True` on an outer wrapper is not sufficient if reachable nested backing remains mutable.

### 13.4 Deterministic ordering

Recommended canonical ordering:

```text
assertions          by assertion_id
related entities    by entity_id
evidence            by evidence_ref_id
source artifacts    by source_artifact_id
source revisions    by source_revision_id
exclusions/work     deterministic existing V2 ordering
```

If another ordering is chosen, document and test it.

### 13.5 Do not optimize by bypassing domain policy

All V3 candidate assertions go through the same generic + pinned-domain admission semantics accepted in V2.

Do not special-case relationship assertions as automatically visible because they are needed to connect the graph.

### 13.6 Do not optimize by pre-admitting indexes

Revision-local indexes remain purely structural.

Do not build/store:

```text
player-visible adjacency
gm-visible adjacency
campaign-admitted assertion lists
source-valid edge cache
```

inside `ParsedKnowledgeRevision`.

Those verdicts depend on request/source/domain state and are not safe by immutable revision alone.

---

## §14 Quality gates

At minimum run:

```bash
uv sync

uv run pytest -q tests/unit/test_vnext_entity_reads.py
uv run pytest -q tests/unit/test_vnext_knowledge_read_context.py
uv run pytest -q tests/unit/test_vnext_parsed_knowledge_revision.py
uv run pytest -q tests/unit/test_vnext_legacy_compatibility.py

uv run pytest -q
uv run pytest -m conformance

uv run ruff check .
uv run pyright
uv run python scripts/generate_vnext_contract_bundle.py --check

git diff --check
```

Run the repository CI workflow on the exact review head.

### Known inherited CI debt

PR #60 inherited the pre-existing `benchmark-smoke` World-path failure originating before V2.

It may remain non-blocking in V3 **only if** the exact failure remains the same inherited baseline and V3 does not touch that path.

If the benchmark-smoke error signature changes, or V3 modifies the affected current World read path, investigate rather than inheriting the waiver automatically.

---

## §15 Stop / rebrief conditions

Stop and report rather than compensating locally if any of the following occurs:

1. V3 requires changing the frozen V0 contract bundle.
2. V3 cannot safely define structural entity-found semantics because product requirements demand entity-level visibility absent from the frozen `Entity` contract.
3. Exact entity lookup requires mutable head resolution or KnowledgeSpace persistence.
4. Exact/complete entity reads require full-space projection for correctness.
5. Incoming touching assertions cannot be enumerated losslessly from the accepted V1 indexes.
6. A correct complete result requires scanning every assertion/evidence/source record.
7. V3 would need a pre-admitted/scoped index cached by revision alone.
8. Domain policy would need to be bypassed for relationship completeness.
9. Opposite endpoint identity cannot be returned without recursively exposing unauthorized endpoint truth.
10. Returning native `IdentityAlias` requires inventing alias visibility/admission semantics not proven in V2.
11. Required evidence/support cannot be assembled from the same coherent V2 authority view.
12. A standalone anchor-resolution contract is required to satisfy V3; that belongs to V4.
13. An arbitrary relationship/assertion/evidence cap is required but result would still be called complete.
14. A PostgreSQL/schema/storage migration appears necessary.
15. A DungeonBuddy/TTRPG dependency must enter generic vNext code.
16. Current World public reads must change to prove V3.
17. Historical compatibility semantics/readers must change.
18. V2 candidate-admission semantic digests or source-freshness behavior must weaken.
19. Performance only passes by dropping valid admitted assertions/evidence/endpoints.
20. A result DTO can poison later reads through reachable mutable backing.

Required stop report:

```text
Stop condition:
Roadmap phase: V3
Observed evidence:
Selected entity/workload:
Which accepted V0/V1/V2 assumption failed:
Affected authority/architecture document:
Why V3 cannot safely compensate locally:
Proposed design decision / experiment:
What remains safe in parallel:
V4 state:
```

If the stop condition changes contracts, ownership, or roadmap ordering, update canonical architecture/roadmap before implementation resumes.

---

## §16 Required handback

The implementation handback must contain:

```text
repository
implementation branch
actual base SHA
actual PR #60 merge SHA
first Steward bookkeeping commit SHA
exact implementation head SHA
PR number/title/status
logical review-cycle count so far
```

Then provide:

### Changed surface

- cumulative changed-file list;
- exact public/application operation names;
- exact result record names;
- whether `KnowledgeReadContext` gained any internal richer evaluation seam;
- confirmation frozen V0 contracts were unchanged.

### Semantic witnesses

- exact hit;
- exact miss;
- zero-admitted-assertion entity;
- low-degree entity;
- >24 touching assertion complete entity;
- >32 direct support witness if implemented;
- incoming/outgoing/self-loop witness;
- endpoint completeness witness;
- hidden relationship does not expose endpoint;
- organizational-memory witness;
- Buddy-shaped PLAYER/GM/campaign/wildcard witness.

### Provenance/coherence witnesses

- one-read snapshot count;
- returned evidence/support count;
- source freshness context A/B proof;
- same-context coherence proof;
- proof excluded-candidate source metadata is not returned.

### Determinism / integrity

- result digest(s);
- repeated-read equality;
- mutation-poison regressions;
- no full-scan/full-projection proof.

### Performance

- benchmark artifact path;
- workload digest;
- parsed semantic digest;
- exact/complete p50/p95;
- candidate/source/endpoint work counts;
- memory observation if practical;
- whether 10k directional target was met;
- any 100k run, only if actually executed.

### Verification

- focused tests;
- broad unit/conformance tests;
- Ruff;
- Pyright;
- frozen contract bundle check;
- CI run ID and job conclusions;
- exact inherited benchmark-smoke classification if still present;
- `git diff --check`.

### What remains false

Explicitly state at least:

```text
no V4 neighborhood API
no standalone evidence API
no standalone anchor API
no deterministic search API
no KnowledgeSpace/head storage runtime
no native vNext writes
no Buddy runtime domain cutover
no bridge genesis
no V8 acceptance
no V9 cutover
no V10 historical-reader quarantine
```

### Successor

If V3 passes, name V4 explicitly:

> **V4 — bounded neighborhood + exact evidence/anchor support + deterministic indexed search.**

The next Steward primary question should begin with the first V4 slice, preferably bounded neighborhood:

> **Can depth-1/depth-2 traversal discover only visited entities/assertions plus their authority support using revision-local adjacency and the accepted V2 admission seam, without full-space projection?**

---

## §17 PR description template

Use these headings in the implementation PR:

```text
Primary question
Base / predecessor identity
Steward bookkeeping
Changed surface
Exact entity semantics
Complete entity semantics
Evidence / provenance semantics
Completeness proof
Genericity / domain witnesses
Structural work evidence
Performance characterization
Regression / CI evidence
Known inherited failures
What remains false
Successor
```

Do not claim V3 acceptance in the PR body before Steward review records:

```text
V3_LAZY_EXACT_COMPLETE_ENTITY_READS_ACCEPTED
```

---

## §18 Reviewer focus

The Steward review should inspect hardest for these failure modes:

1. **Full-space work hidden behind a helper.** Search for iteration over all assertions/entities/evidence/sources in the normal exact/complete path.
2. **Admission after projection.** Candidate discovery must happen before V2 admission, not after whole-space admission.
3. **Relationship bypass.** Touching entity-ref assertions must still pass ordinary V2 scope/visibility/source/domain admission.
4. **Endpoint leak.** Hidden/excluded relationships must not cause opposite endpoint IDs to appear in returned related entities.
5. **Fake entity visibility.** Retrieval must not invent a domain predicate or "visible if any assertion" rule.
6. **Fake ProjectionSnapshot.** No guessed head ID / `is_head` / wall-clock `projected_at`.
7. **Alias widening.** Native aliases must not be dumped into results without an accepted alias-admission rule.
8. **Second authority path.** Evidence/source output must not perform incoherent live reads outside the pinned V2 source view.
9. **Excluded-source leakage.** Candidate provenance used for authorization must be filtered before result output.
10. **Completeness by cap.** No 24/32/etc. ceiling may define a result labeled complete.
11. **Recursive endpoint expansion.** Complete selected entity is not an accidental V4 neighborhood projection.
12. **Revision-only result caching.** Source authority freshness must survive.
13. **Mutable result backing.** Caller-accessible internals must not poison subsequent reads.
14. **Benchmark theater.** Verify work counts and semantic digest before interpreting latency.
15. **V4 creep.** No neighborhood/search/standalone anchor API just because nearby helpers are convenient.

---

## §19 Disposition vocabulary

Use exactly:

```text
V3_HOLD
V3_REBRIEF_REQUIRED
V3_LAZY_EXACT_COMPLETE_ENTITY_READS_ACCEPTED
```

Only the final accepted disposition unlocks V4 merge.
