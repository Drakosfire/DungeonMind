# HANDOFF — V4.1 bounded neighborhood reads

**Created:** 2026-09-16  
**Status:** ACTIVE / IMPLEMENTATION IN REVIEW / NOT ACCEPTED  
**Repository / implementation branch:** `Drakosfire/DungeonMind` / `kernel/v4-1-bounded-neighborhood`  
**Predecessor:** PR #63 — `KERNEL: V3 lazy exact and complete entity reads`  
**Accepted predecessor head:** `6c8adb474d84df6dc6e1d55cec6bedb2380e100b`  
**Predecessor final Steward review:** `5224138590`  
**Predecessor logical review cycles:** `3`  
**Predecessor disposition:** `V3_LAZY_EXACT_COMPLETE_ENTITY_READS_ACCEPTED`  
**Predecessor merge:** `c12bf89ea54af1112a0e98163aa224eb89b11c22`  
**Current implementation base:** `82a5c3e6889ad4e5648fef8f358423b5a576cb9b` — merged PR #64  
**PR #64:** merged handoff/control-surface history; **not** V4.1 runtime implementation; **not** `V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED`  
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**Roadmap phase:** V4.1 — bounded neighborhood — ACTIVE / IMPLEMENTATION IN REVIEW / NOT ACCEPTED  
**Successor:** V4.2 — standalone evidence + source-anchor support  
**One-line mission:** Turn V1 revision-local entity-ref assertion indexes, V2 candidate-local admission, and V3 exact entity semantics into deterministic depth-1/depth-2 admitted graph traversal whose work is proportional to the visited frontier and its authority support rather than the whole KnowledgeSpace.

---

## §0 Dispatch gate — bookkeeping belongs in the implementation PR

The previous V3 handoff exposed a process defect: a docs handoff merged before the living Steward had been advanced. PR #62 had to repair the durable state before V3 implementation could start.

PR #64 then repeated a different process mistake: it merged as a standalone handoff/bookkeeping PR. That is **not** the intended workflow and must not be repeated.

Correct workflow:

```text
Steward designs/writes next implementation handoff
        ↓
Code agent creates implementation branch from current main
        ↓
same implementation PR:
  bookkeeping/process update first
  implementation
  tests
  benchmark/evidence
        ↓
Steward exact-head review
        ↓
PASS + merge
```

Handoffs do not get their own PRs. Bookkeeping and handoff-state updates belong in the implementation PR.

This implementation branch therefore starts from exact current `main`:

```text
82a5c3e6889ad4e5648fef8f358423b5a576cb9b
```

and its **first commit** is bookkeeping/process repair, not neighborhood runtime. It records:

```text
current implementation base:
  82a5c3e6889ad4e5648fef8f358423b5a576cb9b

PR #64:
  merged handoff/control-surface history
  NOT V4.1 runtime implementation
  NOT V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED

V3:
  COMPLETE

V4:
  ACTIVE

V4.1:
  ACTIVE
  implementation now proceeding from current main

V4.2:
  BLOCKED ON V4.1 ACCEPTANCE

V4.3:
  BLOCKED ON V4.2 ACCEPTANCE

V5:
  BLOCKED ON V4.3 ACCEPTANCE
```

Do not start V4.1 production code in that first commit.

The technical design below remains the binding implementation brief. Do not import material from draft PR #65.

---

## §1 Outcome

A successful V4.1 leaves DungeonMind with one generic bounded neighborhood operation over an already-pinned `KnowledgeReadContext`.

Conceptually:

```text
get_neighborhood(
  context,
  seed_entity_ids,
  depth = 1 | 2,
)
```

Exact naming is implementation latitude. The semantics below are binding.

The read shape must be:

```text
exact seed IDs
→ exact structural seed lookups
→ frontier touching assertion IDs from revision-local indexes
→ candidate-local V2 admission
→ admitted entity-ref assertions only
→ exact opposite endpoint entities
→ next frontier if requested depth remains
→ deterministic bounded neighborhood result
```

The successful PR answers:

> **Can depth-1 and depth-2 neighborhood traversal discover and admit only the assertions needed for the visited frontier, with structural/provenance work proportional to visited neighborhood support rather than the whole KnowledgeSpace?**

Only successful final disposition:

```text
V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
```

Until that exact disposition is recorded by Steward review, V4.2 remains blocked from merge.

---

## §2 Why V4 is split

The canonical roadmap names V4 as:

```text
Neighborhood + evidence + anchor + deterministic indexed search
```

but it explicitly gives these separate primary questions:

```text
V4.1 bounded neighborhood
V4.2 evidence + anchor support
V4.3 deterministic indexed search
```

The repository rule remains one primary question per implementation PR.

Therefore this PR is **V4.1 only**.

Do not combine neighborhood traversal, standalone evidence/anchor APIs, and search into one implementation surface merely because they share read infrastructure.

---

## §3 Authority and required reading

Read in this order before editing code.

### 3.1 Binding architecture

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
6. `CONTRIBUTING.md`

### 3.2 Accepted V1 structural substrate

Read:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/records.py
src/dungeonmind/application/vnext/frozen_json.py
```

Relevant accepted revision-local structures now include:

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
evidence_supporters
```

V3 proved an important distinction:

```text
entity_ref_outgoing[E] / entity_ref_incoming[E]
  = neighbor entity IDs

entity_ref_outgoing_assertions[E] / entity_ref_incoming_assertions[E]
  = touching entity-ref assertion IDs
```

Traversal authority must be established through admitted assertions, not raw neighbor IDs.

### 3.3 Accepted V2 admission seam

Read:

```text
src/dungeonmind/application/vnext/read_context.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/provenance.py
src/dungeonmind/application/vnext/ports.py
src/dungeonmind/application/vnext/errors.py
tests/unit/test_vnext_knowledge_read_context.py
Docs/Benchmarks/vnext_candidate_admission_10k_v1.json
```

Reuse exactly:

- exact revision/request/domain/profile pinning;
- generic standing/scope/visibility/domain-declaration/profile checks;
- candidate-local source/evidence dependency collection;
- one pinned coherent source-authority view per context;
- source freshness across newly constructed contexts;
- pure registered domain-policy narrowing only;
- no revision-only cache of admission/source verdicts.

Do not fork authorization or provenance semantics in the traversal service.

### 3.4 Accepted V3 read seam

Read:

```text
src/dungeonmind/application/vnext/entity_reads.py
src/dungeonmind/application/vnext/__init__.py
tests/unit/test_vnext_entity_reads.py
Docs/Benchmarks/vnext_entity_reads_10k_v1.json
Docs/Handoffs/HANDOFF-v3-lazy-exact-complete-entity-reads.md
```

V3 established:

- exact structural entity existence is distinct from assertion admission;
- structural existence may be returned even when zero assertions are admitted;
- incoming/outgoing assertion indexes are the correct complete-read candidate seam;
- hidden/excluded touching assertions cannot leak endpoints;
- direct evidence/provenance support for returned assertions can be assembled without standalone evidence APIs;
- result digests bind visible returned authority, not hidden candidate provenance;
- ordinary result caps may not redefine a result labeled complete.

V4.1 should compose those lessons rather than creating another graph semantics layer.

### 3.5 Historical current-runtime neighborhood

Read the current World implementation for lessons, not API copying:

```text
src/dungeonmind/application/world_graph_retrieval.py
```

The current runtime already proves that depth-1/depth-2 BFS is useful and that explicit seed/missing/truncation coverage matters.

Do **not** import World-specific projection snapshots, campaign/GM semantics, object DTOs, or current `RetrievalBounds` into the generic vNext Kernel.

---

## §4 Primary question and write lease

### Primary question

> **Can depth-1 and depth-2 neighborhood traversal discover and admit only the assertions needed for the visited frontier, with structural/provenance work proportional to visited neighborhood support rather than the whole KnowledgeSpace?**

### Expected write lease

Primary production surface:

```text
src/dungeonmind/application/vnext/
  neighborhood.py          # preferred illustrative name
  __init__.py              # narrow exports
  errors.py                # only bounded traversal-specific integrity errors
```

Bounded internal refactor is allowed in:

```text
entity_reads.py
read_context.py
admission.py
```

only if needed to reuse accepted support/digest helpers without copying semantics.

Tests:

```text
tests/unit/test_vnext_neighborhood.py
```

Fixtures may extend:

```text
tests/fixtures/vnext/
```

Benchmark:

```text
benchmarks/vnext_neighborhood_10k.py
Docs/Benchmarks/vnext_neighborhood_10k_v1.json
```

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

If a frozen V0 contract change appears necessary, stop and rebrief.

---

## §5 Binding traversal semantics

### 5.1 Caller supplies one already-pinned context

Preferred shape:

```python
service.get_neighborhood(
    context,
    seed_entity_ids=(...),
    depth=1,
)
```

The neighborhood service does not resolve mutable heads, load revisions, choose profiles/contracts, or create a second authority context.

### 5.2 Exact opaque seeds only

Seed IDs are exact stable entity IDs.

No fallback to:

```text
alias
label
substring
lexical token
search
nearest match
```

For each caller-supplied seed:

- exact structural hit → returned seed at depth 0;
- exact structural miss → explicit missing seed;
- an existing seed with zero admitted traversal edges remains a returned depth-0 entity.

Missing IDs are safe to echo because they were caller supplied.

### 5.3 Requested depth is exactly 1 or 2

V4.1 supports only:

```text
depth = 1
depth = 2
```

Reject 0, negative, >2, non-integral, or ambiguous depth input rather than silently coercing it.

Depth is the minimum number of **admitted entity-ref assertions** on a path from any returned seed:

```text
seed entity                   depth 0
one admitted edge away        depth 1
two admitted edges away       depth 2
```

Raw structural adjacency is not an admitted path.

### 5.4 Frontier candidate discovery

For each frontier entity `E`, discover touching candidate assertion IDs only from revision-local assertion indexes:

```text
entity_ref_outgoing_assertions[E]
entity_ref_incoming_assertions[E]
```

The implementation may expose a small helper such as:

```text
get_touching_entity_ref_assertion_ids(E)
```

if that makes the work shape clearer, but the underlying data remains derived/rebuildable V1 state.

Do not:

- scan all assertions;
- scan all subject assertions of neighbor entities;
- traverse `entity_adjacency` and assume those edges are admitted;
- pre-project the entire space.

### 5.5 Admission defines traversability

Candidate touching assertions must pass the accepted V2 admission seam.

Only an **admitted** entity-ref assertion becomes a traversal edge.

Therefore:

```text
structural edge exists + hidden              → not traversable
structural edge exists + out of scope        → not traversable
structural edge exists + invalid source      → not traversable
structural edge exists + domain excluded     → not traversable
structural edge exists + admitted            → traversable
```

An excluded edge must not disclose or enqueue its opposite endpoint.

### 5.6 BFS algorithm shape

Conceptually:

```text
visited = existing exact seeds at depth 0
frontier = those seeds
evaluated_assertion_ids = ∅
returned_traversal_assertions = ∅

for layer in 1..requested_depth:
    candidate_ids = touching assertion IDs for all frontier entities
    candidate_ids -= evaluated_assertion_ids
    deterministic dedupe/sort

    evaluate candidate_ids through V2 once for this frontier batch
    evaluated_assertion_ids += candidate_ids

    for each admitted entity-ref assertion:
        return the assertion
        derive exact opposite endpoint relative to the expanded frontier entity
        return endpoint entity
        assign minimum depth if first discovered

    next_frontier = entities first discovered at this layer
    frontier = next_frontier
```

Implementation details may differ, but the observable work shape must remain frontier-local.

### 5.7 Depth-2 stopping rule

For a depth-2 request:

```text
expand depth-0 seeds
expand newly discovered depth-1 entities
STOP
```

Do not expand depth-2 entities merely to collect their outgoing/incoming edges.

This must have an adversarial witness:

> a depth-2 entity may own or touch thousands of additional edges; a depth-2 request must not evaluate them because doing so would be depth 3 work.

### 5.8 Cycles, converging paths, and self-loops

The result must terminate and remain deterministic under:

```text
A → B → A
A → B → C → A
A → A
A → C
B → C
multiple seeds reaching the same C
```

Rules:

- evaluate each candidate assertion ID at most once per operation;
- return each admitted traversal assertion once;
- return each entity once;
- entity depth is the minimum admitted path distance from any returned seed;
- a self-loop is a returned admitted edge but does not create another entity/frontier entry;
- seed order must not change semantic output.

### 5.9 Direction is preserved

Traversal is graph-neighborhood discovery, not relationship rewriting.

Returned `ParsedAssertion` values preserve their exact stored direction:

```text
subject_entity_id
predicate
EntityRefValue(entity_id=target)
```

The implementation may traverse an incoming assertion from target to source for BFS discovery, but it must not swap or normalize the assertion direction in the returned record.

### 5.10 What V4.1 returns

Minimum required immutable result:

```text
exact read identity
requested seed IDs
found seed IDs
missing seed IDs
requested depth
entity → minimum depth
returned structural entities
admitted traversal entity-ref assertions
direct evidence/source support required by those returned assertions
explicit completeness/coverage
structural work counts
semantic result digest
```

Illustrative shape:

```python
@dataclass(frozen=True, slots=True)
class NeighborhoodReadIdentity:
    space_id: str
    revision_id: str
    domain_contract_id: str
    domain_contract_revision: str
    semantic_profile_id: str
    semantic_profile_revision: str

@dataclass(frozen=True, slots=True)
class NeighborhoodWorkCounts:
    seed_entity_lookups: int
    frontier_entities_expanded: int
    touching_assertion_candidates: int
    deduped_candidate_assertions: int
    assertions_evaluated: int
    policy_evaluations: int
    endpoint_entity_lookups: int
    evidence_ids_returned: int
    artifact_ids_requested: int
    revision_ids_requested: int
    provenance_snapshot_calls: int

@dataclass(frozen=True, slots=True)
class NeighborhoodResult:
    identity: NeighborhoodReadIdentity
    requested_seed_entity_ids: tuple[str, ...]
    found_seed_entity_ids: tuple[str, ...]
    missing_seed_entity_ids: tuple[str, ...]
    requested_depth: Literal[1, 2]
    entity_depths: tuple[tuple[str, int], ...]
    entities: tuple[ParsedEntity, ...]
    traversal_assertions: tuple[ParsedAssertion, ...]
    evidence: tuple[ParsedEvidenceRef, ...]
    source_artifacts: tuple[...]
    source_revisions: tuple[...]
    completeness: ...
    work: NeighborhoodWorkCounts
    result_digest: str
```

Exact names/types may differ.

Do not expose mutable dict/list backing merely because `entity_depths` is naturally map-shaped.

### 5.11 Neighborhood truth is not complete-entity truth

A V4.1 neighborhood result is complete **for bounded traversal**, not a claim that every fact about every visited entity has been returned.

The minimum V4.1 result does not need to recursively call `get_complete_entity` for every visited entity.

Do not inflate V4.1 into:

```text
complete entity read × every neighbor
```

because that obscures the traversal cost model and risks duplicated admission/provenance work.

If the implementation includes additional admitted subject facts for visited entities, they must be:

- clearly separated from traversal assertions;
- candidate-local;
- unable to expand traversal beyond requested depth;
- included in work accounting and semantic digest.

They are not required for V4.1 acceptance.

### 5.12 Direct support may be returned; standalone support APIs remain V4.2

Like V3, V4.1 may return direct `EvidenceRef` / source artifact / source revision information already required to justify returned traversal assertions.

That does not authorize:

```text
get_evidence(target)
resolve_source_anchor(anchor_id)
search anchors
open source bodies
```

Those belong to V4.2 or the client.

### 5.13 One coherent authority epoch

All frontier admission within one neighborhood operation must use the caller's one pinned `KnowledgeReadContext`.

Depth 2 naturally requires sequential discovery:

```text
admit depth-1 candidates
→ discover depth-1 endpoints
→ discover/admit depth-2 candidates
```

It is acceptable for the V2 context to materialize one targeted provenance snapshot per frontier admission batch if those snapshots come from the same pinned coherent source view.

Do not create a fresh `KnowledgeReadContext` between layers.

Expected source-snapshot work is therefore approximately:

```text
depth 1 → at most one candidate-admission snapshot batch
depth 2 → at most two candidate-admission snapshot batches
```

A candidate-free frontier may legitimately require fewer.

### 5.14 Source freshness across operations

Preserve V2/V3 behavior:

```text
context A created
→ neighborhood read A uses authority epoch A
→ live source changes
→ second read on context A remains coherent with epoch A
→ context B created over same parsed revision
→ neighborhood read B observes changed source authority
```

No revision-only neighborhood cache may hide this.

---

## §6 Completeness and explicit bounds

### 6.1 Depth is the semantic bound

For V4.1, boundedness comes from the explicit traversal request:

```text
exact seed set
+ requested depth 1 or 2
```

Within that bound, the result should return every admitted traversal edge discovered by the required frontier expansion.

Do not silently apply ordinary limits such as:

```text
12 entities
24 relationships
32 assertions
32 evidence rows
```

and still label the neighborhood complete.

### 6.2 Seed-count validation is allowed

To keep one request operationally bounded, the implementation may require a small explicit seed-count limit.

Preferred inherited product-compatible limit:

```text
1..8 exact seed IDs
```

If implemented, it is a **request validation limit**, not a truth truncation rule.

Reject too many seeds explicitly rather than silently dropping them.

### 6.3 Partial/resource semantics

V4.1 does not need to invent a partial-result mechanism merely because one might be useful later.

Preferred first implementation:

```text
semantic request valid + authority intact → complete traversal result
integrity failure                         → fail closed with typed error
```

If a partial result type is introduced, it must have a closed reason vocabulary and cannot use generic cardinality caps to masquerade as completeness.

---

## §7 Result digest

The semantic result digest must bind caller-visible returned meaning, not timings or work counters.

At minimum bind:

```text
space_id
revision_id
domain contract/profile identity
requested seed IDs
found/missing seed IDs
requested depth
entity IDs + minimum depths
returned traversal assertion IDs
returned evidence identity + locator content
returned source artifact fields actually exposed
returned source revision fields actually exposed
completeness/coverage state
```

Follow the V3 rule:

> Hash visible returned authority. Do not hash the fingerprint of hidden/excluded candidate provenance.

Changing provenance for an excluded edge must not perturb a visible neighborhood digest.

Changing returned source authority metadata must perturb it if that metadata is returned.

Work counts and elapsed timing must not affect the digest.

---

## §8 Structural work accounting

The code and benchmark must make the cost model obvious.

At minimum expose/record:

```text
seed entity lookups
frontier entities expanded
candidate touching assertion IDs discovered
deduped candidate assertion IDs
assertions actually evaluated
policy evaluations
endpoint entity lookups
evidence IDs returned
unique artifact IDs requested
unique source revision IDs requested
provenance snapshot calls
returned entity count
returned traversal assertion count
```

For depth 2, record per-layer counts if practical:

```text
layer 1 frontier size / candidates / evaluated
layer 2 frontier size / candidates / evaluated
```

Do not count only returned edges while hiding thousands of inspected assertions.

---

## §9 Required semantic witnesses

The implementation must include focused witnesses for at least the following.

### A. Exact seed semantics

1. one existing exact seed returns at depth 0;
2. missing seed is explicit and no search fallback occurs;
3. structurally existing seed with zero admitted edges still returns depth 0;
4. duplicate input seeds are deterministic/deduplicated or explicitly rejected;
5. seed ordering does not change the semantic result;
6. if a seed limit is implemented, >limit fails explicitly rather than truncating.

### B. Depth semantics

7. depth 1 returns all admitted touching edges from seeds;
8. depth 1 returns opposite endpoints at depth 1;
9. depth 1 does not expand those endpoints;
10. depth 2 expands only newly discovered depth-1 frontier entities;
11. newly discovered depth-2 entities are returned at depth 2;
12. depth-2 entities are not expanded;
13. shortest/minimum depth wins under converging paths;
14. direct seed→C beats longer seed→B→C;
15. requested depth outside {1,2} fails explicitly.

### C. Edge admission / privacy

16. player-like audience excludes GM-only edge;
17. excluded GM-only edge does not disclose its unique endpoint;
18. out-of-campaign edge does not disclose its endpoint;
19. wildcard campaign context can admit the same edge when otherwise valid;
20. inactive source removes the edge from traversal;
21. missing source/revision fails closed under V2 semantics;
22. domain-policy excluded edge does not traverse;
23. focus/domain context does not silently broaden traversal authority;
24. source visibility is preserved through V2 ordering/privacy behavior.

### D. Direction and graph shape

25. outgoing assertion direction preserved;
26. incoming assertion direction preserved;
27. self-loop returned once and creates no new frontier entity;
28. A→B→A terminates;
29. triangle/cycle terminates;
30. converging paths dedupe entity and assertion output;
31. parallel distinct assertions between same endpoints are preserved if admitted;
32. hidden parallel edge does not cause visible duplicate/leak.

### E. Structural locality

33. no full assertion scan;
34. no neighbor subject-assertion scan to rediscover touching edges;
35. no full-space projection;
36. no full evidence scan;
37. no whole-source preload;
38. unrelated entity/assertion growth does not grow candidate counts for a fixed local neighborhood;
39. unrelated source growth does not grow requested source IDs;
40. a frontier neighbor with thousands of unrelated **non-entity-ref facts** does not increase touching candidate work;
41. a depth-2 endpoint with thousands of additional touching edges is not expanded for a depth-2 request;
42. high-degree seed work scales with its actual touching support and is accounted honestly.

### F. Coherence/freshness

43. depth-1 operation uses one pinned context;
44. depth-2 frontier batches remain on one pinned context/source epoch;
45. live source mutation after context A does not tear a later layer of the same context;
46. new context B over the same parsed revision observes changed authority;
47. no revision-only neighborhood result cache.

### G. Genericity

48. organizational-memory fixture traverses using the generic engine;
49. Buddy-shaped fixture traverses using opaque scope/visibility labels only;
50. no `GM`, `PLAYER`, `campaign_id`, NPC, D&D, or fictional-time dependency appears in the generic neighborhood implementation;
51. no dynamic domain-policy loading appears;
52. frozen V0 aggregate remains exact.

### H. Immutability/determinism

53. returned DTOs are immutable;
54. returned map/depth backing cannot be poisoned by caller mutation;
55. repeated same-context read produces same ordering/digest;
56. reordered fixture construction produces same semantic result;
57. work counters do not participate in semantic digest;
58. excluded provenance changes do not change visible digest;
59. returned authority changes do change digest where visible.

### I. Regression/scope

60. V1 normalized-revision/index tests remain green;
61. V1 legacy-compatibility tests remain green;
62. V2 candidate-admission tests remain green;
63. V3 exact/complete entity-read tests remain green;
64. current World public services remain unchanged;
65. no write/publication path changes;
66. no vNext storage migration;
67. no V4.2 standalone evidence/anchor API exported;
68. no V4.3 search API exported.

The exact test count is not authority. These obligations are.

---

## §10 Benchmark / characterization requirements

Create:

```text
benchmarks/vnext_neighborhood_10k.py
Docs/Benchmarks/vnext_neighborhood_10k_v1.json
```

Minimum workloads:

### 10.1 Fixed low-degree depth-1, 1k vs 10k unrelated space

Same local neighborhood, dramatically more unrelated entities/assertions/sources.

Prove:

```text
candidate touching assertions unchanged
assertions evaluated unchanged
requested source IDs unchanged
returned semantic digest shape unchanged except revision/workload identity where intentionally bound
```

### 10.2 Fixed branching depth-2, 1k vs 10k unrelated space

Prove both frontier layers remain local.

Record per-layer work where practical.

### 10.3 Noisy-neighbor witness

One admitted edge reaches a depth-1 neighbor that owns thousands of unrelated literal/term assertions.

Depth-2 expansion must use that neighbor's entity-ref assertion indexes and must not scan the unrelated subject facts.

### 10.4 Depth-boundary witness

A depth-2 endpoint owns/touches thousands of additional entity-ref assertions.

A depth-2 request must not evaluate them because that would be depth-3 expansion.

### 10.5 High-degree honest-cost witness

A seed with many real touching entity-ref assertions should show work increasing with actual neighborhood degree.

This is not a failure. The claim is locality, not constant time independent of returned truth.

### Required artifact fields

Record at minimum:

```text
schema version
exact base SHA
exact substantive head SHA
workload digests
parsed semantic digests
requested seeds/depth
returned semantic result digest
returned entity/assertion counts
candidate/evaluation/source work counts
p50/p95 where meaningful
structural gate verdict
```

If the benchmark artifact is committed in a bounded finalization commit after the substantive implementation, pin `exact_head` to the substantive implementation head rather than fabricating self-reference.

### Directional target

Canonical architecture target:

```text
10k depth-1 neighborhood p95 < 50 ms
100k depth-1 neighborhood p95 < 100 ms
```

The 10k lane is required for V4.1 acceptance.

100k is useful if practical but is not required to claim only what was actually measured.

A faster wrong answer fails.

---

## §11 Expected implementation shape

Illustrative only:

```python
class NeighborhoodReadService:
    def get_neighborhood(
        self,
        context: KnowledgeReadContext,
        seed_entity_ids: Sequence[str],
        depth: Literal[1, 2] = 1,
    ) -> NeighborhoodResult:
        ...
```

Preferred internal decomposition:

```text
validate + exact seed lookup
→ expand frontier batch
→ V2 evaluate candidates
→ derive admitted opposite endpoints
→ accumulate immutable BFS state
→ assemble direct support for returned assertions
→ build immutable sorted result
→ compute semantic digest
```

If V3's direct support assembly or source DTO conversion needs reuse, prefer extracting one small internal generic helper rather than copying it into neighborhood code.

Do not make `EntityReadService.get_complete_entity()` the traversal primitive for every frontier entity if that causes repeated evaluation/provenance loads or obscures the BFS cost model.

V3 remains the complete selected-entity API. V4.1 is a distinct batched traversal operation.

---

## §12 Explicitly out of scope

Do **not** implement in V4.1:

```text
standalone evidence retrieval API
source-anchor generation
source-anchor revalidation/resolution
lexical search
alias search
ranked search
FTS/BM25
vector retrieval
full-space projection
mutable head resolution
KnowledgeSpace durable runtime
native vNext writes/publication
PostgreSQL vNext authority schema
bridge-genesis migration
DungeonBuddy production policy
DungeonBuddy repin/cutover
current World public-reader replacement
historical-reader quarantine/deletion
Redis/distributed caching
new graph database
```

No V5 work belongs here.

---

## §13 Stop / rebrief conditions

Stop and return to Steward rather than compensating locally if any of these become true:

1. correct depth-1/depth-2 traversal requires full-space projection;
2. raw `entity_adjacency` must be treated as authorized knowledge;
3. an excluded edge's endpoint must be exposed to discover the correct admitted neighborhood;
4. frontier batches cannot share one coherent V2 source-authority epoch;
5. candidate-local traversal requires changing the frozen V0 contract;
6. traversal requires a durable vNext database migration;
7. traversal requires search/anchor semantics before it can be correct;
8. a domain policy must broaden Kernel-rejected knowledge;
9. Buddy/TTRPG vocabulary must enter generic neighborhood code;
10. current public World retrieval must change to prove the generic seam;
11. a revision-only cache of mutable authority verdicts is required;
12. tests must weaken V2/V3 fail-closed semantics to proceed.

When a stop condition fires, record:

```text
Stop condition:
Roadmap phase:
Observed evidence:
Which assumption failed:
Affected authority/architecture document:
Why the current PR cannot safely compensate:
Proposed design decision / experiment:
What remains safe in parallel:
```

If the assumption failure changes architecture, update canonical architecture/roadmap before resuming implementation.

---

## §14 PR body requirements

The V4.1 implementation PR body should contain:

```text
Primary question
Exact base SHA:
  82a5c3e6889ad4e5648fef8f358423b5a576cb9b
Exact current substantive head
Intended changed surface
Frozen V0 aggregate
Accepted V3 predecessor identity
Traversal algorithm / frontier semantics
Authority/admission reuse design
Semantic evidence
Structural work evidence
Benchmark artifact + substantive head
Actual tests/CI
Known inherited failures
What remains false
Named successor: V4.2 evidence + anchor support
```

Do not claim V4.1 acceptance in the PR body before Steward review records it.

---

## §15 Review gate

Review exact heads.

The Steward must verify:

### Bookkeeping / sequencing

- implementation base is exact current `main` `82a5c3e6889ad4e5648fef8f358423b5a576cb9b`;
- the implementation PR's first commit records that PR #64 merge SHA as the new Steward/`main` anchor before production code;
- PR #64 is recorded as merged control-surface history, not V4.1 runtime acceptance;
- living Steward records PR #63 merge, accepted head, review cycles, final PASS, V3 artifact, V3 COMPLETE, V4/V4.1 ACTIVE;
- no standalone successor handoff PR is opened.

### Semantics

- exact seed behavior;
- depth semantics;
- only admitted edges traverse;
- endpoint privacy;
- cycles/convergence/minimum depth;
- source coherence/freshness;
- deterministic immutable result/digest.

### Structural work

- no full-space projection;
- no all-assertion scan;
- no neighbor subject-fact scan;
- no depth-3 expansion for depth-2 requests;
- candidate/source work proportional to visited frontier support;
- benchmark accounting exposes actual work.

### Regression/scope

- frozen V0 contract unchanged;
- V1/V2/V3 suites green apart from accepted inherited baseline failures;
- World public runtime unchanged;
- no V4.2/V4.3/V5 creep.

Only successful disposition:

```text
V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
```

After V4.1 merges, the **V4.2 successor implementation PR** must carry the living Steward update in its first commit:

```text
actual V4.1 merge SHA
accepted V4.1 head
logical review-cycle count
final PASS review ID
V4.1 disposition
vnext_neighborhood_10k_v1.json evidence
V4.1 COMPLETE
V4.2 ACTIVE
```

Do not open a standalone V4.2 handoff/bookkeeping PR.

V4.1 acceptance unblocks V4.2 only. V4.3 remains blocked on V4.2. V5 remains blocked on V4.3.

---

## §16 What remains false after this bookkeeping commit

PR #64 and this first implementation commit do not establish runtime behavior.

All of the following remain false until implementation evidence says otherwise:

- no native vNext bounded neighborhood API is accepted;
- no standalone evidence retrieval API is accepted;
- no source-anchor API is accepted;
- no deterministic indexed search API is accepted;
- no vNext KnowledgeSpace/head durable runtime exists;
- no native vNext governed write path exists;
- no bridge-genesis migration exists;
- no current public World cutover has occurred;
- no historical-reader quarantine/deletion is authorized;
- no DungeonBuddy runtime repin/cutover has occurred;
- deeper storage optimization remains unauthorized.

The handoff's job is to make the next proof precise, not to claim that proof early.
