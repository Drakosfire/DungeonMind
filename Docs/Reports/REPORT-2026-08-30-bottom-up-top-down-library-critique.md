# Report — 2026-08-30 Bottom-up / Top-down DungeonMind Library Critique

**Status:** ACTIVE CRITIQUE — evidence-backed architecture-fitness synthesis; not a rewrite authorization  
**Audit pin:** `5ca5d688612349034f8ca490d465af166d883e6e`  
**External consumer evidence:** DungeonMindBuddy pinned exactly to the same DungeonMind revision during this audit  
**Steward branch:** `steward/post-cutover-library-critique`  
**Companion authority:** `Docs/Architecture/ARCHITECTURE.md`, `Docs/Architecture/AUTHORITY.md`, accepted ADRs  

## Executive conclusion

DungeonMind should **not** be rewritten from scratch. The cutover proved that several difficult parts are real, valuable, and worth preserving: stable knowledge identity, source/evidence provenance, immutable revision identity, explicit head CAS, fail-closed reads, governed exact-parent publication, replay/recovery, and deterministic canonicalization.

But the repository is not yet the small independent library its own architecture describes.

The implementation currently contains at least four different historical layers under one public package:

```text
A. authority kernel
   identity / canonicalization / evidence / immutable revisions / CAS publication

B. World Graph domain
   world / campaign / session / GM-player visibility / canon / fictional time
   World Graph projection and retrieval semantics

C. migration + compatibility machinery
   existing-world adoption / correspondence / repair / reviewed-first-world genesis
   six graph generations and migration-specific compatibility

D. founding agent + retrieval runtime
   MindTurn / capability policy / agent adapters / thread and retrieval sessions
   semantic documents / embeddings / context assembly / demo surfaces
```

The central architectural mistake is not that B, C, or D ever existed. They were useful in discovering and proving the system. The mistake would be allowing all four to remain **architecturally central** now that the migration is complete.

The counterfactual answer is therefore:

> The irreducible DungeonMind Kernel is substantially smaller than `src/dungeonmind` today. The World Graph is a first-class domain built on that Kernel, not evidence that every durable knowledge domain should be modeled as a World. Migration compatibility is a codec/compatibility concern, not a hot-path responsibility. Agent orchestration is a client concern and should leave the library.

A future Rules integration makes this distinction concrete rather than speculative. Rules knowledge needs the same identity, evidence, revision, publication, and graph structure, but it does **not** naturally have campaign scope, GM/PLAYER visibility, fictional time, or Buddy's human Graph Review lifecycle. A good Kernel must allow both without weakening either domain's correctness model.

The target should be **smaller in code, more general in shape, and much faster on point reads**.

---

## 1. The standard used for this critique

For every meaningful subsystem, ask all of the following:

1. **Counterfactual:** If this did not exist today, would we build it again for the consumers and correctness properties we now have?
2. **Correctness:** What concrete failure does it prevent?
3. **Consumer:** Who actually uses it now?
4. **Cost:** What runtime, conceptual, persistence, versioning, and testing cost does it impose?
5. **Composition:** Would the concept still make sense for deterministic rule knowledge rather than Eldyrwild lore?
6. **Domain honesty:** Is it genuinely generic, or is a World/Buddy/D&D assumption hidden behind a generic name?
7. **Extension evidence:** Has it enabled a materially different consumer/domain, or is future usefulness still hypothetical?

Classification vocabulary:

- `ESSENTIAL COMPLEXITY`
- `PRODUCTIVE ABSTRACTION`
- `UNPROVEN ABSTRACTION`
- `ACCIDENTAL COMPLEXITY`
- `HISTORICAL RESIDUE`

A mechanism may be **historically necessary** without remaining part of the current architectural center.

---

## 2. What the cutover proved we should keep

### 2.1 Immutable revision identity and explicit head

This earned its cost repeatedly: adoption, historical pins, governed children, rollback/fix-forward reasoning, native reads, and migration continuity all depended on exact identity.

Keep:

```text
immutable published revision
explicit mutable head
expected-parent CAS
rollback by head movement, never history rewrite
content digest verification
```

Classification: **ESSENTIAL COMPLEXITY**.

### 2.2 Evidence and source provenance

The cutover demonstrated that provenance changes what knowledge may be returned. Evidence is not presentation metadata. Source identity, source revision, lifecycle, visibility, and evidence chains are correctness inputs.

Keep the principle and improve its generality.

Classification: **ESSENTIAL COMPLEXITY**.

### 2.3 Governed publication

The important invariant is not "a human clicked Confirm in Graph Review." It is:

```text
candidate/proposed knowledge
→ validated policy decision
→ exact content binding
→ exact expected parent
→ atomic durable publication
→ idempotent/recoverable terminal result
```

Buddy's human review is one policy implementation of that invariant.

Classification: **ESSENTIAL COMPLEXITY**, with the current review vocabulary partly Buddy-shaped.

### 2.4 Canonical serialization and stable IDs

The migration repeatedly used canonical hashing as an integrity boundary. This is cheap, deterministic, and broadly useful.

Classification: **ESSENTIAL COMPLEXITY**.

### 2.5 Fail-closed integrity

Fail-closed behavior exposed hidden fallback, provenance, scope, identity, and lifecycle bugs that permissive behavior would have concealed.

Keep fail-closed handling for unknown authority state, contract mismatch, missing evidence identity, stale parent, and ambiguous identity.

Classification: **ESSENTIAL COMPLEXITY**.

### 2.6 Repository ports and optional infrastructure

Core imports only Pydantic. PostgreSQL/pgvector and FastAPI are optional extras. The generic package does not import `dungeonmind_dnd`. Those are healthy boundaries.

Keep the one-way dependency principle and transport-neutral application services.

Classification: **PRODUCTIVE ABSTRACTION**.

---

## 3. Bottom-up findings

## 3.1 The public API is a museum of implementation history

`src/dungeonmind/contracts/__init__.py` exports essentially every contract generation and every historical capability family: contribution/review v1 and v2, adoption receipts through V4, adoption repair and correspondence, MindTurn, projection v1/v2, retrieval sessions, semantic documents, reviewed-world initialization, capabilities, fictional time, and more.

`src/dungeonmind/application/__init__.py` repeats the pattern at the service layer.

This conflates three different promises:

```text
1. readable historical durable formats
2. supported current internal implementation types
3. intentional current client API
```

Those are not the same thing.

**Recommendation:** separate them explicitly.

```text
dungeonmind public facade          current supported client jobs
internal/current                   current implementation
compat/...                         old durable codecs and migration readers
```

Old durable formats must remain readable when required. They do not need to remain first-class imports for a new client.

Classification: **ACCIDENTAL COMPLEXITY** around an **ESSENTIAL** compatibility obligation.

---

## 3.2 The supposed generic Kernel contains World-domain policy

This is the largest architectural issue found.

Generic contracts currently encode:

- `world_id` as the root identity;
- `campaign_id` / `campaign_scope`;
- `session_id` / session focus;
- GM vs PLAYER visibility;
- canon state;
- world epistemic categories;
- fictional-time references;
- World/Campaign/Cross-Campaign projection modes.

`KnowledgeAssertionMetadataV1` is especially revealing: a supposedly shared knowledge assertion carries campaign scope, audience visibility, epistemic standing, canon standing, evidence, session references, and fictional time.

`SourceArtifactV2` is also structurally world-owned even though `SourceDomain` already includes `RULEBOOK`: every source artifact requires `world_id`.

`0001_postgres_substrate` makes the same assumption physically: worlds and campaigns are root tables; graph revisions, contributions, source artifacts, semantic documents, threads, and other records are world-bound.

These are good **World knowledge** semantics. They are not the irreducible semantics of all governed knowledge.

ADR-0004 explicitly left GM/player/canon/session policy in the Kernel "for now" pending concrete second-system evidence. That evidence now exists in RulesIngestion / RulesEngine.

Classification: **PRODUCTIVE WORLD-DOMAIN COMPLEXITY MISLOCATED AS GENERIC KERNEL**.

---

## 3.3 The profile boundary proved one thing and currently claims more than it provides

The semantic-profile identity mechanism is strong:

```text
profile_id
profile_revision
descriptor_sha256
admitted term namespaces
```

It keeps D&D vocabulary identity outside the generic package and makes profile selection durable rather than path/config identity.

But the descriptor itself is intentionally tiny. `dnd5e-v3.json` admits only the `dnd5e` namespace. The real executable D&D semantics live in a substantial sibling package containing contribution planning, candidate validation, mechanics, vocabulary, and materialization logic.

Therefore today's `SemanticProfile` is primarily:

> **pinned semantic namespace identity**

not:

> **a complete plug-in contract for a knowledge domain**.

That is fine. Do not respond by adding arbitrary executable hooks to the profile descriptor.

The more useful decomposition is likely two axes:

```text
Knowledge Domain
  WorldKnowledge
  RulesKnowledge
  future materially different domains

System Profile
  dnd5e-world
  dnd2024-rules
  pf2e-remaster-rules
  shadowrun4e-rules
  ...
```

A **domain** owns structural policy and authority semantics. A **profile** owns system vocabulary/schema within that domain.

Classification:

- pinned profile identity: **PRODUCTIVE ABSTRACTION**;
- "profile alone is the generic extension boundary": **UNPROVEN / INCOMPLETE ABSTRACTION**.

---

## 3.4 The current graph structure is more reusable than its metadata

The current v6 graph has useful generic ingredients:

- stable objects;
- stable relationships;
- independently identified assertions;
- aliases and properties as assertions;
- JSON-compatible property values;
- evidence references;
- qualified kinds/predicates;
- assertion-scoped endpoint aspects.

That structure can plausibly represent rule knowledge:

```text
Rule A --specializes--> Rule B
Exception C --overrides--> Rule B
Rule A --requires--> Condition D
Erratum E --supersedes--> Clause F
DefinedTerm G --used_by--> Rule A
```

The problem is the assertion metadata wrapped around it, not the idea of a governed property graph itself.

Classification: generic graph structure **PRODUCTIVE ABSTRACTION**; World metadata currently attached to every assertion is domain-specific.

---

## 3.5 Contribution V2 is a sum type encoded as a bag of optional fields

`GraphContributionAssertionV2` uses:

```text
assertion_kind: str
subject_object_id?
object_object_id?
predicate?
label?
value: str?
...
```

Then `ContributionReviewIntentV2` and the v6 materializer reconstruct the actual per-kind shape with procedural checks.

Worse for future rules, structured values are serialized by Buddy into JSON **strings**, then the v6 materializer calls `json.loads(assertion.value)` to recover a dictionary even though graph property values themselves already support canonical JSON values.

This is migration-shaped ceremony.

A future current contribution contract should be a discriminated union, for example:

```text
CreateObjectAssertion
AddRelationshipAssertion
AddAliasAssertion
SetPropertyAssertion[value: JsonValue]
Retract/SupersedeAssertion
```

The old V1/V2 contracts can remain compatibility formats.

Classification: current V2 transport shape **ACCIDENTAL COMPLEXITY / HISTORICAL COMPATIBILITY**.

---

## 3.6 The write lifecycle is too specifically "Graph Review" to be the universal governance model

Current v2 review hardcodes concepts such as:

- `reviewer_id`;
- assertion verdicts covering every candidate;
- explicit commit confirmation bound to reviewer/time;
- Buddy's reviewable assertion vocabulary;
- exact `dm_union_graph_v6` parent requirement.

That is excellent for the current human-authorized World workflow.

It is wrong as the universal future notion of governed publication.

A rules pipeline might authorize publication through a deterministic gate set:

```text
source/evidence contract valid
+ domain schema valid
+ rule packet validation valid
+ compiler valid
+ executable conformance fixtures pass
+ required review policy satisfied
```

The Kernel should own the **publication invariant**. Domain/workflow packages should own how authorization is earned.

Classification: publication core **ESSENTIAL COMPLEXITY**; current review protocol **PRODUCTIVE WORLD WORKFLOW**, not universal Kernel.

---

## 3.7 Historical compatibility is still in the normal read path

`WorldGraphProjectionService` checks reviewed-first-world initialization receipts on normal reads. `graph_scope.py` contains `GenesisEvidenceCompatibility` and explicit compatibility for the #645-family `OTHER` → `worldbuilding` provenance placeholder.

This was a legitimate cutover repair. It should not become permanent generic read semantics.

Likewise the versioned graph reader supports v1 through v6 inside the live application package, and graph scoping contains behavior for multiple historical grains.

**Recommendation:** preserve historical readability but move it behind a compatibility boundary:

```text
legacy stored revision
  → version-specific decoder / repair-aware compatibility reader
  → one current normalized in-memory graph model
  → current domain read logic
```

Do not make every current retrieval operation understand migration history.

Classification: **HISTORICAL RESIDUE on the hot path**, with **ESSENTIAL historical readability**.

---

## 3.8 Agent/harness ownership is already contradicted by the repository's current architecture

ADR-0022 says the agent harness is client-owned.

But the codebase still contains:

- `contracts/mind_turn.py`, which describes MindTurn as DungeonMind's primary interaction envelope and carries surface context/user messages;
- `application/mind_turn.py`, which imports agent adapters, capability policy, context assembly, semantic retrieval, thread state, and runs an agent;
- `agents/protocol.py`, which says DungeonMind orchestrates agent turns;
- `agents/fixture.py`;
- `CapabilityPolicy`, whose docstring says it is the sole authority for the agent-visible tool set;
- `MindThreadRepository` / `RetrievalSessionRepository`;
- PostgreSQL `mind_threads`, `mind_turns`, and retrieval-session tables.

The current Buddy production consumer does not use DungeonMind's `MindTurnService` or `dungeonmind.agents` path. Buddy owns its Hermes/tool/context orchestration separately.

**Recommendation:** runtime-excise first, physically demolish later. Preserve migrations while old databases still contain the tables, but stop treating the code/contracts as current library API. Move useful fixture/example material outside core or delete it.

Classification: **HISTORICAL RESIDUE**.

---

## 3.9 Semantic documents / embeddings are an unproven current DungeonMind responsibility

The founding PostgreSQL schema includes embedding runs, active embedding pointers, semantic documents, pgvector columns, and FTS indexes. The contracts are careful about provenance and correctly classify embeddings as derived/non-authoritative.

However:

- the current Buddy direct World Graph consumer does not use `SemanticDocumentRepository`;
- native graph retrieval is deterministic and graph-only;
- RulesIngestion already has a substantially more mature corpus retrieval/evaluation pipeline with corpus fingerprints, benchmark projections, promotion artifacts, and multiple systems.

Do not throw this work away blindly, but do not preserve it in the Kernel because "semantic search is useful."

Likely future shape:

```text
Kernel: derived-index extension seam + authority rules
Optional package/service: lexical/vector index implementation
RulesIngestion: rulebook retrieval/evaluation authority for its corpus substrate
```

Classification: **UNPROVEN ABSTRACTION / OPTIONAL DERIVED CAPABILITY**, not irreducible Kernel.

---

## 3.10 Current client ergonomics are not yet good enough

The current Buddy DungeonMind integration is semantically disciplined but physically large. At the audit pin, the integration directory includes large read/write adapters; `world_graph_reads.py` is ~84 KB and `world_graph_writes.py` is ~95 KB.

Some of this is unavoidable translation from Buddy's historical DTOs, and therefore must not be blamed on DungeonMind automatically.

But a second clean consumer should not need to know:

- repository bundle construction;
- graph reader construction;
- profile-registry wiring details;
- adoption/genesis receipt families;
- internal graph-version readers;
- PostgreSQL adapter internals;
- Buddy migration chronology.

The second-client test should have a deliberately small import and composition surface.

Classification: **PUBLIC API ERGONOMICS DEBT**.

---

## 3.11 The Clean-Architecture package names are carrying more ceremony than semantic separation

`src/dungeonmind/domain` is small (canonicalization, capability/error helpers, membership/fusion/revision IDs), while much of the actual domain model and invariants live in `contracts` and `application`.

Meanwhile `application/repositories.py` mixes:

- essential graph/source/contribution repositories;
- review/publication state;
- migration-specific adoption/repair;
- reviewed initialization;
- MindTurn/retrieval threads;
- semantic documents/embedding runs.

The layering rule is useful for import hygiene, but the current package map does not make the architectural center obvious.

Do not preserve a layer merely because "domain/application/infrastructure" looks clean on a diagram. Reorganize around responsibilities that a second consumer can actually understand.

Classification: **ACCIDENTAL ORGANIZATIONAL COMPLEXITY candidate**.

---

## 4. Performance teardown

## 4.1 R.3a was a real success

The live Eldyrwild direct-read optimization improved campaign-GM projection from about **20.7 seconds to 115 ms**, primarily by eliminating N+1 provenance loads and introducing one coherent read context plus parsed-revision reuse.

That is excellent evidence for:

- coherent read contexts;
- batched source/provenance loading;
- measured optimization;
- avoiding speculative cache infrastructure.

Keep those lessons.

## 4.2 The next scaling ceiling is already visible

The same benchmark shows warm synthetic cost still grows with graph size:

```text
10k objects
  projection        ~2.3–2.7 s
  exact object      ~2.18 s
  neighborhood d1   ~2.27 s
  neighborhood d2   ~2.20 s
  search            ~5.24 s
  source anchor     ~4.00 s
```

An exact object lookup taking seconds at 10k objects is not a viable foundation for larger rule corpora.

The reason is architectural: every retrieval operation opens a read context by parsing/loading the selected revision and performing a **full scoped projection** before selecting the small result it actually needs.

Current algorithmic shape:

```text
load whole revision
→ parse whole revision
→ load provenance snapshot for whole revision
→ admit/filter whole graph
→ exact lookup / neighborhood / search
```

For an exact lookup, this inverts the work.

Target shape:

```text
pin revision + authority/provenance view
→ identify candidate object/edge/assertion records
→ validate only evidence/scope needed by those candidates
→ return bounded result
```

Full graph projection remains a valid explicit operation. It should not be the compulsory precursor to every point read.

Classification: eager whole-graph admission on point reads **ACCIDENTAL COMPLEXITY / PERFORMANCE BOTTLENECK**.

## 4.3 Keep immutable logical snapshots; challenge the physical serving model

`WorldGraphRevision` stores a complete canonical graph payload. That is wonderfully simple for hashing, export, audit, migration, and replay.

It does not follow that every serving operation should deserialize/filter that full payload.

A potent design can keep:

```text
canonical immutable revision artifact = authority/checkpoint
```

while adding a derived serving representation:

```text
revision-bound object index
revision-bound adjacency index
revision-bound assertion/evidence index
optional lexical/vector candidate indexes
```

Derived indexes are never authority and can be rebuilt from the canonical revision.

Before normalizing the entire database, first test the smaller change: **lazy admission over the already parsed/indexed current snapshot**. Exact object and neighborhood operations may gain most of the needed speed without redesigning storage.

Only add normalized/indexed persistence if measurement still requires it.

---

## 5. A correctness issue the current read identity does not fully solve

An exact graph revision is immutable, but a scoped semantic read is not determined by graph revision alone.

Current projection deliberately revalidates against live source state:

```text
artifact status
artifact visibility
artifact ownership
current/bound source revision
source provenance validity
```

Therefore the same exact graph revision can produce a different admitted result later.

This was useful during cutover and is appropriate for a "what is currently authoritative?" read.

It is insufficient for:

- byte-reproducible historical semantic reads;
- deterministic Rules compilation;
- exact test replay against an old rule-knowledge state;
- safe long-lived caches keyed only by graph revision.

R.3a already exposes a deterministic `SourceProvenanceSnapshot.fingerprint`, but the snapshot is ephemeral and explicitly not durable authority.

### Counterfactual design direction

Separate two identities:

```text
knowledge revision
source/authority-state revision
```

Then define an exact semantic read identity over both, for example conceptually:

```text
AuthorityView {
  knowledge_revision_id
  source_state_revision_id
  domain_policy_revision
}
```

The names are intentionally provisional.

Current-head reads may advance when either graph knowledge or source authority changes. Historical reads can pin both and become truly reproducible.

Do **not** implement this merely because it is elegant. Prove it with the Rules canary described below, where deterministic compilation gives a concrete need for reproducible authority views.

Classification: current mutable-source/live-projection behavior is **PRODUCTIVE for current authority**, but **INCOMPLETE for reproducible multi-domain knowledge**.

---

## 6. Counterfactual architecture: what I would build today

The minimum useful system is better understood as concentric layers.

## 6.1 Layer 1 — Authority Kernel

This is the irreducible center.

```text
canonical JSON / hashing
stable opaque identities
source artifact + immutable source revision identity
immutable evidence references / anchors
immutable published knowledge revisions
explicit head + expected-parent CAS
contribution/proposal identity
publication transaction + idempotent recovery
retraction/supersession history where required
repository/transaction ports
fail-closed integrity errors
vendor-neutral observation hooks
```

The Authority Kernel does **not** know:

```text
campaign
session
GM vs PLAYER
fictional time
D&D
rule priority
errata
Hermes
selected text
conversation thread
FastAPI
pgvector
```

## 6.2 Layer 2 — Graph Kernel

DungeonMind is intended to be a graph provider, so a reusable graph layer is justified.

```text
object identity
assertion identity
relationship identity
aliases
JSON-valued properties
qualified semantic terms
identity decisions / redirect history where useful
exact object and relationship access
bounded traversal
source-anchor association
```

This layer should operate on domain-neutral assertion envelopes.

It should not hardcode World admission policy.

## 6.3 Layer 3 — Knowledge Domain

A knowledge domain owns structural correctness that is genuinely different between classes of knowledge.

### WorldKnowledge domain

```text
world identity
campaign scope
GM / PLAYER access policy
played/provisional/retracted canon semantics
session association
fictional time
world-specific projection/admission
```

### RulesKnowledge domain

Likely concepts to prove, not pre-invent:

```text
ruleset / edition scope
normative status
errata/supersession
precedence / exception relation
applicability conditions
rule-definition relationships
compiler/executable binding identity
```

A Rules domain should not need fake campaign/session/GM fields.

## 6.4 Layer 4 — System Profile

Profiles then provide system vocabulary and typed schema **within a domain**.

Examples:

```text
WorldKnowledge + dnd5e-world vocabulary
RulesKnowledge + dnd2024-rules vocabulary
RulesKnowledge + pf2e-remaster-rules vocabulary
RulesKnowledge + shadowrun4e-rules vocabulary
```

This preserves the strong profile digest/identity mechanism while avoiding a mega-plugin that owns everything.

## 6.5 Layer 5 — Derived capabilities and transports

```text
PostgreSQL adapter
in-memory reference adapter
FastAPI host
lexical index
vector index
exporters
CLI
Buddy adapter
Rules compiler adapter
```

These are replaceable. They do not define truth.

---

## 7. The provisional root abstraction: do not fake rules as Worlds

Current invariant:

> one World Graph per world

That remains an excellent **WorldKnowledge** invariant.

It should not force a rule corpus to pretend to be a fictional world.

A future generic root may look conceptually like:

```text
KnowledgeSpace / AuthoritySpace   # provisional naming only
  stable space identity
  knowledge-domain identity
  profile identity
  immutable revision lineage
  explicit head
```

Examples:

```text
world:eldyrwild
rules:dnd5e-2024
rules:pf2e-remaster
rules:shadowrun4e
```

Do not merge these into one giant graph merely because cross-domain links are useful.

Composition should be explicit:

```text
Buddy request
  WorldKnowledge revision: Eldyrwild D_B
  RulesKnowledge revision: dnd2024 R_17

RulesEngine build
  RulesKnowledge revision: dnd2024 R_17
  executable ruleset digest: X
```

If a World object needs to refer to a rule or mechanic in another space, use an explicit foreign reference with space/revision/object identity. Do not collapse different authority regimes into one graph head.

---

## 8. RulesIngestion → DungeonMind → RulesEngine

The three systems have naturally different jobs.

## 8.1 RulesIngestion owns evidence reconstruction

Current RulesIngestion architecture already has a strong boundary:

```text
PDF
→ deterministic SurfaceAST
→ EvidenceUnits
→ optional non-authoritative retrieval enrichment
→ typed Stage C rule packets
```

EvidenceUnits are the admissible evidence substrate.

DungeonMind should not rechunk the PDF or create a competing source-truth layer. It should register exact external source/evidence identities and govern semantic rule knowledge derived from them.

## 8.2 DungeonMind owns governed rule knowledge

Potential graph facts:

```text
Rule A specializes Rule B
Rule C is an exception to Rule B
Condition D enables Rule A
Term E is defined by Clause F
Erratum G supersedes Rule H
Rule I affects Resource J
```

DungeonMind answers:

> What rule knowledge has been accepted, what exact evidence supports it, what version is it, what does it relate to, and what executable formalization is bound to it?

## 8.3 RulesEngine owns deterministic execution

RulesEngine's own specification correctly forbids inference and I/O inside rule evaluation.

Therefore RulesEngine should **not** query DungeonMind during the hot evaluation loop.

Integration should happen at a build/load boundary:

```text
pinned RulesKnowledge authority view
→ deterministic compiler / mapper
→ executable ruleset artifact
→ RulesEngine evaluation
```

RulesEngine traces can carry DungeonMind rule IDs / evidence refs for explanation and validation without making DungeonMind part of runtime determinism.

## 8.4 The feedback loop can teach ingestion

This is the unusually valuable part.

Rules understanding can be evaluated as a ladder:

```text
recover source text
→ bind exact evidence
→ identify atomic rule
→ connect definitions/exceptions/precedence
→ produce structured rule packet
→ compile
→ execute deterministic fixtures
→ replay expected outcomes
```

A failure at the executable end becomes a diagnostic signal for Stage C extraction/interpretation quality.

It is not automatic authority. It is evaluation evidence that can improve RulesIngestion prompts/models/rules/schema.

Keep three identities distinct:

```text
source / EvidenceUnit identity
DungeonMind rule-knowledge identity + revision
RulesEngine executable rule/ruleset identity + build digest
```

That separation will make debugging and learning far easier.

---

## 9. Configurable/composable without becoming configuration soup

The design should be highly composable, but correctness must not be optional.

### Good configuration

```text
storage adapter
knowledge domain
system profile
transport host
derived retrieval/index providers
observation sinks
source-body provider
compiler/export adapter
```

### Bad configuration

Do not add switches such as:

```text
use_provenance = false
immutable_revisions = false
fail_closed = false
require_exact_parent = false
```

Those are Kernel invariants.

Design rule:

> **Make composition easy; make correctness non-configurable.**

Prefer a few narrow protocols over a universal plugin hook system.

---

## 10. Architecture-fitness ledger

| Mechanism / subsystem | Classification | Reason / disposition |
|---|---|---|
| Canonical serialization + hashing | ESSENTIAL COMPLEXITY | Integrity and deterministic identity repeatedly paid for themselves |
| Immutable revisions + explicit head CAS | ESSENTIAL COMPLEXITY | Adoption, history, publication, rollback, exact pins |
| Source/evidence identity + provenance | ESSENTIAL COMPLEXITY | Changes semantic admissibility; real cutover proof |
| Exact-parent governed publication + recovery | ESSENTIAL COMPLEXITY | Prevents stale/duplicate/partial writes |
| Fail-closed integrity model | ESSENTIAL COMPLEXITY | Repeatedly exposed real migration bugs |
| Repository transaction ports | PRODUCTIVE ABSTRACTION | Keeps authority independent of Postgres/in-memory implementation |
| Coherent read-context concept | PRODUCTIVE ABSTRACTION | 180× live improvement; semantic coherence preserved |
| Vendor-neutral read observability | PRODUCTIVE ABSTRACTION | Small, privacy-safe, non-authoritative, directly useful to performance work |
| Profile identity/digest/namespace admission | PRODUCTIVE ABSTRACTION | D&D meaning stays outside generic package; identity is durable |
| Generic property-graph structure | PRODUCTIVE ABSTRACTION | Objects/relationships/assertions/evidence can plausibly serve multiple domains |
| D&D sibling package + one-way dependency | PRODUCTIVE ABSTRACTION | Real domain separation; keep |
| Identity decisions / merge/split/alias history | PRODUCTIVE, REVALIDATE IN SECOND DOMAIN | World proved value; Rules may also need stable rule identity/supersession |
| In-memory reference implementation | PRODUCTIVE ABSTRACTION | Useful for conformance and fast tests if semantic parity remains strict |
| Full canonical JSON graph snapshot as audit/checkpoint | PRODUCTIVE ABSTRACTION | Simple, hashable, exportable authority artifact |
| Full canonical snapshot as compulsory serving path | ACCIDENTAL COMPLEXITY | Point reads scale with whole graph |
| Eager full scope projection before exact lookup/neighborhood | ACCIDENTAL COMPLEXITY | 10k point reads are seconds |
| `KnowledgeAssertionMetadataV1` as generic Kernel metadata | MISLOCATED WORLD COMPLEXITY | Campaign/visibility/canon/session/time are not universal knowledge semantics |
| `SourceArtifactV2.world_id` mandatory for all domains including RULEBOOK | ACCIDENTAL GENERICITY FAILURE | Forces non-world sources into a fictional-world root |
| World/Campaign/GM/PLAYER projection contracts in generic package | MISLOCATED WORLD COMPLEXITY | Keep in WorldKnowledge domain |
| SemanticProfile as complete extensibility mechanism | UNPROVEN ABSTRACTION | Current descriptor is namespace identity; real behavior lives elsewhere |
| Contribution V2 bag-of-optionals + JSON-string value | ACCIDENTAL COMPLEXITY | Procedural shape recovery; poor structured-rule fit |
| Human ContributionReview as universal publication policy | MISLOCATED WORKFLOW COMPLEXITY | Keep as World/Buddy policy implementation, not Kernel invariant |
| v1-v6 graph parsing inside current application path | HISTORICAL COMPATIBILITY COST | Preserve decoding, normalize behind compatibility boundary |
| reviewed-init genesis provenance compatibility on normal reads | HISTORICAL RESIDUE ON HOT PATH | Needed for known history now; retire from generic path after durable replacement proof |
| existing-world adoption/correspondence/repair as current public API | HISTORICAL RESIDUE | Preserve durable readers/receipts under compat; stop making new clients learn it |
| MindTurn | HISTORICAL RESIDUE | Explicitly superseded by ADR-0022; current production client owns harness |
| `agents/` protocol + fixture | HISTORICAL RESIDUE | Move to examples/tests or delete |
| CapabilityPolicy / agent-visible tool authority | HISTORICAL RESIDUE | Client/harness responsibility under ADR-0022 |
| MindThread / retrieval-session persistence | HISTORICAL RESIDUE unless independent consumer appears | Do not keep in Kernel for hypothetical agent use |
| Context assembly / answer claim validation | LIKELY CLIENT CONCERN / UNPROVEN LIBRARY OWNERSHIP | Re-evaluate components individually before removal |
| SemanticDocument / embedding runtime | UNPROVEN OPTIONAL CAPABILITY | No current Buddy consumer; RulesIngestion owns stronger retrieval research |
| pgvector/FTS derived indexes | UNPROVEN IMPLEMENTATION | Keep optional only if future measured read workload justifies them |
| FastAPI host | OPTIONAL PRODUCTIVE ADAPTER | Cheap if it remains outside core import/runtime semantics |
| `demo_access` | HISTORICAL / EXAMPLE candidate | Not library architecture |
| giant contract/application `__init__` re-export surfaces | ACCIDENTAL COMPLEXITY | Replace with intentional current facade + explicit compat imports |
| giant mixed repository protocol module | ACCIDENTAL ORGANIZATIONAL COMPLEXITY | Split by authority responsibility after consumer map |

---

## 11. Successor ladder

Do not combine this into one rewrite. Use the Buddy pin as an experimentation firewall.

### K1 — Freeze and measure the actual current public/consumer surface

**Purpose:** produce a machine-checkable import/consumer map before demolition.

Prove:

- every symbol Buddy imports from DungeonMind at the exact pin;
- every exported symbol with no external consumer;
- every database table/repository used by current graph read/write/init paths;
- package import boundaries;
- baseline test cohorts and R.3a performance.

No behavior change.

### K2 — Runtime-excise the founding agent/harness subsystem

Target:

```text
MindTurn
agents/
CapabilityPolicy as agent-tool authority
context assembly owned only by MindTurn
MindThread / retrieval-session runtime wiring
```

First remove from current public/composition surfaces and prove no current consumer. Physical DB/table deletion is a separate migration after compatibility review.

### K3 — Quarantine migration/history compatibility

Move current architecture toward:

```text
compat/
  graph_v1_v6 codecs
  existing_world_adoption
  adoption_repair
  correspondence
  reviewed_init_v1 compatibility
```

Current code consumes one normalized model after decode.

Do not delete the ability to reconstruct living Eldyrwild state.

### K4 — Lazy-admission read experiment

This is the first performance successor I would prioritize.

Keep the current canonical revision and source snapshot semantics. Change only the work shape for point operations:

- exact object does not fully project the graph;
- neighborhood scopes only visited candidates;
- evidence validates only requested targets;
- full projection remains explicit;
- search uses a candidate index before admission if needed.

Benchmark at 1k / 10k / at least one larger synthetic rules-like graph.

**Candidate performance goals for the experiment, not architecture promises:**

```text
10k warm exact object        < 25 ms
10k warm depth-1 neighborhood < 50 ms
10k warm deterministic search < 100 ms
```

If those are unrealistic in the current physical model, let evidence justify the next indexing/storage change.

### K5 — RulesKnowledge canary before generic refactor

Use one tiny real RulesIngestion vertical slice, preferably the existing D&D 2024 occupancy default + ally-prone exception because it already has explicit grounding/evidence intent.

Attempt to represent and retrieve it through DungeonMind **without**:

- fake world/campaign/session identity;
- fake GM/PLAYER visibility;
- fake canon semantics;
- JSON-string encoding of structured conditions;
- putting RulesEngine execution in DungeonMind.

Expected result: current contracts should fail this ergonomics test in specific, measurable ways. Capture exactly which concepts force the mismatch.

Then repeat with one non-D&D rules packet when available (PF2e, Shadowrun, Starfinder, or S&W) to test system-profile generality.

### K6 — Split Authority/Graph Kernel from WorldKnowledge using K5 evidence

Only after the canary identifies real seams:

- make the root authority identity domain-neutral;
- move campaign/session/GM-player/canon/fictional-time into WorldKnowledge;
- introduce domain-policy identity/versioning if required;
- retain profile digest/namespace identity;
- introduce a RulesKnowledge domain only for semantics proven by the canary.

No universal ontology interpreter.

### K7 — Reproducible authority-view experiment

Use Rules compilation/replay to decide whether source-authority state needs durable revision identity alongside graph knowledge revision.

Prove that a pinned rule-knowledge input can be rebuilt byte-for-byte after source lifecycle/errata changes.

If required, introduce the smallest durable authority-view/source-state revision model that satisfies the proof.

### K8 — Current public facade + tiny second client

A clean client should be able to do current jobs through an intentional facade without importing repository bundles or internal graph readers.

A minimal target ergonomics probe:

```text
open/configure store
open exact/head read context
get object
search
neighborhood
evidence/anchor
submit governed publication
initialize a new knowledge space/domain
```

The facade may be thin wrappers over explicit services; do not create a god object.

### K9 — Derived-index / physical serving experiment only if K4 requires it

Potential options, in increasing complexity:

1. in-process immutable per-revision indexes;
2. PostgreSQL derived object/edge/assertion indexes keyed to exact revision;
3. content-addressed immutable record store + revision membership;
4. more sophisticated delta/materialization only if scale proves necessary.

Authority remains the canonical revision/ledger; indexes remain rebuildable.

---

## 12. Things I would explicitly not build

- No giant "universal TTRPG ontology."
- No fake World record used merely to fit rulebooks into current tables.
- No single graph head mixing Eldyrwild events and D&D/PF2e rules authority.
- No plugin system with arbitrary executable hooks everywhere.
- No correctness flags that can disable provenance/revision/CAS/fail-closed invariants.
- No RulesEngine network/query calls during deterministic rule evaluation.
- No second vector/retrieval research stack inside core when RulesIngestion already owns the corpus experiment loop.
- No broad database normalization rewrite before lazy-admission benchmarks.
- No deletion of historical codecs/receipt readers until exact Eldyrwild reconstruction remains proven.
- No Buddy repin during the critique merely to make experimentation convenient.

---

## 13. Proposed north star

A more durable statement than "governed world-knowledge library" is:

> **DungeonMind is a small, deterministic, provenance-first authority and graph library for versioned knowledge. It owns knowledge identity, evidence, revision, publication, and graph integrity. Knowledge domains own what those facts mean and how they are admitted. Clients own how users and agents act on them.**

World knowledge is the first proven domain.

Rules knowledge should be the next adversarial domain.

That does not make DungeonMind a generic framework. It makes the central invariants smaller and harder, while allowing domain packages to remain opinionated.

---

## 14. What "fast and impressive" should mean

Not a demo that hides complexity behind a model call.

The impressive version is:

- exact identity and citations survive ingestion, correction, publication, reload, and cross-product use;
- point reads stay fast as the graph grows;
- a second domain can be added without editing the authority Kernel everywhere;
- deterministic RulesEngine builds pin exact rule knowledge and evidence;
- an ingestion error can be traced from executable failure → rule object → assertion → EvidenceUnit → exact source span;
- historical state is reproducible;
- the current public API is small enough that a new client is obvious to write;
- optional capabilities remain optional;
- deleting a product/harness integration does not damage knowledge authority.

The current system already has several of the hardest ingredients. The next phase should spend that architectural capital by **removing ceremony and making the proven invariants cheaper to consume**, not by adding another abstraction layer on top of the existing pile.

---

## 15. Immediate recommendation

After the Buddy CUTOVER documentation PR closes, do **not** begin with a generic `KnowledgeSpace` implementation.

Start with two evidence-producing slices:

1. **K1 consumer/public-surface inventory**, so demolition is safe.
2. **K4 lazy-admission read experiment**, because the current 10k scaling is already a concrete constraint.

Then run **K5 RulesKnowledge canary** before committing the domain/root abstraction.

That order protects the strongest lesson from the cutover:

> Real consumers and adversarial data should earn abstractions. Architecture should not get credit for futures it has not survived yet.
