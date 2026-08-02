# DungeonMind — Architecture and Ownership

**Status:** founding (v0.1.0, PR A / A.1)
**Authority:** this document + `AUTHORITY.md` + ADRs. Where this disagrees with
any other source, see `AUTHORITY.md` precedence.

## 1. What DungeonMind is

DungeonMind is a governed context and knowledge runtime for persistent
fictional worlds. It owns durable world knowledge, revision-aware graph
projections, semantic retrieval, evidence admission, context assembly, and
capability-bounded agent interaction. Product surfaces consume it but do not
own its behavior.

```text
Product Surface
  LandingPage / Plan / Play / Build / future clients
        │  surface context + user message (MindTurnRequest)
        ▼
DungeonMind
  scope and revision resolution
  exact identity resolution
  semantic profile resolution + qualified-term admission
  semantic and lexical candidate retrieval
  graph traversal
  evidence admission
  retrieval-session state
  context budgeting
  agent orchestration
  capability policy
  answer validation
  semantic response projections
        ▼
Knowledge substrate
  PostgreSQL (relational identity + JSONB payloads)
  pgvector-derived indexes (disposable, rebuildable)
  source artifacts / object storage
  immutable graph revisions, contributions, evidence

Semantic profile layer (side boundary, one-way — PR B.2b/B.2c)
  profile descriptors pinned by id + revision + digest
  (e.g. the dungeonmind_dnd D&D 5e profile package)
  resolved through a registry port fed by operator config;
  the kernel never imports a profile package

Profile-side candidate layer (PR B.2c — dungeonmind_dnd only)
  vocabulary catalog (exact kinds/predicates + direction)
  strict provenance-bearing candidate contracts
  deterministic candidate validation and prompt/schema rendering
        no graph read/write authority, no identity resolution,
        no publication, no LLM
```

## 2. Governing invariant

> DungeonMind owns knowledge, retrieval, evidence, context assembly, and
> capability policy independently of any UI, agent provider, database adapter,
> or sibling application repository.

Supporting invariants (closed — see `AUTHORITY.md` §3):

1. The World Graph is authoritative materialized knowledge; vectors are
   disposable retrieval indexes.
2. Source artifacts and admitted evidence remain the basis for factual support.
3. Every read operates against one explicit world, campaign scope,
   admissibility policy, and coherent graph revision. Admissibility and
   query visibility are required fields with no defaults — absence never
   means GM (PR A.1). Campaign ownership lives on the request/scope only;
   focus is chronology and never a second campaign authority.
4. Surfaces publish context and consume semantic results; they do not assemble
   graph queries or prompts.
5. Hermes is the first agent adapter, not the definition of DungeonMind.
   ``CapabilityPolicy`` is the sole authority for the agent-visible tool set.
6. DungeonMindServer may host consumers and existing product APIs; it never
   owns DungeonMind's graph or retrieval semantics.
7. No agent or surface receives silent durable write authority.
8. All integrations are replaceable ports, not moved filesystem assumptions.

## 3. Closed structural decisions (adopted from DungeonMindBuddy)

These were proven in DungeonMindBuddy and are not reopened by this repo
(implementation evidence of contradiction goes to an ADR, not a quiet edit):

- **One World Supergraph per world.** Campaign is a *scope* on assertions,
  evidence, chronology, and visibility — never a second graph. The schema
  encodes this; any "one graph per campaign" design is a stop condition.
- **Session is a lens**, not an ownership boundary.
- **Immutable, content-addressed published revisions** (`rev:<sha256-32>`).
- **One head per world**, advanced atomically by compare-and-swap with
  stale-parent rejection. Failed writes leave the previous head readable.
  "Latest row by timestamp" is never the head. Rollback is auditable
  repointing, never deletion.
- **Explicit identity outcomes** (`resolved_existing`, `created_new`,
  `provisional_new`, `ambiguous`, `blocked_collision`, `rejected`,
  `human_override`). Confidence is never authority. Merge/split/unmerge are
  durable, replayable decisions.
- **Governed contributions** are the only write unit into the graph
  (active | superseded | retracted | failed; idempotent reprocessing).
- **Source-grounded evidence**: excerpts only via graph-admitted anchors.
- **Revision-pinned projections**: a projection is a lens over one exact
  revision, never a store.
- **Separate read and write paths**; surfaces do not extract, extractors do
  not render, projection does not mutate identity.
- **No privileged agent writer.** Durable writes need typed capabilities
  (`read_only`, `draft_only`, `preview_write`, `confirm_commit`,
  `admin_diagnostic`) and explicit confirmation. Chat is never campaign truth.
- **Surfaces never own graph semantics** (identity resolution, revision
  selection, semantic-query construction, evidence admission, traversal
  policy, prompt assembly, canon/visibility policy, capability classification).

## 4. Ownership map

| Concern | Owner | Notes |
| --- | --- | --- |
| World Graph domain, revisions, head CAS, contributions, identity | **DungeonMind** | `domain/`, `contracts/` |
| Retrieval sessions, claim ledgers, coverage, answer validation | **DungeonMind** | read-only, revision-pinned |
| Semantic documents, embedding runs, provenance | **DungeonMind** | derived data (ADR-0003) |
| Semantic profile identity model: ref/descriptor/registry contracts, registry port, qualified-term admission | **DungeonMind** | `contracts/semantic_profile.py`, `application/semantic_profiles.py` (PR B.2b, ADR-0004) |
| D&D 5e profile descriptor content (namespaces, revisions, digests) | **DungeonMindDnD** (`src/dungeonmind_dnd/`) | sibling package; kernel never imports it (PR B.2b, ADR-0004) |
| D&D vocabulary catalogs, candidate contracts, candidate validation, prompt/schema rendering | **DungeonMindDnD** (`src/dungeonmind_dnd/`) | side-effect-free executable profile package; pure deterministic logic only (PR B.2c, ADR-0005) |
| Which profiles a deployment loads; descriptor file locations | **Operator configuration** | local registry config; locators are never durable identity (PR B.2b) |
| Schema, migrations, repository ports, PostgreSQL adapters, reconstruction tooling | **DungeonMind** | `migrations/`, `infrastructure/postgres` (PR B) |
| Dev/CI PostgreSQL substrate definition (pinned pgvector compose) | **DungeonMind** | PR B |
| **Production** PostgreSQL lifecycle: network, volumes, backups, secrets wiring | **Deployment orchestrator** (today: DungeonOverMind) | ADR-0002 |
| RulesLawyer product API, Mongo catalog, its own retrieval adapter choice | **DungeonMindServer** | consumer only; never owns graph/retrieval semantics |
| Retrieval benchmark discipline, corpus contracts, bakeoff methodology | **RulesIngestion** | eval-only relationship; Option B (ADR-0001/ROADMAP PR C) |
| Surface layouts, panes/drawers/cards, user interaction | **LandingPage / surfaces** | never leak into core type names |
| Agent tool execution within a bounded policy | **Agent adapter** (Hermes first) | `agents/protocol.py`; optional extras |

## 5. Layering and dependency rules

Enforced by `tests/unit/test_import_boundaries.py`:

```text
contracts  (stdlib + pydantic only)
   ▲
domain     (pure logic; imports contracts)
   ▲
application (ports; imports contracts + domain)
   ▲
infrastructure.memory / .postgres (PR B) │ agents.* │ service.api (later)
```

- Importing `dungeonmind` never requires FastAPI, a database driver, Torch,
  SentenceTransformers, OpenAI, or Hermes; those live behind optional extras.
- The semantic-profile dependency is one-way: no code under
  `src/dungeonmind` imports `dungeonmind_dnd` (enforced by
  `tests/unit/test_import_boundaries.py`). `dungeonmind_dnd` is an
  executable profile package (ADR-0005): it may contain side-effect-free
  contracts and pure deterministic validation, importing only
  `dungeonmind.contracts.base`, `dungeonmind.contracts.evidence`,
  `dungeonmind.contracts.semantic_profile`, and
  `dungeonmind.domain.canonical` — never kernel application,
  infrastructure, service, or agent layers, providers, databases, or API
  frameworks; no registration side effects and no import-time resource
  reads. Profile resolution flows through the `SemanticProfileRegistry`
  port and operator configuration, never through package imports. One
  wheel currently ships both packages.
- No runtime imports from sibling repositories (`graph_memory`,
  `retrieval_lab`, `apps.*`, UI packages). Adaption means owned code in this
  repo with conformance fixtures proving behavior, not import reuse.
- No clients, models, or connections are initialized at module import time.
- IDs are opaque and stable; labels/names are never identity keys.
- Caller/tenant authorization is separate from `world_id` (a world id is not
  an authentication boundary).
- Every durable contract carries a `schema_version` literal and changes only
  by versioned supersession.

## 6. The Mind Turn

`contracts/mind_turn.py` (`mind_turn_v1`) is the primary interaction
envelope. A surface sends context + a message; DungeonMind resolves scope and
revision, retrieves and admits evidence, assembles context, runs an agent
adapter under a capability policy, and returns an answer plus semantic
projections, claims, evidence, source reads, coverage, and diagnostics.
Recorded deviations from the founding handoff's conceptual target are in the
contract module docstring (explicit `caller_scope`; shared projection
vocabulary; shared retrieval-session sub-records).

Contract closures that PostgreSQL adapters must reproduce (PR A.1):

- **Admitted evidence ledger.** `GraphRetrievalSession` and `MindTurnResponse`
  validate closed-envelope evidentiary integrity among evidence, anchors,
  source reads, and claims. Accepted graph facts require SUPPORT evidence;
  anchors must agree with linked evidence provenance; operations and anchors
  must match the pinned revision. Invented evidence IDs cannot ground a fact.
- **Embedding-run lifecycle.** `RUNNING → COMPLETED|FAILED`;
  `COMPLETED|FAILED → SUPERSEDED`. Terminal retries do not rewrite timestamps.
  New semantic documents insert only into `RUNNING` runs; exact replays remain
  idempotent after terminal. Candidate retrieval binds one `COMPLETED`
  non-superseded run (explicit query pin or per-world active-run pointer).
  Failed and superseded runs never contribute candidates. Document deletion
  is allowed only after failure or supersession. In-memory adapters serialize
  run transitions, document mutate/delete, active-pointer changes, and
  retrieval eligibility under one materialization unit-of-work lock.
- **Exact semantic provenance.** Source chunks require `source_revision_id`;
  graph-object documents require `graph_object_id` and `graph_revision_id`.
  Document model metadata must match the materialization run.
- **Agent turn scope unity.** `AgentTurnContext` requires
  `CapabilityPolicy.graph_scope` (when present) to agree with
  `AgentTurnInput` on world, campaign, focus, admissibility, and the resolved
  revision pin — no split-brain assembled vs tool scope.
- **v1 threads.** Caller-private and cross-surface. Immutable binding is
  `(thread_id, tenant_id, caller_id, world_id, campaign_id)`. Surface is
  per-turn. Append is retry-safe by `turn_id`. Shared multi-user threads are
  out of scope.
- **One capability policy.** Permitted tools are derived from
  `CapabilityPolicy` only; callers cannot inject a second tool list.

The retrieval sequence inside a turn (ADR-0003):

```text
exact ID / explicit selection
  → alias and lexical resolution
  → vector candidate retrieval
  → candidate fusion (deterministic)
  → exact graph resolution and traversal
  → scope and visibility filtering
  → evidence admission
  → context assembly
```

A similarity score is never surfaced as factual support.

### 6.1 Stored graph schemas and field admission

Published graph schemas are exact and versioned. Readers dispatch by
`graph_schema` and never reinterpret an older revision under newer rules.

- **`dm_union_graph_v1`** — coarse object projection. Aliases and summary share
  the object's evidence set. If any attached evidence is missing, broken, or
  out of scope, the entire object is hidden. Existing v1 revisions retain this
  behavior byte-for-byte.
- **`dm_union_graph_v2`** — assertion-scoped aliases and one optional summary
  for **read projection only**. Object existence and the primary label remain
  coarse (node-level evidence). Each alias assertion and the summary assertion
  are retained only when every evidence reference attached to that field is
  independently valid and in scope. Omitted fields must not participate in
  identity resolution, agent context, semantic projections, evidence, anchors,
  coverage, or diagnostics.   Semantic candidate seeding must not override an
  exact omitted-alias match (recovering the object via a player-visible
  document would reveal the hidden alias→object association), nor seed
  objects that share an exact admitted alias marked AMBIGUOUS. Relationships
  remain coarse in v2.
- **`dm_union_graph_v3`** — v2 node, relationship, and evidence shapes plus
  one required `semantic_profile` ref (`dm_semantic_profile_ref_v1`) at the
  payload root (PR B.2b, ADR-0004). The ref pins durable identity by
  `profile_id` + `profile_revision` + `descriptor_sha256` — never a path,
  URI, module name, or `latest` pointer. The reader resolves the descriptor
  through the `SemanticProfileRegistry` port, verifies identity and digest,
  and only then admits terms: every node `kind` and relationship `predicate`
  must be a qualified `namespace:local` token whose namespace the pinned
  descriptor's `term_namespaces` admits. Malformed terms, unknown profiles,
  and tampered descriptors fail closed as persistence-integrity errors.
  Terms are opaque — the kernel admits or rejects and never interprets.
  Scoped projection follows v2 field admission exactly.

Scope is derived from admitted evidence provenance. Assertions carry no direct
visibility, campaign, confidence, or authority fields. There is no public
generic assertion / world-object contract in this slice; schema-local records
live with the graph reader. Additive semantic projection
`entity_field_provenance` exposes only admitted alias/summary mappings;
`entity_brief` remains surface-compatible with admitted field values.

Semantic-profile rules that bind every schema (ADR-0004):

- **Config locator versus durable identity.** A descriptor's filesystem path
  exists only in local registry config (`dm_semantic_profile_registry_config_v1`,
  resolved relative to the config file). Graph payloads, public responses,
  and error details never carry paths. Relocating an identical descriptor
  file and updating the config preserves identity; changing descriptor bytes
  changes the digest and requires a new immutable profile revision. Old
  descriptor revisions must remain loadable for as long as the v3 graphs
  pinned to them must remain readable.
- **V1/V2 stay unqualified.** V1 and V2 payloads reject a `semantic_profile`
  field and keep their open `kind`/`predicate` strings with unchanged
  behavior. Their fixture vocabulary is fixture-local — it is **not** a
  canonical taxonomy and must not be promoted into kernel enums.
- **Projection kinds remain kernel-owned.** The current response projection
  kinds (`entity_brief`, `entity_field_provenance`) stay kernel vocabulary;
  v3 adds no projection kinds and no profile term is ever interpreted into
  one.
- **Audience policy stays kernel policy.** GM/player/canon/session
  admissibility remains DungeonMind kernel policy for now; it is not claimed
  as universal TTRPG ontology and does not move into profile data.
- **Future interpretation insertion point.** Anything beyond admit/reject —
  taxonomy reasoning, mechanics, cross-profile mapping — would land as a
  profile-side capability behind the `SemanticProfileRegistry` port, only
  after a concrete second-system pressure proves the abstraction. No such
  interpreter exists today.

### 6.2 Profile-side candidate layer (PR B.2c, ADR-0005)

`dungeonmind_dnd` now owns one narrow executable capability: the
`dnd5e-profile-v2` descriptor, the Threat vocabulary catalog
(`dungeonmind.dnd5e.threat` / `threat-v1`), strict provenance-bearing
candidate contracts (`dmdnd_*_v1`), and pure deterministic validation plus
JSON Schema/prompt rendering.

Rules that bind this layer:

- **This is not the interpretation layer.** The kernel still validates
  namespaces only. The D&D package validates exact D&D terms for candidate
  production only. A graph may contain profile-qualified terms not produced
  by this candidate package, and candidate validation never makes a fact
  canonical.
- **Threat is a relationship.** `dnd5e:threatens` is contextual; no
  `dnd5e:threat` object kind exists and the candidate contract rejects one.
- **Candidate identity is temporary.** Candidates carry packet-local IDs, a
  closed evidence ledger, and no stable IDs, merge outcomes, confidence,
  property bags, or write-path fields. Existing graph objects are
  referenced explicitly (`existing_object_id` + `expected_kind`) but stay
  unverified until a graph-aware successor (B.2d).
- **Prompts are never authority.** The rendered prompt fragment is
  deterministic catalog output; validation authority is the catalog alone.
- **The bundled catalog is the only validation authority.** Injected
  catalogs must exactly match the bundled vocabulary identity (ID, revision,
  pinned profile ref, canonical digest) or are rejected; a caller cannot
  widen the term inventory with its own internally consistent catalog.
- **Ingestion is sanitizing.** Raw payloads enter through
  `parse_threat_candidate_packet`, which converts Pydantic failures into
  sanitized package-owned errors that never echo rejected input (labels,
  summaries, evidence locators, source prose).
- **No graph authority.** The package reads no graphs, calls no LLM,
  persists nothing, and publishes nothing.

## 7. Persistence strategy (summary of ADR-0001/0002/0003)

- PostgreSQL + JSONB + pgvector. Relational identity/lifecycle columns;
  canonical graph snapshots as JSONB payloads in v1. No premature
  normalization of nodes/edges/assertions.
- Head publication: transaction + row-level lock (CAS), never timestamp.
- Source bodies: identity/hashes/locators durable in PostgreSQL; bodies may
  live in object storage behind the source port.
- pgvector: exact search while the corpus is small; HNSW/IVFFlat only after
  measured justification with a recall comparison.
- Embeddings are always rebuildable from durable records; re-embedding
  creates a new materialization run.

## 8. What does not exist yet (and where it lands)

See `Docs/Roadmaps/ROADMAP.md`. In short: PostgreSQL adapters + migrations
(PR B), thin read-only Mind Turn host + curated browser consumer (PR B.1a/B.1b),
assertion-scoped alias/summary read projection (PR B.2a), the semantic
profile boundary with `dm_union_graph_v3` plus the `dungeonmind_dnd`
sibling package (PR B.2b), and the package's first executable capability —
the Threat vocabulary catalog, candidate contracts, and deterministic
candidate validation (PR B.2c) — have landed. Next: graph-aware candidate
resolution and reviewable contribution planning (B.2d), exact external
mechanics/statblock binding for a Threat consumer (B.3), pgvector
benchmark backend via RulesIngestion Option B (PR C), embedding bakeoff
(PR D), DungeonMindServer retrieval seam (PR E), and production IaC
integration (PR F). Conversation/chat history is never authoritative anywhere
in this target state. Still false after B.2c: generic assertion frameworks,
assertion-scoped relationships, assertion authoring, source opening, Hermes,
and external product-surface adoption — plus, on the profile boundary: any
LLM-backed extraction runtime, any graph-aware candidate resolution or
identity work, any candidate-to-contribution planning or publication, any
statblock/mechanics binding, any profile interpretation layer (admit/reject
in the kernel plus one narrow D&D candidate validator is all that exists),
cross-profile mapping, multi-game/multi-system product support,
audience-policy generalization into profile data, and a separate repository
or distribution for `dungeonmind_dnd`. The B.2b canary proves kernel/profile
decoupling; it does not prove multi-system support.
