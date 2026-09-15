# HANDOFF — STEWARDSHIP: DungeonMind vNext roadmap

**Created:** 2026-09-14  
**Status:** ACTIVE — living stewardship authority for the vNext roadmap  
**Repository:** `Drakosfire/DungeonMind`  
**Current main anchor at creation:** `22bf2e42686876e1c0f9750d1b346e4a6fffebc4` — merged PR #54  
**Current main anchor:** `6c5e746d3fa3ffbbdb371ddb15d9c392ab3fd3a0` — merged PR #58  
**Canonical roadmap:** `Docs/Roadmaps/ROADMAP.md`  
**Semantic architecture:** `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`  
**Read/performance architecture:** `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`  
**One-line mission:** Steward the deliberate V0–V11 transition from the current World-shaped DungeonMind implementation to a domain-agnostic governed knowledge library while preserving authority invariants, historical readability, semantic parity, and evidence-backed read-path performance.

---

## §1 Steward role

This is the durable control document for continuity of design and proof across the vNext roadmap.

The Steward owns:

```text
intent
sequencing
proof obligations
scope control
review continuity
cross-repository contract alignment
recording what was learned
```

The Steward must:

- re-anchor against current checked-in truth before every decision;
- dispatch small PRs with one primary question;
- review exact heads, not branch names;
- distinguish semantic, migration, performance, and consumer evidence;
- preserve DungeonMind / DungeonMindBuddy ownership boundaries;
- stop and rebrief when implementation evidence falsifies the planned shape;
- update canonical architecture/roadmap documents when accepted decisions change them;
- update this handoff after every roadmap merge before another roadmap PR merges.

Implementation PRs own bounded technical choices inside these constraints.

> **Be strict about invariants and evidence; be flexible about mechanisms that satisfy them cleanly.**

---

## §2 Current checkpoint

### Completed architectural foundation

PR #53 established the breaking semantic direction:

```text
KnowledgeSpace
immutable KnowledgeRevision lineage
Entity + Assertion graph
EvidenceRef
KnowledgeContribution
IdentityDecision
DomainContract
SemanticProfile
Generic scope / visibility / standing / temporal contracts
```

PR #54 established the V0–V11 roadmap and read/performance architecture.

PR #56 froze the generic vNext contract bundle at:

```text
fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

DungeonMindBuddy PR #719 proved the frozen contract can represent the current DungeonBuddy World/TTRPG authority semantics without adding Buddy-only fields to the generic Kernel contract. Overall V0 disposition:

```text
VNEXT_CONTRACT_FROZEN
```

### V1 complete

DungeonMind PR #57 established V1.1, the immutable generic `ParsedKnowledgeRevision` plus deterministic revision-local indexes.

DungeonMind PR #58 established V1.2, the frozen v1–v6 compatibility codec and semantic parity proof.

V1 final dispositions:

```text
V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED
V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED
V1_IMMUTABLE_NORMALIZATION_COMPLETE
```

The canonical roadmap is now:

```text
V0   Contract freeze                                      COMPLETE
V1   Immutable normalized revision + revision indexes    COMPLETE
V2   Generic KnowledgeReadContext + candidate admission  ACTIVE
V3   Lazy exact / complete entity reads
V4   Neighborhood + evidence + anchor + indexed search
V5   Generic governed write contracts
V6   DungeonBuddy domain implementation
V7   Bridge-genesis migration
V8   Joint semantic + performance acceptance
V9   Cutover
V10  Remove old current/public paths; quarantine compatibility
V11  Deeper storage optimization only if evidence still demands it
```

### Current primary question

**V2 — generic `KnowledgeReadContext` + candidate admission seam**

> Can one exact `ParsedKnowledgeRevision` support coherent generic and pinned-domain admission over an arbitrary candidate slice, with targeted fresh source/provenance state, without pre-projecting the entire KnowledgeSpace or changing current World runtime behavior?

V2 is a seam/proof phase. It is not permission to implement V3 entity retrieval early.

---

## §3 Authority and source precedence

Current checked-in repository truth outranks this handoff. Chat/history is never authority.

Fresh Steward read order:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `CONTRIBUTING.md`
6. `Docs/Architecture/ARCHITECTURE.md` for the current pre-cutover runtime
7. relevant accepted ADRs
8. current performance evidence
9. this handoff

Frequently relevant ADRs remain:

```text
ADR-0010 expected-parent CAS publication
ADR-0011 durable publication recovery
ADR-0014 assertion-scoped World Graph v4
ADR-0015 lossless source provenance v2
ADR-0018 relationship endpoint aspects v6
ADR-0019 existing-world adoption boundary
ADR-0020 v6 governed review publication
ADR-0021 existing-world adoption repair
ADR-0022 independent library / agent-harness boundary
ADR-0023 reviewed-first-world provenance compatibility
```

If a conversation creates a real architectural decision, update the appropriate checked-in architecture/roadmap/ADR before treating it as durable.

---

## §4 Project mental model

DungeonMind owns knowledge authority mechanics, not product meaning.

The following complexity is earned and survives vNext:

```text
stable opaque identity
exact source/evidence provenance
immutable published revisions
explicit mutable head
expected-parent CAS
canonical hashing
fail-closed reads
governed publication
replay/idempotency/recovery
historical reconstructibility
```

World-specific semantics leave the generic Kernel:

```text
world_id vocabulary
campaign modes
GM / PLAYER enums
canon vocabulary
session authorization
fictional-time ontology
World/Campaign/Cross-Campaign projection enums
```

The boundary remains:

```text
DungeonMind knows
  identity
  assertions
  evidence
  immutable revisions
  generic governance/admission
  retrieval mechanics

Domains/clients know
  what predicates and claim modes mean
  domain scope labels
  audience-role mapping
  domain temporal meaning
  product authorization
  UI / agent workflows
```

> **Make composition easy; make correctness non-configurable.**

---

## §5 Read/performance mental model

The target bounded-read shape is:

```text
exact immutable revision
→ immutable ParsedKnowledgeRevision
→ revision-local candidate lookup
→ targeted coherent provenance load
→ generic standing/scope/visibility admission
→ pinned pure domain admission
→ bounded result
```

Full projection remains valid and explicit O(N). It must no longer be a compulsory precursor to bounded reads.

Binding cache rule:

```text
SAFE TO REUSE BY EXACT REVISION / COMPATIBILITY ID
  ParsedKnowledgeRevision
  revision-local structural indexes

NOT SAFE TO CACHE BY REVISION ALONE
  source-authority verdict
  scope/visibility verdict
  admitted candidate/projection
  domain-admission verdict
```

Source/provenance state may change while the knowledge revision remains immutable.

Optimization order:

```text
1. avoid unnecessary work
2. avoid loading unnecessary data
3. avoid unnecessary copies / allocations
4. add immutable derived indexes
5. optimize serialization / hashing
6. redesign durable storage only if evidence still demands it
```

Do not introduce Redis, distributed caches, graph-database migration, event sourcing, vector-first retrieval, or revision-only authorization caches without measured evidence and explicit roadmap authorization.

---

## §6 V1 evidence now binding for V2

### PR #57 — immutable normalized model

```text
merge: 6d9a40f609530f4882470c5599b4914e2288b8d5
accepted head: 38d9eac3252ba911ff7565b930ce8b84aca0767b
review cycles: 2
final review: 5213422370
disposition: V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED
```

It established:

- immutable `ParsedKnowledgeRevision`;
- fail-closed structural integrity;
- exact revision-header preservation;
- entity/assertion/evidence/alias lookup indexes;
- subject, adjacency, evidence-support, literal, alias, and lexical indexes;
- no scope/visibility admission in the parser;
- no D&D dependency;
- no frozen V0 contract change.

10k characterization artifact:

`Docs/Benchmarks/vnext_parsed_knowledge_revision_10k_v1.json`

### PR #58 — legacy compatibility parity

```text
merge: 6c5e746d3fa3ffbbdb371ddb15d9c392ab3fd3a0
accepted head: b8ca0a579c00a6fde7f9ea51b6bad709cba1e71f
review cycles: 4
final PASS review: 5216431557
dispositions:
  V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED
  V1_IMMUTABLE_NORMALIZATION_COMPLETE
```

Compatibility identity:

```text
mapping revision: dm_legacy_world_compat_v1
manifest sha256: f408ce73b8efb32a36e4fb29eb68e9242cb358a76c0c0b60eafdce5046abbe4f
parity records digest: 733e1af301123c5de337bd8bb15241517b07c63bc6cf27eb2dec6e6ee21db139
```

Canonical parity artifact:

`Docs/Compatibility/legacy_v1_v6_parity_v1.json`

All six frozen historical graph generations have exact historical-reader/compatibility-witness parity.

The compatibility codec is **not migration**:

- historical payloads are never rewritten;
- no fake native-vNext parentage is created;
- the current historical readers remain the semantic oracle until quarantine is explicitly proven later;
- v1–v3 missing metadata remains compatibility-coarse rather than being filled with guessed permissive semantics;
- `fact` is not silently mapped to `asserted`;
- `source_derived_candidate` is not silently mapped to `inferred`;
- v6 endpoint aspects survive losslessly;
- scoped/GM aliases remain assertions rather than entering generic identity aliases;
- compatibility implementation identity seals executable mapping semantics.

10k v6-like compatibility characterization:

```text
artifact: Docs/Benchmarks/legacy_v6_compatibility_10k_v1.json
entities: 3,000
assertions: 16,000
evidence: 1,500
semantic digest: f48c400849b811bc03695c16072614ba87bc628a278894358329e5d099b1a688
compatibility key: a62befb9ee50df5756b3ad56a1e796c655fc5dd35966a7e5748e3ef4fd9532f2
peak traced memory: ~132.62 MiB
compatibility decode/build: ~14.48 s
normalized indexed lookups: microsecond-scale characterization
```

This is characterization, not a V2 latency target.

### V2 compatibility caution

`dungeonmind.compat:*` fields created by the historical codec preserve legacy meaning. In particular, compatibility-coarse visibility is not a new generic authorization label that V2 may reinterpret as product authority. Native V2 generic admission must operate on the normalized metadata literally and fail closed when a context cannot establish admissibility.

---

## §7 V2 implementation boundary

V2 owns the read/admission seam only.

Expected application-layer concepts:

```text
KnowledgeReadContext
  exact ParsedKnowledgeRevision
  exact request/context identity
  ScopeSelector
  effective audience labels
  standing selector
  focus/domain context
  pinned DomainContractDescriptor
  pinned SemanticProfileDescriptorV2
  source/provenance reader
  per-context provenance/evidence memo

CandidateAdmission
  candidate assertion IDs
  generic integrity / standing / scope / visibility
  evidence/source integrity
  pure pinned domain policy
  admitted/excluded result
```

The exact class/module names are implementation choices; responsibilities are binding.

V2 should introduce a generic vNext provenance read abstraction over:

```text
SourceArtifactV3
SourceRevisionV2
EvidenceRefV3 / ParsedEvidenceRef
```

It may use an in-memory/fake adapter for proof. A PostgreSQL vNext storage migration is not required or authorized in this phase.

### Domain policy runtime

`DomainContractDescriptor` remains data-only.

A runtime domain policy mechanism may be introduced only if it is:

- explicitly registered by the embedding application/test harness;
- resolved against the exact pinned `DomainContractRef` / descriptor identity;
- pure and deterministic;
- passed immutable candidate/context values only;
- given no repository/network/clock/mutation capability;
- able only to narrow Kernel-admissible knowledge;
- fail-closed when absent, unknown, or mismatched.

Do not dynamically import arbitrary code from `admission_policy_id`.

### Candidate-local provenance

For a bounded candidate slice:

```text
candidate assertion IDs
→ evidence refs referenced by those assertions
→ unique required source artifact/revision IDs
→ one coherent targeted source snapshot
→ provenance admission
```

Do not load provenance for the full revision merely because it is easier.

Within one context, the source view must be coherent and memoized. A new context must observe changed live source authority even when the `ParsedKnowledgeRevision` object is reused.

---

## §8 Explicitly not V2

Do not implement in this phase:

```text
get_entity / get_complete_entity public reads
neighborhood traversal API
search API
anchor resolution API
full-space vNext projection API
KnowledgeSpace/head repository migration
native vNext publication/writes
PostgreSQL vNext authority schema
DungeonBuddy production domain policy
DungeonBuddy dependency repin/cutover
bridge-genesis migration
World public-read replacement
historical-reader deletion/quarantine
storage-model redesign
```

V3 consumes the accepted V2 seam for exact/complete entity reads.

---

## §9 Stewarding one roadmap PR

Each implementation PR must state:

```text
primary question
base SHA
intended changed surface
binding invariants
required evidence
actual evidence
known inherited failures
what remains false
named successor
```

Review exact heads and record:

```text
base SHA
reviewed head SHA
logical review cycle
blocking findings
non-blocking findings
verification evidence
final disposition
```

A PR merges only when its primary question has an evidence-backed answer.

Do not merge because CI is green if the claimed authority proof is missing, and do not weaken tests to make a changed semantic result acceptable without an explicit contract/architecture decision.

---

## §10 Steward mutation protocol

This document is intentionally mutable.

After every roadmap PR merge, update this file before another roadmap PR merges.

Preferred sequence:

1. successor branch first commit updates this handoff with the actual merge anchor and phase transition; or
2. a tiny Steward sync PR lands before the next implementation slice.

Every update records at minimum:

```text
current main anchor
last merged roadmap PR
accepted implementation head
review-cycle count / final PASS reference
new proof artifacts / benchmark baselines
current phase/disposition
new risks / stop conditions
what remains false
next primary question
parallel work posture
```

Keep this useful rather than archival. Detailed review history belongs in PR history.

If an update changes semantic contracts, ownership, migration model, read architecture, or roadmap ordering, update the canonical architecture/roadmap in the same change set.

---

## §11 Invariants protected across the roadmap

1. Published history is never rewritten.
2. One explicit head selects current truth; timestamps do not.
3. Expected-parent CAS remains the publication concurrency boundary.
4. Evidence/source state participates in knowledge validity.
5. Unknown or broken authority fails closed.
6. Retrieval/ranking never manufactures authority.
7. Stable IDs remain opaque and durable.
8. Domain policy may narrow generic admission; it may never recover rejected knowledge.
9. DungeonMind does not become the product agent harness.
10. DungeonBuddy remains a replaceable client and does not define Kernel vocabulary.
11. Genericity does not mean untyped property bags.
12. Derived indexes are rebuildable and non-authoritative.
13. Bounded vNext reads must not require full-space projection.
14. Source/provenance freshness must not be hidden by revision-only admission caches.
15. Performance credit requires semantic parity first.
16. Historical readability survives hot-path cleanup.
17. Migration preserves durable IDs wherever meaning is unchanged.
18. No long-lived dual-write architecture is introduced for cutover convenience.
19. Physical storage complexity remains evidence-gated until V11.
20. One PR has one primary question.

---

## §12 Current V2 proof obligations

The V2 implementation must prove at least:

- exact request/revision/contract/profile identity is pinned and mismatches fail closed;
- candidate assertion IDs are resolved only from the exact parsed revision;
- scope admission implements the frozen `ScopeSelector` semantics exactly;
- visibility implements Public / LabelsAny / LabelsAll exactly;
- undeclared/unknown audience labels or policy identity fail closed;
- standing selection is explicit and deterministic;
- evidence/source chains are validated from one coherent targeted snapshot;
- missing/inactive sources and mismatched source revisions exclude candidate knowledge;
- source visibility is evaluated before detailed lifecycle diagnostics are exposed;
- domain policy receives only Kernel-admissible candidates and can only exclude;
- a domain policy cannot re-admit a Kernel-rejected assertion;
- focus/domain context does not silently become authorization;
- DungeonBuddy-shaped campaign/GM/player behavior is reproducible using only opaque generic scopes/labels in fixtures;
- an unrelated organizational-memory fixture uses the same admission engine;
- changing source authority between contexts is visible even when the parsed revision instance is reused;
- source changes during one context do not tear the read into inconsistent provenance views;
- candidate-local provenance work counts scale with candidate support rather than full revision size;
- the current World runtime and historical readers are untouched.

The exact test count is not authority; these semantic obligations are.

---

## §13 Stop / rebrief conditions

Stop rather than compensating locally if:

- V2 requires changing the frozen V0 contract bundle;
- candidate-local admission cannot preserve fail-closed provenance semantics;
- a bounded candidate requires full-space projection for correctness;
- a domain policy requires storage/network/clock access;
- `admission_policy_id` would need arbitrary dynamic plugin execution;
- domain policy needs to recover Kernel-rejected knowledge;
- focus must become hidden authorization to reproduce required semantics;
- source freshness requires a revision-only cache of mutable authority verdicts;
- V2 requires a durable vNext database migration or bridge-genesis migration;
- Buddy/TTRPG vocabulary must enter generic application code;
- compatibility-coarse legacy metadata would need to be silently promoted into native authority semantics;
- current public World readers must change to prove the seam;
- tests must weaken fail-closed behavior to proceed.

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

Then update canonical architecture/roadmap before implementation resumes if the decision is architectural.

---

## §14 Current stewardship ledger

### Last merged roadmap PR

```text
DungeonMind PR #58
KERNEL: legacy v1–v6 compatibility decoder + semantic parity
merged: 6c5e746d3fa3ffbbdb371ddb15d9c392ab3fd3a0
accepted implementation head: b8ca0a579c00a6fde7f9ea51b6bad709cba1e71f
review cycles: 4
final PASS review: 5216431557
disposition:
  V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED
  V1_IMMUTABLE_NORMALIZATION_COMPLETE
manifest sha256: f408ce73b8efb32a36e4fb29eb68e9242cb358a76c0c0b60eafdce5046abbe4f
parity records digest: 733e1af301123c5de337bd8bb15241517b07c63bc6cf27eb2dec6e6ee21db139
frozen V0 aggregate: fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

Prior key anchors:

```text
PR #57 merge 6d9a40f609530f4882470c5599b4914e2288b8d5 — V1.1
DungeonMindBuddy PR #719 merge c77056b0c909513cecd8b81f9e7fac22e02d339a — V0.2 / VNEXT_CONTRACT_FROZEN
PR #56 merge 63ec810a02f18c4e25af228f6fdb19d99d12579e — V0.1
PR #54 merge 22bf2e42686876e1c0f9750d1b346e4a6fffebc4 — roadmap/read architecture
```

### Current phase

```text
V0 COMPLETE — VNEXT_CONTRACT_FROZEN
V1 COMPLETE — V1_IMMUTABLE_NORMALIZATION_COMPLETE
V2 ACTIVE
```

### Next primary question

```text
Can one exact ParsedKnowledgeRevision support coherent generic and pinned-domain admission over an arbitrary candidate slice, with targeted fresh source/provenance state, without pre-projecting the entire KnowledgeSpace or changing current World runtime behavior?
```

### Parallel work posture

```text
safe / independent:
  larger-scale benchmark characterization
  contract-frozen Buddy/domain work that does not depend on V2 runtime
  design work for V3 consuming the V2 seam, but not V3 merge

blocked until V2 acceptance:
  V3 merge
  V4+ bounded read rollout
  bridge-genesis migration
  cutover
  current-public-path quarantine/deletion
```

### What remains false

- no generic `KnowledgeReadContext` exists yet;
- no generic candidate-admission runtime exists yet;
- no vNext source/provenance reader port or coherent targeted snapshot is accepted yet;
- no pinned pure domain-policy runtime seam is accepted yet;
- no native vNext `get_entity` / `get_complete_entity` runtime exists;
- no `KnowledgeSpace` head/storage runtime exists;
- current public World readers still use the historical path;
- no bridge-genesis migration has occurred;
- no vNext authority has been published;
- DungeonBuddy has not implemented runtime vNext World read/write semantics;
- no cutover has occurred;
- old World contracts remain current production contracts;
- larger 50k/100k K0.3 characterization remains incomplete;
- deeper storage optimization is not authorized.

### Named next action

Dispatch V2 from DungeonMind `main` anchor `6c5e746d3fa3ffbbdb371ddb15d9c392ab3fd3a0` using the successor handoff on branch `handoff/v2-knowledge-read-context-admission`.

---

## §15 Steward completion condition

This handoff remains `ACTIVE` through the roadmap.

It may be superseded only when either:

1. V10/V11 completes and a new steady-state stewardship model is checked in; or
2. the roadmap is deliberately replaced by a new canonical program with a successor Steward handoff.

Landing this file does not complete stewardship.