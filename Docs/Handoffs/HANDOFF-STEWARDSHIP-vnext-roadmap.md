# HANDOFF — STEWARDSHIP: DungeonMind vNext roadmap

**Created:** 2026-09-14  
**Status:** ACTIVE — living stewardship authority for the vNext roadmap  
**Repository:** `Drakosfire/DungeonMind`  
**Current main anchor at creation:** `22bf2e42686876e1c0f9750d1b346e4a6fffebc4` — merged PR #54
**Current main anchor:** `6d9a40f609530f4882470c5599b4914e2288b8d5` — merged PR #57
**Canonical roadmap:** `Docs/Roadmaps/ROADMAP.md`  
**Semantic architecture:** `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`  
**Read/performance architecture:** `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`  
**One-line mission:** Steward the deliberate V0–V11 transition from the current World-shaped DungeonMind implementation to a domain-agnostic governed knowledge library, preserving authority invariants, folding in the already-earned structural read optimizations, and keeping the roadmap, proof obligations, cross-repository contract, and next PR continuously coherent.

---

## §1 Steward role

This is not a one-PR implementation handoff.

This is the durable control document for the agent responsible for **continuity of design and proof across the roadmap**.

The Steward is expected to:

- re-anchor against current checked-in truth before every decision;
- understand the architectural destination and why it exists;
- dispatch small implementation/design PRs that each answer one primary question;
- review exact PR heads against the roadmap and architecture, not against memory;
- distinguish semantic correctness, migration correctness, performance evidence, and product integration evidence;
- preserve strict DungeonMind / DungeonMindBuddy ownership boundaries;
- stop or rebrief when implementation evidence falsifies the planned shape;
- update canonical architecture/roadmap documents when an accepted decision changes them;
- **update this Steward handoff as the roadmap advances so a new Steward can resume from checked-in state without chat history.**

The Steward does **not** exist to force implementation details that the architecture does not require.

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

Implementation PRs own their bounded technical choices inside those constraints.

A useful rule:

> The Steward should be strict about invariants and evidence, and flexible about implementation mechanisms that satisfy them cleanly.

---

## §2 Current checkpoint

At creation, the documentation/design foundation is complete enough to begin V0.

### Merged architectural decisions

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

The Kernel owns governed knowledge mechanics. Domains own what assertions mean.

PR #54 established the forward execution roadmap and read/performance architecture.

PR #56 established and froze the generic vNext contract schemas, models, semantic invariants, and multi-domain fixtures (`fd04a904...`).

DungeonMindBuddy PR #719 established and merged the V0.2 consumer proof, confirming that Buddy's campaign/session scope, GM/player visibility, standing, fictional time, World-object representation, candidate governance, and all 11 source domains map losslessly into the generic vNext contract without Kernel modifications or production changes.

DungeonMind PR #57 established and merged V1.1 (`6d9a40f...`), proving that generic vNext knowledge primitives can be normalized into an immutable serving model (`ParsedKnowledgeRevision`) with deterministic derived indexes, deep immutability against cache poisoning, and fail-closed structural integrity.

The canonical roadmap is now:

```text
V0   Contract freeze (COMPLETE — VNEXT_CONTRACT_FROZEN)
V1   Immutable normalized revision + revision-local indexes (ACTIVE: V1.1 COMPLETE, V1.2 ACTIVE)
V2   Generic KnowledgeReadContext + candidate admission seam
V3   Lazy exact / complete entity reads
V4   Neighborhood + evidence + anchor + deterministic indexed search
V5   Generic governed write contracts
V6   DungeonBuddy domain implementation
V7   Bridge-genesis migration
V8   Joint semantic + performance acceptance
V9   Cutover
V10  Remove old current/public paths; quarantine compatibility
V11  Deeper storage optimization only if evidence still demands it
```

### Current next primary question

**V1.2 — legacy v1–v6 compatibility decoder + semantic parity**

> Can every frozen historical `dm_union_graph_v1` through `dm_union_graph_v6` stored revision be verified and decoded into the accepted immutable `ParsedKnowledgeRevision` with deterministic semantic parity to the current historical reader, without rewriting history, performing admission, or pretending legacy payloads are native vNext authority?

### Parallel evidence lane

The unfinished larger-scale K0.3 benchmark work remains useful, especially its planned World-like / Rules-like 100 / 1k / 10k / 50k / 100k characterization.

It is **not** a gate in front of V0 or V1.

R.2a and R.3a already earned the decision to remove whole-projection work from bounded reads. The large-scale lane should be harvested for V1–V4 measurement and V8 acceptance rather than used to delay contract work.

---

## §3 Authority and source precedence

Read current checked-in sources. Never treat this handoff or chat history as higher authority than the repository.

### Required read order for a fresh Steward

1. **`Docs/Architecture/AUTHORITY.md`**
   - source precedence;
   - durable authority rules;
   - source/evidence freshness;
   - client boundary;
   - governed-write authority.

2. **`Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`**
   - the breaking semantic destination;
   - KnowledgeSpace / Entity / Assertion / DomainContract design;
   - generic scope, visibility, temporal, source, contribution, identity, and migration contracts;
   - v1 → vNext break inventory;
   - DungeonBuddy domain responsibility;
   - bridge-genesis migration model.

3. **`Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`**
   - normalized immutable revision model;
   - revision-local derived indexes;
   - KnowledgeReadContext;
   - candidate-local admission;
   - targeted coherent provenance;
   - full projection as explicit O(N);
   - bounded-read/search/evidence/anchor optimization doctrine;
   - durable storage redesign as a later evidence-gated decision.

4. **`Docs/Roadmaps/ROADMAP.md`**
   - current V0–V11 sequence;
   - primary question and stop conditions for each phase;
   - parallelism allowed between DungeonMind and DungeonBuddy work;
   - final migration/cutover shape.

5. **`CONTRIBUTING.md`**
   - toolchain;
   - import/layering rules;
   - versioned durable-contract rules;
   - data hygiene;
   - PR discipline and handoff expectations.

6. **`Docs/Architecture/ARCHITECTURE.md`**
   - current pre-vNext implementation architecture;
   - current public World read/write behavior;
   - current ownership map;
   - R.3a cache/provenance safety rule.

   Treat this as the description of the **current implementation**, while the two vNext architecture documents describe the accepted destination.

7. **Accepted ADRs in `Docs/Decisions/`**, especially when touching their owned invariants.

   Frequently relevant:

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

8. **Performance evidence**

   ```text
   Docs/Benchmarks/BASELINE-world-graph-reads-r2a.md
   Docs/Benchmarks/BASELINE-world-graph-reads-r3a.md
   Docs/Handoffs/HANDOFF-cutover-direct-read-optimization.md
   Docs/Handoffs/HANDOFF-complete-selected-object-one-hop-read.md
   ```

9. **Architecture-fitness history**

   ```text
   Docs/Reports/REPORT-2026-08-23-independent-library-transition.md
   ```

   Deeper reconstruction evidence that did not land on main remains available on:

   ```text
   steward/post-cutover-library-critique
   ```

   including the K0 surface inventory, golden semantic witness, critique, and reconstruction roadmap. Use these as evidence when useful; do not let an archival branch outrank current main.

### Chat/history rule

If a conversation produces a real architectural decision, that decision is not durable until the appropriate checked-in architecture/roadmap/handoff is updated.

This handoff should point to the checked-in decision rather than preserving a parallel private truth.

---

## §4 Project mental model

DungeonMind exists because the project discovered that persistent knowledge authority should not belong to the product surface that happens to consume it.

The current implementation was extracted from DungeonMindBuddy and proven against a real adopted campaign/world authority.

The cutover earned several pieces of complexity:

```text
stable opaque identity
exact source/evidence provenance
immutable published revisions
explicit mutable head
expected-parent CAS
canonical hashing
fail-closed reads
replay/idempotency/recovery
governed publication
historical reconstructibility
```

Those survive vNext.

The breaking redesign exists because World-specific semantics leaked into supposedly generic contracts:

```text
world_id
campaign scope
GM / PLAYER
canon
session semantics
fictional time
World/Campaign/Cross-Campaign projection modes
```

The new boundary is intentionally simpler:

```text
DungeonMind knows
  identity,
  assertions,
  evidence,
  revisions,
  governance,
  generic admission,
  retrieval.

DungeonBuddy knows
  campaigns,
  GM/player meaning,
  TTRPG claim modes,
  fictional time,
  D&D vocabulary,
  product authorization,
  UI/agent workflows.
```

The genericization is not an excuse to weaken correctness.

The design principle is:

> **Make composition easy; make correctness non-configurable.**

---

## §5 Performance mental model

The performance roadmap is evidence-backed, not aesthetic.

R.2a showed that the current bounded reads effectively do:

```text
load/parse full revision
→ admit/project whole graph
→ return one small answer
```

At 10k objects, exact object, neighborhood, evidence, search, and anchors were measured in seconds because whole projection was the structural floor.

R.3a proved the first low-hanging correction:

```text
one coherent WorldGraphReadContext
+ parsed immutable revision reuse
+ one batched SourceProvenanceSnapshot
+ per-context evidence memo
```

Live Eldyrwild projection improved from roughly 20.7 seconds to roughly 115 ms warm with semantic parity.

The remaining structural target is:

```text
exact immutable revision
→ immutable normalized revision model
→ candidate/index lookup
→ targeted coherent provenance
→ generic admission
→ domain admission
→ bounded result
```

Binding safety rule:

```text
SAFE TO REUSE BY EXACT REVISION / COMPATIBILITY ID
  parsed immutable revision
  revision-local derived indexes

NOT SAFE TO CACHE BY REVISION ALONE
  source-authority verdict
  scope/visibility verdict
  admitted projection
  domain-admission result
```

Source/provenance state can change while a knowledge revision remains immutable.

Optimization order remains:

```text
1. avoid unnecessary work
2. avoid loading unnecessary data
3. avoid unnecessary copies/allocations
4. add immutable derived indexes
5. optimize serialization/hashing
6. redesign durable storage only if the preceding work is insufficient
```

The Steward must resist premature:

```text
Redis
distributed caches
Neo4j / graph-database migration
event sourcing
structural-sharing persistence
vector-first retrieval
cross-request authorization-result caches
```

unless a later measured phase explicitly earns them.

---

## §6 Critical implementation locations

Re-discover exact names at the current main before dispatching a PR; these paths describe the present architecture and likely transition seams.

### Current contracts

```text
src/dungeonmind/contracts/graph.py
src/dungeonmind/contracts/contribution.py
src/dungeonmind/contracts/knowledge_assertion.py
src/dungeonmind/contracts/evidence.py
src/dungeonmind/contracts/projection_v2.py
src/dungeonmind/contracts/semantic_profile.py
src/dungeonmind/contracts/identity.py
```

These contain many of the v1 → vNext breaks.

### Current graph normalization/read path

```text
src/dungeonmind/application/graph_snapshot.py
src/dungeonmind/application/world_graph_read_context.py
src/dungeonmind/application/world_graph_projection.py
src/dungeonmind/application/world_graph_retrieval.py
src/dungeonmind/application/graph_scope.py
src/dungeonmind/application/source_provenance_snapshot.py
src/dungeonmind/application/parsed_revision_cache.py
```

### Repository boundaries

```text
src/dungeonmind/application/repositories.py
src/dungeonmind/infrastructure/memory/
src/dungeonmind/infrastructure/postgres/
```

### Domain/profile boundary

```text
src/dungeonmind_dnd/
```

The generic Kernel must not gain a dependency on the D&D package.

### Compatibility/history

The current versioned graph readers, adoption/reviewed-initialization logic, and migration receipts remain required historical machinery until V10 proves they can be quarantined or physically removed.

Do not delete historical readers because vNext has a cleaner current model.

---

## §7 DungeonMindBuddy relationship

DungeonMindBuddy is the first real consumer and a critical acceptance witness.

It is not DungeonMind semantic authority.

Cross-repository rule:

> Land separate PRs in separate repositories, but bind them to one exact contract identity when they participate in the same roadmap phase.

The expected split is:

```text
DungeonMind
  generic contracts
  generic authority/read/write behavior
  storage/adapters
  contract fixtures

DungeonMindBuddy
  DungeonBuddy DomainContract
  D&D semantic profile usage
  campaign/session mapping
  GM/player audience-label mapping
  fictional-time adapter
  product DTO mapping
  product authorization
  UI / agent / work-surface behavior
```

V0 must make it possible for both sides to work without silently inventing their own interpretation.

V6 is the explicit Buddy domain implementation lane.

V8 is the joint acceptance lane.

V9 is the deliberate cutover.

Do not repin or cut Buddy over early merely because an intermediate DungeonMind implementation exists.

---

## §8 Stewarding one roadmap PR

Each implementation PR should have one primary question copied or refined from the roadmap.

Before dispatch:

1. Re-anchor `main` and relevant external consumer heads.
2. Read the current version of this handoff, the roadmap phase, and binding architecture sections.
3. Inspect the current code at the intended seam; do not dispatch based only on old reports.
4. Define a narrow write lease.
5. Name the semantic proof, performance proof, migration proof, or consumer proof required.
6. Name explicit stop conditions.
7. Record what is **not** being solved.

Use `Docs/Handoffs/HANDOFF-TEMPLATE.md` for individual slices.

### PR description as merge contract

The implementation PR description should state:

```text
primary question
base SHA
intended changed surface
binding invariants
required evidence
actual evidence
known failures / inherited red baselines
what remains false
named successor
```

### Review discipline

Review the exact head, not the branch name.

Record:

```text
base SHA
reviewed head SHA
logical review cycle
blocking findings
non-blocking findings
verification evidence
final disposition
```

If self-review restrictions prevent an `APPROVE`, a review/comment body may still explicitly record `PASS — merge-ready`, but the exact head must be named.

A docs-only bookkeeping commit after a substantive PASS does not require reopening the technical review unless it changes architecture, evidence, or behavior.

### Merge discipline

A PR merges only when its primary question has an evidence-backed answer.

Do not merge because:

```text
CI is green but the claimed proof was not run;
performance improved but semantic parity drifted;
tests were changed to accept the new result without an explicit contract decision;
the implementation is "close enough" and a future PR can repair the invariant;
Buddy can work around a missing Kernel contract;
```

---

## §9 Steward handoff mutation protocol

**This document is intentionally mutable.**

It is not historical evidence that should remain frozen forever.

Its purpose is to describe the current stewardship state accurately enough that a new agent can resume immediately.

### Mandatory update cadence

After every roadmap PR is merged, the Steward should update this file before another roadmap PR is allowed to merge.

Preferred forms:

1. **Immediate successor branch:** update this file as the first bookkeeping change when dispatching the next roadmap slice; or
2. **Tiny stewardship sync PR:** if no successor begins immediately, land a docs-only checkpoint.

Do not allow more than one roadmap merge to accumulate without a stewardship update.

### What every update must record

At minimum update:

```text
current main / accepted merge anchor
current roadmap phase and disposition
last merged roadmap PR
exact accepted implementation head if relevant
review-cycle count / final PASS reference when useful
new proof artifacts or benchmark baselines
architecture decisions learned or changed
new stop conditions / risks discovered
what remains false
next primary question
parallel work that is now safe
parallel work that remains blocked
```

### Keep this document useful, not archival

Do not append an endless diary.

Maintain:

- a concise **Current checkpoint**;
- the current resource map;
- currently binding lessons;
- the last few meaningful roadmap transitions where they help re-entry;
- current next question and blockers.

Move detailed history to PRs, ADRs, reports, or Git history.

The Steward may rewrite obsolete sections of this handoff as the project changes.

### When this handoff itself must trigger architecture docs

This file may summarize and route decisions. It must not become a hidden architecture layer.

If the Steward concludes that an accepted decision changes:

```text
semantic contracts
ownership boundaries
migration model
read/performance architecture
roadmap ordering / gates
```

update the relevant canonical architecture/roadmap document in the same docs change set.

Then update this handoff to point to the new authority.

---

## §10 Invariants the Steward protects across the entire roadmap

1. **Immutable published history is never rewritten.**
2. **One explicit head selects current truth; timestamps do not.**
3. **Expected-parent CAS remains the publication concurrency boundary.**
4. **Evidence/source state participates in knowledge validity.**
5. **Unknown or broken authority fails closed.**
6. **Retrieval/ranking never manufactures authority.**
7. **Stable IDs remain opaque and durable.**
8. **Domain policy may narrow generic admission, never broaden rejected knowledge.**
9. **DungeonMind does not become the product agent harness.**
10. **DungeonBuddy is replaceable as a client and does not define generic Kernel vocabulary.**
11. **Genericity does not mean untyped property-bag semantics.**
12. **Derived indexes remain rebuildable and non-authoritative.**
13. **Bounded reads must not require full-space projection by design in vNext.**
14. **Source/provenance freshness is not hidden by revision-only authorization caching.**
15. **Performance credit requires semantic parity first.**
16. **Historical readability is preserved even when historical machinery leaves the hot path.**
17. **Migration preserves durable IDs wherever the meaning is unchanged.**
18. **No long-lived dual-write architecture is introduced merely to make cutover comfortable.**
19. **Storage-model complexity remains evidence-gated until V11.**
20. **One PR has one primary question.**

---

## §11 Roadmap-specific stewardship expectations

### V0 — contract freeze

Steward focus:

- exact type/schema decisions;
- no fields invented independently by Buddy and DungeonMind;
- distinguish DomainContract from SemanticProfile;
- ensure bounded reads are possible without a precomputed full projection;
- require the three acceptance fixture families.

Exit disposition:

```text
VNEXT_CONTRACT_FROZEN
```

### V1 — normalized immutable revision

Steward focus:

- compatibility reader → one generic current model;
- deterministic derived indexes;
- immutability / mutation isolation;
- no scope/visibility policy in the parser;
- no persistence rewrite.

### V2 — KnowledgeReadContext

Steward focus:

- candidate-local admission;
- coherent targeted provenance;
- generic scope / visibility / standing;
- pure pinned domain admission;
- source freshness across contexts.

### V3 — exact / complete entity

Steward focus:

- selected entity completeness;
- no ordinary caps defining truth;
- no full projection in bounded read path;
- >24-edge / >32-anchor witnesses;
- structural work counts and 10k characterization.

### V4 — neighborhood/evidence/anchor/search

Steward focus:

- adjacency/support indexes;
- candidate generation before admission;
- deterministic ranking;
- no vector escalation without evidence.

### V5 — governed writes

Steward focus:

- typed contribution union;
- native JSON values;
- exact parent/content binding;
- replay/recovery;
- benchmark large-parent + tiny-delta writes;
- do not redesign durable revision storage yet.

### V6 — Buddy domain

Steward focus:

- campaign/GM/player/fictional-time semantics move out of generic Kernel;
- no authority bypass;
- DungeonMind has no Buddy import.

### V7 — bridge genesis

Steward focus:

- freeze exact legacy authority point;
- deterministic migration manifest;
- preserve IDs;
- old history untouched;
- no fake native parentage between v1 and vNext.

### V8 — joint acceptance

Steward focus:

- exact commits/digests on both repositories;
- DungeonBuddy preservation fixture;
- organizational-memory non-TTRPG fixture;
- adversarial epistemic/identity fixture;
- semantic equality where meaning is intended to survive;
- large-scale performance characterization;
- explicit resource-limited cases.

### V9 — cutover

Steward focus:

- freeze old writes;
- atomic/admissible authority transition;
- rollback/fix-forward plan;
- Buddy exact contract pin;
- no silent split-brain authority.

### V10 — quarantine old current paths

Steward focus:

- current API no longer exposes World-era transports as first-class contracts;
- historical readers remain where required;
- no migration-history logic in normal vNext reads.

### V11 — deeper storage optimization

Steward focus:

- begin only if V1–V8 measurements show the need;
- preserve logical immutable revisions regardless of physical representation;
- benchmark against the three useful baselines: old current path, normalized/indexed vNext path, and proposed storage change.

---

## §12 Stop / rebrief conditions

Stop and explicitly redesign rather than improvising if:

- the frozen contract cannot represent DungeonBuddy semantics without putting World vocabulary back into the Kernel;
- a second non-TTRPG fixture requires changing generic contracts in ways the DomainContract boundary cannot explain;
- candidate-local admission cannot preserve current fail-closed provenance semantics;
- a bounded read can only be implemented by silently broadening scope/visibility;
- historical v1-v6 state must be rewritten to create the vNext model;
- stable identity would need to be discarded for convenience;
- the proposed optimization requires caching mutable source-authority results without coherent state identity;
- an implementation PR unexpectedly requires a durable schema/storage rewrite before V7/V11;
- Buddy needs to reconstruct a foreign graph to compensate for an incomplete DungeonMind read contract;
- test expectations need to be weakened without an explicit contract decision;
- a migration requires long-lived dual writes with unclear authority;
- the roadmap ordering itself is falsified by implementation evidence.

Required response to a stop condition:

```text
Stop condition:
Roadmap phase:
Observed evidence:
Which current assumption failed:
Affected authority/architecture document:
Why the current PR cannot safely compensate:
Proposed design decision / experiment:
What remains safe to continue in parallel:
```

Then update architecture/roadmap docs before resuming implementation if the decision is architectural.

---

## §13 Current stewardship ledger

Keep this section short and current.

### Last canonical roadmap change

```text
DungeonMind PR #57
KERNEL: immutable ParsedKnowledgeRevision core and structural indexes
merged: 6d9a40f609530f4882470c5599b4914e2288b8d5
accepted implementation head: 38d9eac3252ba911ff7565b930ce8b84aca0767b
review cycles: 2 (Cycle 1 f240b09, Cycle 2 38d9eac)
final PASS review: 5213422370
disposition: V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED
benchmark artifact: Docs/Benchmarks/vnext_parsed_knowledge_revision_10k_v1.json
cardinalities:
  assertions: 10,000
  entities: 5,000
  evidence refs: 2,500
  aliases: 2,000
build: ~7004.647 ms
peak traced memory: ~48.53 MiB
semantic digest: 8b51a341d7464710be1410421a843d31fa2e84e9387d0043e131575d44d2379d
compatibility key: b795c672dbf87394b83ebaba42976b54994b257ed5beefa93b7cc184f82bc9e5
indexed lookups: microsecond-scale characterization
contract aggregate sha256: fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

It established:

- Application-layer vNext normalized model and builder in `src/dungeonmind/application/vnext/`;
- Deep immutability via `FrozenDict` and `freeze_json_value`, with mutation attacks cleanly rejected;
- Domain-agnostic, rebuildable structural indexes: `entities_by_id`, `assertions_by_id`, `aliases_by_id`, `evidence_by_id`, `assertions_by_subject`, `entity_adjacency` (incoming/outgoing/touching), `alias_exact_index`, `literal_exact_index`, and `lexical_candidate_index`;
- Fail-closed structural integrity enforcement (`RevisionStructuralIntegrityError`) on duplicate IDs, missing assertion subjects, missing entity-ref targets, missing evidence refs, missing alias targets, and malformed visibility/temporal variants;
- Exact revision-header identity preservation, including contract sequence of `operation_ids`;
- Pinned compatibility key covering parser format version, graph schema, and complete pinned `DomainContractRef` and `SemanticProfileRef` identities;
- Zero modifications to frozen V0 contract bundle (`fd04a904...`) and zero imports from `dungeonmind_dnd`.

Prior roadmap baseline:
- DungeonMindBuddy PR #719 (`c77056b0c909513cecd8b81f9e7fac22e02d339a`): V0.2 consumer proof (`VNEXT_CONTRACT_FROZEN`).
- PR #56 (`63ec810a02f18c4e25af228f6fdb19d99d12579e`): V0.1 generic vNext schema surface (`fd04a904...`).
- PR #54 (`22bf2e42686876e1c0f9750d1b346e4a6fffebc4`): canonized vNext execution and optimization roadmap.

### Current phase

```text
V0 COMPLETE — VNEXT_CONTRACT_FROZEN
V1 ACTIVE
V1.1 COMPLETE
V1.2 ACTIVE
```

### Next primary question

```text
Can every frozen historical dm_union_graph_v1 through dm_union_graph_v6 stored revision be verified and decoded into the accepted immutable ParsedKnowledgeRevision with deterministic semantic parity to the current historical reader, without rewriting history, performing admission, or pretending legacy payloads are native vNext authority?
```

### Parallel work posture

```text
safe / independent:
  larger-scale benchmark characterization
  already-contract-frozen Buddy/domain work that does not depend on V2 runtime

still blocked by V1 completion:
  V2 merge
  V3+ Kernel read-path rollout
  bridge-genesis migration
  cutover
  deletion/quarantine of current public historical readers
```

### What remains false

At this checkpoint:

- v1-v6 -> ParsedKnowledgeRevision compatibility parity is not yet proven (active slice V1.2);
- overall V1 is not complete;
- V2 is not yet active;
- current public World readers still use the historical path;
- no bridge-genesis migration has occurred;
- no vNext cutover has occurred;
- no `KnowledgeReadContext` exists;
- no `KnowledgeSpace` runtime exists;
- bounded reads still run through the current World architecture;
- DungeonBuddy has not yet implemented runtime World read/write cutover (V6);
- no vNext authority has been published;
- old World contracts remain current production contracts;
- larger K0.3 50k/100k characterization is not complete;
- deeper storage optimization is not authorized.

### Named next action

Dispatch **V1.2: legacy v1–v6 compatibility decoder + semantic parity** from DungeonMind `main` anchor `6d9a40f609530f4882470c5599b4914e2288b8d5` (branch `kernel/v1-2-legacy-compatibility-parity`, handoff `Docs/Handoffs/HANDOFF-v1-2-legacy-compatibility-parity.md`).

---

## §14 Steward completion condition

This handoff remains `ACTIVE` through the roadmap.

It may be marked `SUPERSEDED` only when one of the following is true:

1. V10/V11 completes and a new steady-state stewardship model is checked in; or
2. the roadmap is deliberately replaced by a new canonical program and a successor Steward handoff is merged.

Do not mark it `LANDED` merely because this file was merged. The file landing starts stewardship; it does not complete it.
