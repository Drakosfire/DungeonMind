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
  Failed and superseded runs never contribute candidates.
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
(PR B), thin read-only Mind Turn demo (PR B.1), then pgvector benchmark
backend via RulesIngestion Option B (PR C), embedding bakeoff (PR D),
DungeonMindServer retrieval seam (PR E), and production IaC integration
(PR F). Conversation/chat history is never authoritative anywhere in this
target state.
