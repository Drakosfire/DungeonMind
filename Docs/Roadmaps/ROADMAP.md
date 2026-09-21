# DungeonMind — vNext Governed Knowledge Roadmap

**Status:** current forward roadmap  
**Updated:** 2026-09-18  
**Roadmap anchor:** DungeonMind `main` after PR #68 (`bc115eb40f1601e5b6c6fda23ff05ee5bf06883d`)  
**Semantic target:** [`ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`](../Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md)  
**Read/performance target:** [`ARCHITECTURE-vnext-read-path-and-performance.md`](../Architecture/ARCHITECTURE-vnext-read-path-and-performance.md)

This document replaces the earlier L.1–L.6 forward lanes as the canonical execution roadmap.

Historical cutover, critique, K0/K1 planning, and R.1/R.2/R.3 records remain valuable evidence and are not rewritten. The current production implementation is still the World Graph architecture; this roadmap describes the deliberate breaking transition to vNext.

## North star

DungeonMind becomes a small, deterministic, provenance-first governed knowledge library.

It owns:

```text
stable identity
immutable revisions
explicit head + expected-parent CAS
source/evidence integrity
governed contributions and publication
generic graph structure
generic scope / visibility enforcement
domain/profile identity
bounded retrieval over admitted knowledge
historical reconstructibility
```

Knowledge domains own what facts mean.

Clients own user interaction, agent harnesses, product workflows, and authorization decisions that produce effective Kernel context.

The intended boundary is:

```text
DungeonMind knows
  what identity is,
  what an assertion is,
  what evidence is,
  what a revision is,
  and how governed knowledge changes.

DungeonBuddy knows
  what the assertions mean.
```

## Why the roadmap changed

The post-cutover critique identified two independent problems that converge on the same implementation seam.

### Semantic problem

Current generic contracts encode World-specific concepts:

```text
world_id
campaign scope
GM / PLAYER
canon
session focus
fictional time
```

The accepted vNext architecture moves these into an explicit DungeonBuddy domain contract and replaces them with generic KnowledgeSpace / scope / visibility / standing / temporal contracts.

### Performance problem

R.2a and R.3a established that point reads still scale with whole-graph projection.

R.3a already delivered the first low-hanging wave:

```text
live Eldyrwild projection
~20.7 s
→ ~115 ms warm
```

through:

- one coherent read context;
- immutable revision parse reuse;
- one batched provenance snapshot;
- per-context evidence memoization.

But synthetic 10k bounded reads remain measured in seconds because they still pay graph-sized admission/projection work.

Therefore the vNext transition intentionally combines genericization with the next low-hanging structural optimization:

> immutable normalized revisions + revision-local indexes + candidate-local admission.

This is not permission for a speculative persistence rewrite.

---

# Governing rules

## Rule 1 — one primary question per implementation PR

Every PR must answer:

> What did this PR prove that was not proven before?

Do not bundle contract invention, storage migration, Buddy cutover, and performance work into one review surface.

## Rule 2 — correctness invariants remain non-configurable

Never add switches for:

```text
immutable revisions
provenance integrity
expected-parent CAS
fail-closed unknown authority
replay/history integrity
domain validation
```

Composition should be easy. Correctness should not be optional.

## Rule 3 — semantic parity precedes performance credit

A faster wrong answer fails.

Every optimization result records the semantic result/digest before interpreting timing.

## Rule 4 — reduce work before changing infrastructure

Optimization order:

```text
1. avoid unnecessary work
2. avoid loading unnecessary data
3. avoid unnecessary copies/allocations
4. add immutable derived indexes
5. optimize serialization/hashing
6. redesign durable storage only if still required
```

## Rule 5 — immutable authority and serving representation are distinct

A full canonical immutable revision may remain the audit/export/replay artifact even when bounded serving uses revision-local derived indexes.

Derived indexes never become knowledge authority.

## Rule 6 — source authority remains fresh

A graph/knowledge revision alone does not freeze mutable source lifecycle state.

Do not cache admitted/scoped results across requests by revision alone.

## Rule 7 — old history remains history

Do not rewrite v1-v6 immutable graph revisions into vNext payloads.

Migration produces an explicit bridge genesis into the new authority model.

Historical readers are quarantined compatibility obligations, not the new hot-path architecture.

---

# Evidence inherited by every vNext PR

## Current semantic proof

K0.2 golden semantic witness:

```text
schema: dm_k0_semantic_witness_v1
aggregate: sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
```

Current World semantics are an acceptance oracle during migration until an explicit vNext contract decision intentionally changes transport shape.

## Current optimization proof

R.2a:

- full projection is the structural floor of bounded reads;
- search and anchor resolution add graph-size-dependent secondary cost;
- memory grows with admitted graph size.

R.3a:

- coherent provenance batching removes catastrophic PostgreSQL N+1 behavior;
- parsed immutable revision reuse is safe when compatibility identity is part of the key;
- admitted/scoped projection caching by revision alone is unsafe;
- semantic digests can remain exact while structural work changes dramatically.

Complete-object retrieval:

- complete selected-object truth cannot be defined by ordinary bounded result caps;
- a product should not need whole-World transport to obtain one complete selected object.

These are binding lessons for vNext implementation.

---

# Phase map

```text
V0   Contract freeze
 ↓
V1   Immutable normalized revision + revision-local indexes
 ↓
V2   Generic KnowledgeReadContext + candidate admission seam
 ↓
V3   Lazy exact / complete entity reads
 ↓
V4   Neighborhood + evidence + anchor + deterministic indexed search
 ↓
V5   Generic governed write contracts
 ↘
   V6 DungeonBuddy domain implementation
 ↙
V7   Bridge-genesis migration
 ↓
V8   Joint semantic + performance acceptance
 ↓
V9   Cutover
 ↓
V10  Remove old current/public paths; quarantine compatibility
 ↓
V11  Deeper storage optimization only if evidence still demands it
```

The large-scale World-like / Rules-like benchmark expansion may proceed in parallel. It does not block V0.

---

# V0 — Contract freeze

**Primary question:** Can DungeonMind and DungeonBuddy implement one breaking contract independently without inventing fields on either side?

No persistence or behavior change.

Freeze exact current schemas/types for:

```text
KnowledgeSpace
KnowledgeRevision
KnowledgeHead
PublishKnowledgeRevision

Entity
Assertion
AssertionValue
AssertionMetadata
IdentityAlias
IdentityDecision

ScopeBinding
ScopeSelector
VisibilityRequirement
TemporalScope
KnowledgeStanding
EpistemicBasis

DomainContractRef
DomainContractDescriptor
SemanticProfileRef
SemanticProfileDescriptorV2

SourceArtifact
SourceRevision
EvidenceRef

KnowledgeContribution
ContributionItem union
ContributionDisposition

ProjectionRequest
ProjectionSnapshot
```

Required artifacts:

- canonical JSON/schema fixtures or equivalent deterministic contract descriptions;
- exact contract digest;
- a DungeonBuddy domain-contract fixture;
- an organizational-memory fixture;
- an adversarial epistemic/identity fixture.

### Contract constraint for future performance

Do not define bounded retrieval APIs such that they require a pre-built full `ProjectionResult`.

The contract must allow:

```text
exact revision
+ request context
+ candidate-local admission
```

without changing externally visible authority semantics.

### V0 exit

```text
VNEXT_CONTRACT_FROZEN
```

Both repositories can pin one exact contract identity.

---

# V1 — Immutable normalized revision + revision-local indexes

**Primary question:** Can all current stored graph generations normalize into one immutable generic internal revision representation with exact semantic preservation?

Build:

```text
legacy v1-v6 stored revision
        ↓
compat decoder
        ↓
ParsedKnowledgeRevision
```

`ParsedKnowledgeRevision` should own or expose derived structures equivalent to:

```text
entities_by_id
assertions_by_id
assertions_by_subject
entity_adjacency
evidence_by_id
assertion_evidence
evidence_supporters
exact label index
alias index
lexical candidate index
```

These are derived state, rebuildable from one immutable revision.

### Immutability requirement

Prefer frozen/immutable internal records rather than repeated defensive deep copies of mutable cached models.

### Performance intent

Structural lookup should become bounded before scope/domain admission.

Do not optimize authorization by caching admitted results.

### Proof

- all required legacy schemas decode;
- semantic normalization matches the current reader for the same exact revisions;
- malformed historical state still fails closed;
- index construction is deterministic;
- mutation attempts cannot poison another read;
- relevant 10k benchmark lane is recorded.

### Stop conditions

- a new authority database is required just to build indexes;
- historical revisions would need rewriting;
- scope/visibility semantics are moved into the parser;
- an index is treated as authoritative rather than rebuildable.

---

# V2 — Generic `KnowledgeReadContext`

**Primary question:** Can one exact revision support coherent generic/domain admission without pre-projecting the entire space?

Build a context containing:

```text
exact revision identity
parsed immutable revision
ScopeSelector
effective audience labels
standing selector
focus/domain context
pinned DomainContract
pinned SemanticProfile
source/evidence repository access
per-context provenance/evidence memo
```

### Admission order

Candidate knowledge must pass:

```text
referential integrity
→ standing / retraction state
→ evidence/source integrity
→ generic scope
→ generic visibility
→ domain admission
```

A domain policy may narrow Kernel-admissible knowledge. It may not recover excluded knowledge.

### Provenance behavior

For bounded candidate sets:

```text
candidate assertions
→ required source artifact/revision IDs
→ one coherent targeted provenance snapshot
```

Full projection may still gather full relevant provenance.

### Cache rule

Safe:

```text
parsed immutable revision
revision-local indexes
```

Unsafe by revision alone:

```text
scope projection
visibility verdicts
source-authority verdicts
domain-admission result
```

### Proof

- current GM/PLAYER/campaign behavior is reproducible through DungeonBuddy domain labels/scopes in fixtures;
- changed source authority is visible on the next context even when the knowledge revision is unchanged;
- no source-state tear within one read;
- unknown labels/policy state fail closed.

---

# V3 — Lazy exact and complete entity reads

**Primary question:** Can exact entity truth be returned with work proportional to the selected entity and its support rather than the whole space?

Land first:

```text
get_entity
get_complete_entity
```

### `get_entity`

Target shape:

```text
entities_by_id[id]
→ subject assertions
→ required evidence/source IDs
→ targeted provenance
→ admission
→ bounded result
```

### `get_complete_entity`

This is the first major architecture witness.

Return:

```text
selected entity
all admitted assertions about it required by the public contract
all admitted touching entity-ref assertions
all required opposite endpoints
all valid support/evidence/anchors
explicit completeness
```

Complete means complete. Ordinary retrieval caps do not silently truncate truth.

### Performance target

The earlier reconstruction target remains directional:

```text
10k exact entity p95       < 25 ms
100k exact entity p95      < 50 ms
```

Do not weaken correctness to reach it.

### Proof

- low-degree entity;
- >24-edge entity;
- >32-anchor entity;
- incoming/outgoing semantics;
- PLAYER-like restricted audience through the DungeonBuddy domain fixture;
- source change freshness;
- deterministic ordering/digest;
- full-space projection not invoked by bounded read.

---

# V4 — Neighborhood, evidence, anchor, and search

## V4.1 — Bounded neighborhood

**Primary question:** Can depth-1/depth-2 traversal touch only visited entities/assertions plus their authority support?

Use revision-local adjacency.

Target:

```text
10k depth-1 p95       < 50 ms
100k depth-1 p95      < 100 ms
```

## V4.2 — Evidence and anchor support

**Primary question:** Can evidence and source anchors resolve through exact support indexes rather than whole-space supporter rediscovery?

Use:

```text
assertion → evidence refs
evidence ref → supporter assertions
```

Preserve existing fail-closed provenance behavior.

## V4.3 — Deterministic search

**Primary question:** Can deterministic entity search generate an exact structural match-witness set from immutable revision-local indexes, admit only those witnesses through the pinned V2 authority path, and rank only admitted matches so that work grows with the real query match set rather than the whole KnowledgeSpace, while hidden or excluded matches cannot affect public result membership, ordering, or digest?

Search indexes discover candidates. They never authorize them.

Public V4.3 results are **assertion-backed**. The revision may retain `alias_exact_index` as rebuildable structural substrate, but V4.3 must not treat an alias match as authority and must not return an entity merely because an alias matched and some unrelated assertion is admitted.

Shape:

```text
query
→ revision-local structural candidate generation
→ exact match-witness assertions
→ candidate-local V2 admission
→ admitted-match aggregation
→ deterministic ranking
→ output limit
```

Do not rank or cap candidates before admission. Hidden matches may increase internal work; they must not change visible membership, order, score, or digest.

Indexes:

```text
exact entity ID
assertion-level lexical tokens
qualified predicates
qualified term-ref values
```

Escalation only if later measured need remains:

```text
1. revision-local lexical index
2. deterministic FTS/BM25 candidate index
3. optional vector candidate source with explicit evidence of value
```

Target:

```text
10k deterministic search p95    < 100 ms
100k deterministic search p95   < 250 ms
```

No search index becomes authority.

---

# V5 — Generic governed writes

**Primary question:** Can the current publication invariants survive after removing World/Graph-Review-specific transport shapes?

Replace migration-shaped contribution bags with typed items:

```text
ProposeEntity
ProposeAssertion
RetractAssertion
SupersedeAssertion
ProposeIdentityDecision
```

Use native canonical JSON assertion values rather than JSON encoded inside strings.

Preserve:

```text
candidate/proposed knowledge
→ validation
→ identity resolution
→ policy disposition
→ exact content binding
→ exact expected parent
→ atomic publication
→ idempotent/recoverable terminal result
```

Human Graph Review becomes one DungeonBuddy governance workflow, not the Kernel definition of publication.

### V5.1 — Generic governed materialization

V5.1 answers only the first publication seam:

```text
governed intent
→ deterministic graph materialization
→ frozen PublishKnowledgeRevisionCommand
```

No database write. No head mutation. No CAS. No replay.

Given one exact native-vNext parent, one frozen `KnowledgeContribution`, complete accepted/rejected `ContributionDisposition`s, and explicit publication identity, materialize one structurally validated generic child graph and one frozen command.

V5.1 is accepted: `V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED` on PR #69, merge `9f006bf77d72faabee8a3eef359b89a3d537b0c1`, accepted head `daa6de4d8a3f36095deff68614db34f2eaba342e`, substantive runtime `cc62079883f34227aa001b7358b6abe192d7f36e`, review cycles 4, final PASS `5257033813`.

### V5.2 — Expected-parent atomic CAS publication

V5.2 answers only the durability seam:

```text
GovernedMaterializationResult
→ sealed PublishKnowledgeRevisionCommand
→ one immutable KnowledgeRevision
→ one atomic KnowledgeHead transition
```

Native authority lives in `knowledge_spaces`, `knowledge_revisions`, `knowledge_heads`, and `knowledge_head_events`. It does not reuse World tables. Stale expected parents fail closed with no authority mutation. V5.2 does not provide a publication receipt, exact replay-as-success, or uncertain-outcome recovery.

V5.3 remains blocked until V5.2 is accepted.

Current V5.2 implementation base after PR #69:

```text
9f006bf77d72faabee8a3eef359b89a3d537b0c1
```

Authority: `Docs/Handoffs/HANDOFF-v5-2-expected-parent-cas-publication.md`

V5.1 authority remains `Docs/Handoffs/HANDOFF-v5-1-generic-governed-materialization.md`.

### Low-hanging write optimization

Take only obvious representation wins:

- typed union validation;
- avoid parse-stringify-parse loops;
- avoid redundant model copies;
- canonical serialize/hash once where possible.

Do not redesign revision persistence yet.

### Required characterization

Measure:

```text
large immutable parent
+ one tiny accepted change
```

Break down parent load, materialization, validation, serialization/hash, bytes written, and total publication latency.

V5.1 records the in-memory subset (parent load, materialization, validation, serialization/hash, payload bytes). Bytes written and publication latency wait for V5.2+.

---

# V6 — DungeonBuddy domain implementation

**Primary question:** Can existing TTRPG semantics move out of the Kernel and remain exact through an explicit domain contract?

This lane may begin after V0 and proceed in parallel with V1–V5 where contracts are frozen.

DungeonBuddy owns:

```text
campaign scope axis
session/focus vocabulary
GM/player visibility labels
claim modes such as fact/belief/rumor/plan
domain temporal schema for fictional time
TTRPG source classifications
D&D semantic profile
World-object DTO adaptation
product authorization → effective Kernel audience labels
```

DungeonBuddy does not bypass governed writes.

### Preservation proof

Reproduce current required behavior:

```text
world-global knowledge
campaign-specific knowledge
cross-campaign read
GM visibility
PLAYER fail-closed visibility
session focus
fictional-time metadata
complete object/evidence/anchors
```

The generic Kernel must contain no `GM`, `PLAYER`, `campaign_id`, `NPC`, or fictional-time implementation dependency after this boundary is complete.

---

# V7 — Bridge-genesis migration

**Primary question:** Can the living current authority become vNext without rewriting history or minting unnecessary identity?

Freeze one exact v1 authority point:

```text
legacy world ID
legacy head revision
legacy graph payload digest
source/evidence state digest
contribution/identity lineage
```

Create deterministic migration manifest.

Then create:

```text
space_id = exact previous world_id value
```

and one vNext bridge genesis:

```text
K0
parent = null
migration_origin_ref = exact legacy authority + manifest digest
```

Preserve existing durable IDs wherever semantics permit.

Old immutable revisions remain untouched and readable through compatibility readers.

No long-lived dual-write regime.

---

# V8 — Joint semantic + performance acceptance

**Primary question:** Is the new architecture both semantically faithful and structurally better before cutover?

Required joint artifact:

```text
dm_vnext_contract_acceptance_v1
```

Record at minimum:

```text
DungeonMind commit
DungeonBuddy commit
contract digest
domain-contract digest
semantic-profile digest
migration-manifest digest
fixture digests
semantic result digests
performance observations
```

Required fixture families:

1. DungeonBuddy preservation fixture;
2. organizational-memory non-TTRPG fixture;
3. adversarial epistemic/identity fixture.

### Performance acceptance

Compare structural work and semantic-equivalent timings for:

```text
exact entity
complete entity
depth-1/depth-2 neighborhood
evidence
anchor
search
full projection
large-parent tiny-delta write
```

At minimum rerun the relevant 10k lanes.

Run the largest practical World-like and Rules-like scale ladder before final cutover. Record `resource_limited` honestly rather than omitting large cases.

The unfinished K0.3 benchmark work may be harvested for this ladder rather than rebuilt from scratch.

---

# V9 — Joint cutover

**Primary question:** Can DungeonBuddy run against vNext authority without a hidden v1 graph runtime?

Sequence:

```text
accept V8 witness
→ freeze old current writes
→ restore/migrate exact accepted authority into vNext
→ pin DungeonBuddy to accepted DungeonMind
→ run full owning consumer cohorts
→ switch current authority path
→ verify head / migration receipt / semantic witness
```

No product workaround is accepted as a substitute for a missing DungeonMind contract.

---

# V10 — Remove old current paths; quarantine compatibility

**Primary question:** What v1 code remains necessary only for historical reconstruction after vNext is current?

Delete from the current/public surface:

```text
WorldGraphRevision / WorldGraphHead current APIs
WorldGraphProjectionRequestV2 current API
ScopeModeV2
Kernel GM/PLAYER admissibility
Kernel campaign scope
World-specific current service names
old current-write contribution shapes
relationship as separate current authority model where vNext assertion covers it
```

Retain required historical codecs/readers under an explicit compatibility boundary.

Do not delete old database/migration history until a separate reconstructibility proof says it is safe.

---

# V11 — Evidence-gated deeper storage optimization

**Primary question:** After lazy indexed reads and representation cleanup, is the physical immutable-snapshot storage model still the limiting cost?

Only enter this lane with measurements.

Possible experiments:

```text
immutable change records
structural sharing
revision root/digest
periodic canonical checkpoints
revision-local durable indexes
incremental materialization
```

Requirements:

- logical immutable revision semantics unchanged;
- exact historical reconstruction preserved;
- canonical export/checkpoint still possible;
- CAS publication unchanged in meaning;
- old/new semantic digests match for equivalent current state;
- measurable improvement over V8 baseline.

Do not adopt a graph database, distributed cache, or event log merely because vNext is a major version.

---

# Parallel measurement lane

The larger K0.3-style benchmark expansion is retained as an evidence project, not a front-door blocker.

Desired deterministic workload shapes:

```text
World-like
Rules-like
```

Scale ladder:

```text
100
1k
10k
50k
100k where machine capacity permits
```

Measure:

```text
cold parse/load
full projection
exact/complete entity
neighborhood
evidence
anchor
search
source snapshot load
large-parent tiny-delta publication
canonical serialization/hash
memory/allocation pressure
repository/query/work counts
```

Timing is observational. Fixture identity and semantic result identity are deterministic.

Large cases may be `resource_limited`; they may not silently disappear.

---

# Expected code shape

The exact package layout is implementation latitude, but ownership should become obvious enough to resemble:

```text
dungeonmind/
  authority/
    revisions
    publication
    provenance

  graph/
    entity
    assertion
    parsed_revision
    indexes
    identity

  governance/
    contribution
    disposition

  domains/
    contract
    registry

  read/
    context
    admission
    retrieval
    projection
    search

  compat/
    world_v1/
      graph_v1 ... graph_v6
      migration
```

The dependency story matters more than folder names:

```text
compat
  → normalized graph

authority
  → normalized graph

read
  → authority + normalized graph + DomainContract

DungeonBuddy
  → public DungeonMind API + DungeonBuddy DomainContract
```

Never:

```text
Kernel → campaign
Kernel → GM
Kernel → NPC
Kernel → DungeonBuddy
```

---

# PR readability standard

Every vNext implementation PR handback must include:

```text
base SHA / exact head SHA
primary question
changed public contract, if any
changed data/work shape
semantic proof
performance/work-accounting delta when relevant
owning tests/integration cohort
review-cycle count
what remains false
named successor
```

For read-path work, explicitly state:

> What data does this operation load and touch as the KnowledgeSpace grows?

For write-path work, explicitly state:

> What part of the parent revision is loaded/materialized/serialized for this change?

A reviewer should not need to reverse engineer the whole service to answer either question.

---

# Explicit anti-goals

Until evidence changes the decision, do not roadmap:

- an agent harness inside DungeonMind;
- UI/product work;
- a second graph per campaign/project/team;
- arbitrary executable semantic-profile hooks;
- untyped property-graph semantics;
- vector search as authority;
- scoped authorization caches keyed only by revision;
- Redis/distributed cache infrastructure;
- a graph database migration by default;
- long-lived dual writes;
- rewriting immutable historical revisions;
- RulesEngine hot-loop queries into DungeonMind;
- weakening provenance/revision/CAS invariants for speed.

## Final optimization principle

```text
Authority stays immutable.
Serving becomes indexed.
Admission becomes candidate-local.
Provenance stays coherent and fresh.
Domain meaning stays outside the Kernel.
Storage complexity must be earned by measurement.
```
