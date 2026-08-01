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

**Founding through B.1a landed; B.1b DungeonMind-owned browser consumer in flight.**

What exists today:

- versioned public contracts with cross-field invariant validators;
- repository protocols with in-memory and PostgreSQL/pgvector adapters;
- Alembic migrations and a pinned local Compose Postgres image;
- thin read-only Mind Turn HTTP host (`/healthz`, `/readyz`, `/v1/mind-turn`)
  with trusted demo-access binding, hybrid retrieval, evidence admission,
  fixture agent adapter, and retrieval-session / thread replay;
- curated synthetic fixture + idempotent seed command;
- a repository-local static browser example under
  `examples/curated_mind_turn_surface/` that consumes the live API on a second
  origin (acceptance consumer — **not** a product surface and **not**
  LandingPage).

What deliberately does **not** exist yet: LandingPage or other product-surface
adoption of `mind_turn_v1`, source-body opening, Hermes, production auth,
multi-worker exactly-once adapter execution, the retrieval benchmark backend
(PR C), the embedding bakeoff (PR D), or production deployment hardening
(PR F). See [`Docs/Roadmaps/ROADMAP.md`](Docs/Roadmaps/ROADMAP.md).

## Quickstart

```bash
uv sync --locked        # package + dev tools
uv run pytest -m "not integration"
uv run ruff check .
uv run pyright
```

### Curated Mind Turn demo (PostgreSQL + API + browser example)

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
uv run python scripts/seed_curated_mind_turn.py

# terminal A — single worker
export DUNGEONMIND_CORS_ORIGIN=http://127.0.0.1:8081
uv run uvicorn dungeonmind.service.bootstrap:create_demo_app --factory \
  --host 127.0.0.1 --port 8000 --workers 1

# terminal B — static acceptance consumer
uv run python scripts/serve_curated_mind_turn_surface.py
# open http://127.0.0.1:8081/
```

Exact browser proof steps:
[`Docs/Runbooks/RUNBOOK-b1b-curated-browser-surface.md`](Docs/Runbooks/RUNBOOK-b1b-curated-browser-surface.md).

Integration tests (opt-in locally, required in CI):

```bash
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -m integration
```

## Repository map

```text
src/dungeonmind/
  contracts/       versioned Pydantic v2 wire contracts (the public API)
  domain/          pure logic: canonical hashing, revision identity, fusion, errors
  application/     repository protocols and Mind Turn orchestration
  agents/          agent adapter protocol + deterministic fixture adapter
  infrastructure/
    memory/        in-memory adapters for unit tests
    postgres/      PostgreSQL/pgvector adapters
    fixtures/      curated seed helpers
  service/         optional FastAPI host (api extra)
migrations/        DungeonMind-owned schema migrations
examples/          non-product acceptance consumers (static browser proof)
scripts/           seed + static example server
tests/             unit / integration / conformance / fixtures
Docs/              architecture, ADRs, roadmaps, handoffs, runbooks
```

Import rules are enforced by tests: `contracts` ← `domain` ← `application` ←
`infrastructure` / `agents`; nothing in `src/` may import FastAPI, Torch,
SentenceTransformers, a database driver, Hermes, or code from any sibling
repository or UI package. Heavyweight integrations live behind optional extras.
The browser example under `examples/` is framework-free HTML/CSS/JS and is not
imported by the Python package.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: small reviewable PRs, the
PR description is the merge contract, durable contracts are versioned, corpus
prose / model weights / secrets never enter git, and every durable write is
explicit and auditable.
