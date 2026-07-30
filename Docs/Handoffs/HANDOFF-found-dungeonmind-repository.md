# HANDOFF — Found DungeonMind and Establish the PostgreSQL/pgvector Retrieval Foundation

**Created:** 2026-07-29
**Status:** LANDED (PR A) — preserved verbatim as the founding charter. Its §14
non-goals and §15 stop conditions remain binding for all successor slices.
**Note:** this copy lives at the canonical path named by the charter itself.

---

## §0 Operator intent

The operator wants to establish **DungeonMind as an independent repository and product boundary**.

This is not a DungeonMindBuddy cleanup mission. Do not begin by reorganizing, deleting, or migrating the existing project.

DungeonMindBuddy is the workshop in which much of the graph, projection, retrieval, evidence, and Hermes interaction architecture has already been designed and proven. DungeonMind is the reusable system being extracted from those lessons.

The intended long-term product shape is:

```text
User
  → replaceable product surface
  → DungeonMind
  → governed graph, sources, evidence, retrieval, and agent context
```

The user interface may remain a relatively static route hosted in LandingPage, become its own vertical, or later be replaced entirely. The UI is not the primary product boundary.

The valuable system is the **Mind**:

* durable identity and knowledge;
* graph revisions and projections;
* semantic and exact retrieval;
* evidence admission;
* query planning;
* context assembly;
* agent orchestration;
* capability enforcement;
* deliberate write boundaries.

The immediate goal is to lay credible foundations for a bolt-on, read-oriented demonstration without forcing a broad migration of DungeonMindBuddy.

---

## §1 Mission

Found the independent `DungeonMind` repository, establish its architectural and engineering rules, determine the correct ownership and deployment of its PostgreSQL/pgvector substrate, prove a benchmarkable semantic-retrieval path using existing retrieval assets, and leave DungeonMindServer and the deployment environment ready to consume DungeonMind without owning its domain.

### Governing invariant

```text
DungeonMind owns knowledge, retrieval, evidence, context assembly, and capability policy independently of any UI, agent provider, database adapter, or sibling application repository.
```

### Supporting invariants

1. The World Graph is authoritative materialized knowledge; vectors are disposable retrieval indexes.
2. Source artifacts and admitted evidence remain the basis for factual support.
3. Every read operates against one explicit world, campaign scope, admissibility policy, and coherent graph revision.
4. Surfaces publish context and consume semantic results; they do not assemble graph queries or prompts.
5. Hermes is the first agent adapter, not the definition of DungeonMind.
6. DungeonMindServer may host consumers and existing product APIs, but it must not become the owner of DungeonMind’s graph or retrieval semantics.
7. No agent or surface receives silent durable write authority.
8. The founding work must establish replaceable ports, not merely move existing filesystem assumptions into a new repository.

### Mission falsification test

This mission has exceeded its boundary if it attempts to also deliver:

* complete DungeonMindBuddy migration;
* removal of preview or legacy graph paths;
* production migration of all RulesLawyer data;
* a finished multi-surface UI;
* autonomous graph writes;
* full graph extraction;
* Play/combat migration;
* a normalized relational representation of every historical graph object;
* or a public production launch.

---

## §2 Authority order

### 2.1 Current DungeonMindBuddy authority

1. `Docs/Design/ARCHITECTURE-campaign-supergraph.md`
2. `Docs/Roadmaps/ROADMAP-campaign-supergraph.md`
3. `Docs/Plans/PR-TRACKER-campaign-supergraph.md`
4. `Docs/Design/STATUS-world-graph-continuity-spine.md`
5. `Docs/Design/CONTRACT-graph-kernel-boundary.md`
6. `Docs/Design/ARCHITECTURE-hermes-campaign-authoring-foundation.md`
7. Current graph-memory models, Kernel APIs, projection contracts, retrieval-session contracts, tests, and accepted dogfood reports.

These decisions are already closed unless implementation evidence exposes a contradiction:

* one World Supergraph per world;
* campaign-scoped assertions, evidence, chronology, and visibility;
* immutable published revisions;
* atomic graph-head advancement;
* explicit identity outcomes;
* governed contributions;
* source-grounded evidence;
* revision-pinned projections;
* separate read and write paths;
* no privileged agent writer;
* surfaces never own graph semantics.

### 2.2 DungeonMindServer sources

`pyproject.toml`, `dependencies.py`, `env.example`,
`ruleslawyer/ruleslawyer_helper.py`, `ruleslawyer/hybrid_retriever.py`,
`routers/ruleslawyer_router.py`, `statblocks_v1/application/repositories.py`,
`statblocks_v1/infrastructure/memory_repositories.py`,
`statblocks_v1/infrastructure/firestore_repositories.py`,
`statblocks_v1/infrastructure/runtime.py`, `Dockerfile`, deployment scripts,
health/readiness implementation.

### 2.3 RulesIngestion sources

`Docs/Workflows/WORKFLOW-Retrieval-Best-Practices.md`,
`Docs/Reports/REPORT-Embedding-Bakeoff-Comprehensive-2026-03-04.md`,
`Docs/Reports/REFERENCE-Retrieval-Benchmark-Results-Timeline.md`,
`Docs/Design/v1/retrieval_lab_v1.md`, `retrieval_lab/`,
`scripts/run_embedding_bakeoff_multivariate.py`, `evals/retrieval/`.

### 2.4 Project Source classification

| Source | Use |
| --- | --- |
| `CORPUS-ANCHOR.md` | Source-location anchor |
| `GRAPH-MEMORY-PROJECT-LAYOUT.md` | Active reference, subject to current GitHub state |
| `ARCHITECTURE-plan-surface-toolbox.md` | Active surface-boundary reference |
| `LLM-graph-construction.md` | Research only |
| `dungeonbuddy_spec_architecture_v0_2.md` | Historical conceptual ancestor |
| `GRAPH-MEMORY-SUPERGRAPH-ARCHITECTURE-ROADMAP.md` | Superseded historical roadmap |
| `PROPOSAL-context-audit-source-reanchor.md` | Proposal, not authority |
| `_bmad-output/project-context.md` | Preserve useful engineering rules, but treat old “no API/database/vector” scope as superseded |

GitHub current authority overrides local or Project Source copies where they disagree.

---

## §3–§5 (condensed in this preservation copy)

§3 Known current state, §4 Required product boundary, and §5 Founding
reconnaissance requirements were executed at founding; their results are
recorded in:

* `Docs/Architecture/ARCHITECTURE.md` (boundary, invariants, ownership)
* `Docs/Reports/RECON-2026-07-29-founding-inventory.md` (§5.1 module
  inventory + classification, §2.2/§10.1 server audit, §2.3 benchmark
  contracts, §5.2–5.3 infrastructure inventory and IaC decision)
* `Docs/Decisions/ADR-0001-database-selection.md` (§5.4 comparison)
* `Docs/Decisions/ADR-0002-persistence-lifecycle-ownership.md`
* `Docs/Decisions/ADR-0003-pgvector-derived-index.md`

The Mind Turn contract target from §4.2 is implemented as
`src/dungeonmind/contracts/mind_turn.py` (`mind_turn_v1`); deviations are
recorded in that module and in the recon report §F.

---

## §6–§13 (executed at founding)

§6 repository foundation, §7 PostgreSQL foundation requirements, §8 pgvector
role, §9 embedding/retrieval experiment discipline, §10 DungeonMindServer
boundaries, §11 PR decomposition, §12 deliverables, and §13 acceptance gates
were implemented or scheduled exactly as chartered. The PR ladder (§11) was
confirmed without amendment and lives in `Docs/Roadmaps/ROADMAP.md`.

---

## §14 Explicit non-goals (binding)

Do not:

* clean up DungeonMindBuddy generally;
* delete existing graph paths;
* move UI code into DungeonMind;
* move RulesLawyer into DungeonMind;
* make MongoDB disappear merely for consistency;
* migrate production data without a separate approved plan;
* expose pgvector directly to browsers;
* treat vector search as evidence;
* make the embedding model part of graph identity;
* make Hermes a required core dependency;
* build autonomous graph writes;
* build a second agent-specific write protocol;
* auto-publish extracted facts;
* normalize every graph revision into relational tables;
* add HNSW before exact-search evidence;
* change production defaults based on one benchmark;
* reuse generic LibreChat database credentials;
* commit model weights;
* place corpus prose in Git unless existing corpus policy permits it;
* claim Project Sources were updated.

---

## §15 Stop conditions (binding)

Stop implementation and report before proceeding when:

1. `Drakosfire/DungeonMind` already exists with conflicting content.
2. The current repository authority differs materially from this handoff.
3. Existing PostgreSQL ownership cannot be established.
4. The only available PostgreSQL instance is unsafe, publicly exposed, unbacked-up, or operationally owned by an unrelated service.
5. pgvector cannot be enabled on the intended PostgreSQL instance.
6. Database changes require credentials or production access unavailable to the agent.
7. A proposed dependency forces DungeonMind core to import DungeonMindServer, DungeonMindBuddy, LandingPage, or RulesIngestion.
8. A model’s license is incompatible with the intended deployment.
9. Existing benchmark projections do not match the active corpus fingerprint.
10. A benchmark condition changes both corpus shaping and retrieval behavior.
11. A proposed model switch materially regresses candidate coverage without an explicit accepted tradeoff.
12. PostgreSQL persistence cannot reproduce current graph revision/head guarantees.
13. Multi-repository work cannot be split into independently reviewable PRs.
14. The work begins requiring DungeonMindBuddy cleanup or migration to make the founding contract appear complete.
15. The proposed schema encodes one graph per campaign or makes conversation history authoritative.
16. Any path grants an agent or surface silent durable write authority.

A stop report must include: the discovered fact; affected invariant; options;
recommended resolution; work safely completed; exact work not attempted.

---

## §16–§17

The §16 handback for PR A is delivered in the PR A handback report
(`Docs/Reports/HANDBACK-PR-A.md`) and the PR body. §17's success condition
remains the program-level definition of done.
