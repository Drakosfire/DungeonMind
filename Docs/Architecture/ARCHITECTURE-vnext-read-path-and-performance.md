# DungeonMind vNext — Read Path and Performance Architecture

**Status:** canonical companion to `ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`  
**Design anchor:** DungeonMind `main` after PR #53 (`ccd9327e9e2b47b2f046b661b9aedc0a9f3e5895`)  
**Purpose:** bind the vNext implementation to the performance lessons already proven by R.2a, R.3a, and complete-object retrieval without turning the breaking redesign into a speculative storage rewrite.

## Executive decision

The vNext genericization and the next read-path optimization wave should be executed together where they touch the same architectural seam.

The semantic architecture says:

> DungeonMind should stop requiring World-specific projection semantics for every knowledge read.

The performance evidence says:

> DungeonMind should stop requiring whole-graph projection and admission for every bounded read.

Those are the same structural problem from two directions.

Therefore vNext must preserve immutable revision authority while making bounded reads proportional to the requested knowledge rather than to the entire KnowledgeSpace.

The target read shape is:

```text
exact immutable revision
→ immutable normalized revision model
→ revision-local candidate/index lookup
→ targeted coherent provenance load
→ generic scope / visibility / standing admission
→ domain admission
→ bounded result
```

Full-space projection remains valid and explicit:

```text
exact immutable revision
→ admit the complete revision
→ O(N) projection result
```

It must no longer be the compulsory precursor to `get_entity`, `get_complete_entity`, evidence, anchor, bounded neighborhood, or deterministic search.

---

## 1. Evidence already earned

### 1.1 R.2a identified whole-projection cost as the structural floor

`Docs/Benchmarks/BASELINE-world-graph-reads-r2a.md` measured the original direct read path.

At 10k objects:

```text
project_head             ~6.74 s
get_object               ~6.97 s
neighborhood depth-1     ~7.07 s
get_evidence             ~6.90 s
resolve_source_anchor     ~9.51 s
search                    ~9.95 s
peak traced memory        ~318 MiB for ordinary reads
```

The important result was not the exact laptop timing. It was the work shape:

> full projection was almost the entire cost of a bounded point read.

Search and anchor resolution then added additional graph-size-dependent work on top.

### 1.2 R.3a proved ordinary structural optimization can preserve semantics

`Docs/Benchmarks/BASELINE-world-graph-reads-r3a.md` and `Docs/Handoffs/HANDOFF-cutover-direct-read-optimization.md` established:

- one coherent `WorldGraphReadContext` per public read;
- service-local immutable revision parse reuse;
- one coherent batched `SourceProvenanceSnapshot`;
- per-context evidence memoization;
- no scoped cross-request authorization cache;
- no Redis or distributed cache;
- no search/anchor index;
- exact semantic digest parity with the predecessor benchmark.

Live Eldyrwild campaign-GM projection improved from approximately 20.7 seconds to approximately 115 ms warm, primarily by eliminating per-evidence PostgreSQL N+1 reads.

The safety lesson is binding:

> parsed immutable revision state may be reused by exact revision identity and parse compatibility; admitted/scoped knowledge may not be cached by revision alone because source/provenance authority can change while the graph revision remains fixed.

### 1.3 R.3a also exposed the next ceiling

After the large live N+1 win, the synthetic 10k ladder still measured roughly:

```text
project_head             2.32 s
get_object               2.18 s
neighborhood depth-1     2.27 s
get_evidence             2.06 s
resolve_source_anchor     4.00 s
search                    5.24 s
```

That is sufficient evidence to reject the current work shape for vNext point reads.

### 1.4 Complete-object retrieval sharpened the product requirement

`Docs/Handoffs/HANDOFF-complete-selected-object-one-hop-read.md` established a separate correctness requirement:

> a selected entity can require a complete admitted one-hop view whose truth is not defined by generic result caps.

The accepted current implementation still uses the World read context and can be fast enough at Eldyrwild scale, but it explicitly leaves a successor if object-centric latency must improve further.

vNext should make that successor a natural consequence of the normalized revision model rather than another product-specific read path.

---

## 2. Governing optimization rule

> **Reduce structural work before adding infrastructure.**

Optimization order:

```text
1. avoid unnecessary work
2. avoid loading unnecessary data
3. avoid unnecessary copies / allocations
4. add immutable derived indexes
5. optimize serialization / hashing
6. change durable authority storage only if the preceding steps are insufficient
```

The following are not authorized merely because vNext is breaking:

- Redis;
- distributed caches;
- a process-global parse singleton;
- cross-request caches of admitted/scoped results keyed only by revision;
- Neo4j or another graph database by fashion;
- event sourcing;
- structural-sharing revision trees;
- vector search as a default serving path;
- a second authority model for fast reads.

---

## 3. One immutable normalized revision model

The current v1-v6 readers already normalize historical stored graph generations into a parsed graph snapshot.

vNext should make this concept explicit and generic:

```text
ParsedKnowledgeRevision
  space_id
  revision_id
  domain_contract_ref
  semantic_profile_ref

  entities_by_id
  assertions_by_id
  evidence_by_id

  assertions_by_subject
  entity_adjacency
  evidence_supporters
  assertion_evidence

  exact_label_index
  alias_index
  lexical_candidate_index
```

Names are illustrative; responsibilities are binding.

This model is derived from an immutable revision and is not a second authority.

### 3.1 Derived indexes are revision-local

The following are safe to derive and reuse for an exact immutable revision:

```text
entity ID lookup
assertion ID lookup
subject → assertion IDs
entity-ref adjacency
assertion → evidence refs
evidence ref → supporter assertion IDs
exact label / alias lookup
deterministic lexical candidate lookup
```

The index identity must include everything that changes parse meaning, including the pinned semantic-profile/domain-contract compatibility identity.

### 3.2 Internal normalized records should be immutable

R.3a must defensively isolate mutable parsed Pydantic models from cache poisoning.

vNext should prefer genuinely immutable internal records for the normalized revision representation.

Conceptually:

```text
durable contract payload
→ parse / verify once
→ immutable internal revision model
→ read operations
→ public result DTOs
```

Public Pydantic models remain acceptable. Repeated deep-copying of the internal authority representation should not be the default isolation mechanism when immutability can provide the same safety more directly.

---

## 4. Generic `KnowledgeReadContext`

The vNext read context must not mean "fully projected KnowledgeSpace."

It means:

```text
KnowledgeReadContext
  exact revision identity
  parsed immutable revision
  scope selector
  effective audience labels
  standing selector
  focus/domain context
  pinned DomainContract
  pinned SemanticProfile
  source/evidence repository access
  per-context provenance/evidence memo
```

It supplies coherent admission for whatever candidate slice an operation needs.

### 4.1 Safe reuse

Safe to reuse across requests when keyed exactly:

```text
parsed immutable revision
revision-local adjacency/indexes
revision-local lexical candidate index
revision-local support indexes
```

### 4.2 Not safe to reuse by graph revision alone

Do not cross-request cache:

```text
scope-admitted projection
visibility result
source-authority verdict
domain-admission verdict
```

Source lifecycle and provenance state remain live authority inputs unless a later explicit AuthorityView design freezes them.

---

## 5. Lazy candidate admission

Bounded reads should select structural candidates before expensive admission.

### 5.1 Exact entity

Target work shape:

```text
entities_by_id[entity_id]
→ assertions_by_subject[entity_id]
→ candidate evidence/source IDs
→ coherent targeted provenance snapshot
→ scope / visibility / standing checks
→ domain admission
→ result
```

Complexity goal:

```text
O(1) / O(log N) structural lookup
+ work proportional to returned entity assertions and evidence
```

not O(N) full projection.

### 5.2 Complete entity

`get_complete_entity(entity_id)` is the first preferred witness for the architecture because it exercises:

- exact identity;
- all selected-entity assertions;
- entity-reference adjacency;
- opposite endpoints;
- evidence;
- anchors;
- scope;
- visibility;
- standing;
- domain admission;
- completeness semantics.

Target work shape:

```text
entity
→ all subject assertions
→ all touching entity-ref assertions
→ required endpoint entities
→ required evidence/source IDs
→ targeted coherent provenance
→ admission
→ complete result
```

No generic 12/24/32/32 cap may define the truth of a result labeled complete.

### 5.3 Bounded neighborhood

Use `entity_adjacency` to discover depth-1/depth-2 candidate sets.

Admission happens on the bounded candidate slice.

Full-space traversal is not required to discover a handful of neighbors.

### 5.4 Evidence and anchors

Use exact support indexes:

```text
assertion → evidence refs
evidence ref → supporter assertions
```

Anchor emit/revalidation should walk the relevant support chain, not rediscover every supporter from the whole graph.

---

## 6. Search candidate generation before admission

R.2a/R.3a show deterministic lexical search carries a separate graph-size-dependent cost after projection.

The first vNext search index should remain deliberately simple and deterministic:

```text
exact entity ID
normalized label
normalized alias
token → candidate entity/assertion IDs
predicate/qualified term → candidates
```

Read shape:

```text
query
→ deterministic candidate IDs
→ bounded ranking
→ candidate evidence/provenance
→ generic/domain admission
→ result
```

Do not begin with vector retrieval.

Escalation order if measured search remains inadequate:

```text
1. revision-local in-memory lexical index
2. deterministic FTS/BM25-derived candidate index
3. optional vector candidate source only with demonstrated workload value
```

Search ranking never becomes authority.

---

## 7. Provenance loading

R.3a proved that coherent batched provenance is essential and that the repository already supports ID-targeted snapshot loading.

For bounded reads, collect the required source artifact/revision IDs from the candidate slice and request only those records coherently.

The semantics remain fail closed:

- missing source IDs stay missing;
- stale/incompatible authority cannot be broadened by retrieval;
- one read must not stitch mutually inconsistent source states together.

A full-space projection may still request a full relevant provenance snapshot.

---

## 8. Write-path optimization boundary

The vNext contribution redesign should take the obvious low-cost wins:

- typed contribution-item discriminated unions;
- native canonical JSON assertion values instead of JSON encoded inside strings;
- parse/validate once where possible;
- avoid unnecessary model copies;
- canonical serialize/hash once per required authority artifact;
- retain exact-parent CAS and replay/recovery semantics.

Do **not** redesign durable revision storage merely because the current materializer reconstructs a full child snapshot.

Before any change to snapshot persistence, characterize:

```text
large immutable parent
+ one tiny accepted change
```

Measure:

```text
parent load
materialization / validation
canonical serialization
hashing
bytes written
total publication latency
```

Only if those measurements remain unacceptable after the vNext representation cleanup may a later lane evaluate structural sharing, immutable change records, checkpoints, or another physical representation.

Logical immutable revision semantics remain binding regardless of physical storage.

---

## 9. Performance acceptance

Absolute laptop timing is evidence, not authority.

Every performance PR must prove semantic parity first.

Minimum reporting:

```text
exact base/head
workload identity / fixture digest
semantic digest
result cardinality
p50 / p95 where statistically meaningful
memory observation
repository/query/work counts where practical
```

Structural work reduction is more important than a single wall-clock result.

The earlier reconstruction roadmap proposed these attack targets for warm local/in-process reads:

```text
10k exact entity/evidence p95         < 25 ms
10k depth-1 neighborhood p95          < 50 ms
10k deterministic search p95          < 100 ms

100k exact entity p95                 < 50 ms
100k depth-1 neighborhood p95         < 100 ms
100k deterministic search p95         < 250 ms
```

These are directional targets, not permission to weaken semantics or fabricate benchmark conditions.

---

## 10. Relationship to the larger benchmark lane

The unfinished K0.3 performance-baseline work remains useful.

Its World-like / Rules-like 100 / 1k / 10k / 50k / 100k ladder should be harvested as the large-scale characterization harness where practical.

It is no longer a gate in front of vNext contract work because R.2a/R.3a already established the structural defect being corrected.

Required posture:

```text
V0 contract work may proceed immediately.
Large-scale benchmark expansion may proceed in parallel.
Before accepting V1–V4 optimization claims, run at least the relevant 10k semantic/performance lane.
Before final cutover, run the largest practical World-like and Rules-like ladder and record resource-limited cases honestly.
```

A missing 100k run is not permission to claim 100k behavior.

---

## 11. PR discipline

Do not hide the vNext migration and optimization inside one enormous implementation PR.

Each PR answers one primary question.

Preferred sequence:

```text
contract
→ normalized immutable revision
→ generic read context
→ lazy exact/complete entity
→ neighborhood/evidence/anchor
→ deterministic search
→ governed writes
→ Buddy domain implementation
→ migration
→ joint acceptance
```

Every read-path PR must make its cost model obvious in code.

A reviewer should be able to answer:

> What data does this operation load and touch as the space grows?

without reverse engineering the entire application service.

---

## 12. Binding invariants

1. Immutable revision identity survives.
2. Exact-parent CAS survives.
3. Evidence participates in validity.
4. Unknown/missing authority fails closed.
5. Retrieval never manufactures authority.
6. Domain policy may narrow Kernel-admissible knowledge, never broaden it.
7. Parsed revision/index state is derived and rebuildable.
8. Source/provenance authority remains fresh unless explicitly pinned by a future authority-view contract.
9. Full projection remains available but is explicitly O(N).
10. Bounded reads must not require full projection by design.
11. Optimization may not change semantic digests to improve timing.
12. Durable storage redesign is evidence-gated after the low-hanging structural work is exhausted.

## Architectural shorthand

```text
Authority stays immutable.
Serving becomes indexed.
Admission becomes candidate-local.
Provenance stays coherent and fresh.
Domain meaning stays outside the Kernel.
```
