# DungeonMind

DungeonMind is a governed context and knowledge runtime for persistent fictional
worlds. It owns durable world knowledge, revision-aware graph projections,
semantic retrieval, evidence admission, context assembly, and
capability-bounded agent interaction. Product surfaces consume it but do not
own its behavior.

```text
User
  → replaceable product surface (LandingPage / Plan / Play / Build / future clients)
  → DungeonMind
  → governed graph, sources, evidence, retrieval, and agent context
```

DungeonMind is **not**:

- a graph database wrapper;
- a RAG pipeline (vectors are disposable retrieval indexes, not knowledge);
- a graph viewer;
- a Hermes plugin (Hermes is the first agent adapter, not the definition);
- a DungeonMindBuddy extraction library (DungeonMindBuddy is the workshop where
  this architecture was proven; this repository is the product boundary);
- a LandingPage backend.

## Ownership at a glance

| DungeonMind owns | DungeonMind does not own |
| --- | --- |
| Durable world knowledge (World Graph, one supergraph per world) | Product surfaces and their layouts |
| Immutable graph revisions + atomic head publication | PostgreSQL service lifecycle, volumes, backups (deployment layer) |
| Semantic retrieval indexes (pgvector, derived + rebuildable) | RulesLawyer / DungeonMindServer product APIs (they are consumers) |
| Source artifacts, evidence admission, provenance | Embedding benchmark authority (RulesIngestion discipline) |
| Context assembly + retrieval sessions | Conversation/chat history as truth |
| Capability policy (what any agent may do) | Any agent's silent durable write authority (none exists) |

Full ownership and boundary rules: [`Docs/Architecture/ARCHITECTURE.md`](Docs/Architecture/ARCHITECTURE.md).
Source-of-truth precedence: [`Docs/Architecture/AUTHORITY.md`](Docs/Architecture/AUTHORITY.md).

## Status

**Founding (PR A).** What exists today:

- versioned public contracts (graph revisions, contributions, evidence,
  identity decisions, projections, retrieval sessions, semantic documents,
  capability policy, the Mind Turn);
- repository protocols (ports) with in-memory adapters, including atomic head
  publication with stale-parent rejection;
- deterministic canonical hashing, revision identity, and rank fusion;
- import-boundary enforcement tests (core imports with no FastAPI, PostgreSQL
  driver, Torch, or Hermes);
- the founding decision record (ADRs) and the PR ladder.

What deliberately does **not** exist yet: PostgreSQL adapters and migrations
(PR B), the retrieval benchmark backend (PR C), the embedding bakeoff (PR D),
the FastAPI service host, any agent adapter, and any durable write path beyond
graph revision publication. See [`Docs/Roadmaps/ROADMAP.md`](Docs/Roadmaps/ROADMAP.md).

## Quickstart

```bash
uv sync                 # installs package + dev tools (no heavy deps)
uv run pytest           # unit tests (in-memory; no services required)
uv run ruff check .     # lint
```

PostgreSQL integration tests (PR B+) are opt-in locally and active in CI:

```bash
uv sync --extra postgres
DUNGEONMIND_DATABASE_URL=... uv run pytest -m integration
```

## Repository map

```text
src/dungeonmind/
  contracts/       versioned Pydantic v2 wire contracts (the public API)
  domain/          pure logic: canonical hashing, revision identity, fusion, errors
  application/     repository protocols (ports) and orchestration seams
  agents/          agent adapter protocol (Hermes is an adapter, not a dependency)
  infrastructure/
    memory/        in-memory adapters for unit tests and local development
    postgres/      (PR B) PostgreSQL/pgvector adapters
  service/api/     (successor) FastAPI host
migrations/        (PR B) DungeonMind-owned schema migrations
tests/             unit / integration / conformance / fixtures
Docs/              architecture, decisions (ADRs), roadmaps, handoffs, reports
```

Import rules are enforced by tests: `contracts` ← `domain` ← `application` ←
`infrastructure` / `agents`; nothing in `src/` may import FastAPI, Torch,
SentenceTransformers, a database driver, Hermes, or code from any sibling
repository or UI package. Heavyweight integrations live behind optional extras.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: small reviewable PRs, the
PR description is the merge contract, durable contracts are versioned, corpus
prose / model weights / secrets never enter git, and every durable write is
explicit and auditable.
