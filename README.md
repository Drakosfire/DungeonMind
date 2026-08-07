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
- a LandingPage backend;
- the owner of D&D (or any game system's) meaning — game vocabulary lives in
  versioned semantic profiles outside the kernel (ADR-0004, ADR-0005).

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

### Kernel versus profile ownership

DungeonMind is a governed semantic **kernel**: it owns identity, evidence,
revisions, retrieval, and admission — including the *identity model* for
semantic profiles (pinned refs, descriptor shape, registry port,
qualified-term admission). It does not own any game system's meaning. D&D
5e profile data and pure candidate logic live in `src/dungeonmind_dnd/`, a
side-effect-free sibling package: one distribution currently contains both
packages, the dependency is strictly one-way (no code under
`src/dungeonmind` imports `dungeonmind_dnd`), and importing the profile
package registers nothing and reads nothing. Graph payloads pin profiles by
identity and digest, never by path; local registry config decides which
descriptors a deployment loads. Multi-system support is **not** implemented
— the B.2b proof fixture uses a synthetic non-D&D profile precisely so the
canary proves kernel/profile decoupling, not product support for any game
system. Decision records:
[`Docs/Decisions/ADR-0004-semantic-profile-boundary.md`](Docs/Decisions/ADR-0004-semantic-profile-boundary.md),
[`Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md`](Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md),
[`Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md`](Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md).
[`Docs/Decisions/ADR-0007-finalized-contribution-review-adoption.md`](Docs/Decisions/ADR-0007-finalized-contribution-review-adoption.md).
[`Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md`](Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md).
[`Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md`](Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md).
[`Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md`](Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md).
[`Docs/Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md`](Docs/Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md).

The D&D package's first executable slice (B.2c) is intentionally tiny: one
immutable `dnd5e-profile-v2` descriptor, one Threat vocabulary catalog
(four kinds, four predicates with closed direction), strict
provenance-bearing extraction-candidate contracts, and deterministic
validation plus JSON Schema/prompt rendering. B.2d adds non-mutating
graph-aware planning: exact label/alias create-or-connect against one
passed stored revision, producing a candidate-only contribution preview
pinned to the expected parent. B.2e adds a generic kernel review seam: the
ready plan can be translated into a complete review intent and, under exact
GM `confirm_commit` authority plus a content-bound receipt, persisted as one
superseded candidate, one active reviewed successor, and one finalized review
record. The graph head and identity-decision ledger remain unchanged. The
profile package remains repository-blind — no persistence, graph writes, LLM
calls, or fuzzy matching. Historical Threat *candidates* still treat Threat
as contextual `dnd5e:threatens` (ADR-0005 / `threat-v1`). ADR-0013 adds
immutable `dnd5e-profile-v3` + `world-object-v1` so cutover work can represent
persistent Threat/NPC/PlayerCharacter kinds and bind exact mechanics without
hostility, while B.3a Threat mechanics remain readable for historical pins.

## Status

**Founding through B.2f-c landed; the B.2f-d finalized-review publication
transport is implemented in the current branch for review. It exposes one
separate, retry-safe HTTP write boundary; product adoption remains false.**

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
  LandingPage);
- `dm_union_graph_v1` coarse-object read projection (unchanged) plus
  `dm_union_graph_v2` assertion-scoped aliases and summary for read projection
  only (no generic world-object / assertion authoring model);
- `dm_union_graph_v3`: v2-shaped graphs whose payloads pin one exact semantic
  profile (`profile_id` + revision + descriptor digest) and admit only
  qualified `namespace:local` kinds/predicates that profile owns, resolved
  through a config-driven registry
  (`DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH`) that fails closed when
  unconfigured — with the `dungeonmind_dnd` sibling package shipping the D&D
  5e descriptors as package data, and a synthetic non-D&D canary profile
  (`test.narrative`) proving the boundary end to end;
- `dungeonmind_dnd` executable profile slice: the immutable
  `dnd5e-profile-v2` descriptor, the `threat-v1` vocabulary catalog (exact
  kinds/predicates + direction), strict provenance-bearing Threat candidate
  contracts, deterministic catalog validation, deterministic JSON Schema and
  prompt-fragment rendering, a synthetic conformance fixture connecting new
  candidates to an existing object reference, and a repository-blind
  exact-match create-or-connect planner that emits a candidate-only
  `GraphContribution` preview pinned to one expected parent revision.
- generic finalized contribution review contracts and a D&D ready-plan adapter;
- exact GM-scoped `confirm_commit` receipt binding, stale-parent preflight,
  atomic/idempotent in-memory review persistence, and a PostgreSQL review table
  that reloads the superseded candidate, active reviewed successor, and review
  record together;
- pure generic materialization of one finalized review against one exact pinned
  `dm_union_graph_v3` parent, including deterministic accepted nodes, evidence,
  relationships, output reparse, and an ephemeral copy-on-read,
  digest-bound result;
- one trusted application seam that first replays a durable publication by
  `(world_id, review_id)`, otherwise loads the exact review and parent,
  materializes through B.2f-a, and commits one immutable child, head CAS, and
  terminal `dm_finalized_review_publication_v1` record atomically;
- in-memory and PostgreSQL publication repositories with exact replay,
  bounded adoption of an exact predecessor revision, same-review idempotent
  concurrency, different-review expected-parent CAS, and one response-loss
  recovery probe;
- a separate B.2f-d publication host with `/healthz`, `/readyz`, and
  `POST /v1/finalized-review-publications`; the request contains only
  `world_id` and `review_id`, the server owns publication time, and the
  response is the exact durable `dm_finalized_review_publication_v1` record;
- one-world shared-secret transport access (not production user auth), sanitized
  error envelopes, no CORS/browser write surface, infrastructure-only readiness,
  and a standard-library-only external client with exact replay verification;

What deliberately does **not** exist yet: review creation/edit/finalization
transport, pending/failed publication lifecycle,
attempt logs, workers, queues, leases, retry schedulers, arbitrary history
inference, current-head success inference, GET publication polling, mutable
review drafts/editing/replacement, review API/UI/tooling,
global identity-decision append, or target overrides; generic field/property
assertion models, assertion-scoped relationships, assertion authoring or graph writes,
field-level semantic-document materialization, LandingPage or other
product-surface adoption of `mind_turn_v1`, source-body opening, Hermes,
production auth, multi-worker exactly-once adapter execution, the retrieval
benchmark backend (PR C), the embedding bakeoff (PR D), or production
deployment hardening (PR F) — and, on the profile boundary: any LLM-backed
extraction runtime, durable identity decisions, contribution append or graph
publication, fuzzy/semantic identity matching, statblock/mechanics binding,
any generic profile interpretation layer (the kernel admits or rejects
qualified terms; the profile package adds one narrow candidate validator and
one exact-match planner), cross-profile mapping, multi-game or multi-system
product support, and audience-policy generalization. See
[`Docs/Roadmaps/ROADMAP.md`](Docs/Roadmaps/ROADMAP.md).

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

### Finalized-review publication service (B.2f-d)

The publication service is deployed separately from Mind Turn and is intended
for a server-side/operator caller:

```bash
export DUNGEONMIND_PUBLICATION_WORLD_ID=world:synthetic-gatewatch
export DUNGEONMIND_PUBLICATION_BEARER_TOKEN='local-secret-from-operator'
uv run uvicorn dungeonmind.service.bootstrap:create_publication_service_app \
  --factory --host 127.0.0.1 --port 8001

uv run python examples/finalized_review_publication_client/client.py \
  --base-url http://127.0.0.1:8001 \
  --world-id world:synthetic-gatewatch \
  --review-id review:cff0162637b428e634e8cccaa9958dc2 \
  --verify-replay
```

The request has no caller timestamp, operation identity, expected parent,
confirmation, graph payload, or token. An outcome-unknown 503 explicitly says
that retrying the same request is safe. Current head is never success evidence.
See the [B.2f-d runbook](Docs/Runbooks/RUNBOOK-b2f-d-finalized-review-publication-service.md).

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
src/dungeonmind_dnd/
  contracts/       D&D-owned strict contracts (vocabulary, candidates, plans)
  domain/          package-owned typed errors (transport-free)
  application/     pure loaders/validators/planners (side-effect-free)
  profiles/        immutable semantic profile descriptors (v1 + v2 package data)
  vocabularies/    immutable Threat vocabulary catalog (package data)
migrations/        DungeonMind-owned schema migrations
examples/          non-product acceptance consumers (static browser proof,
                   semantic profile registry config example)
scripts/           seed + static example server
tests/             unit / integration / conformance / fixtures
Docs/              architecture, ADRs, roadmaps, handoffs, runbooks
```

Import rules are enforced by tests: `contracts` ← `domain` ← `application` ←
`infrastructure` / `agents`; nothing in `src/` may import FastAPI, Torch,
SentenceTransformers, a database driver, Hermes, or code from any sibling
repository or UI package. Heavyweight integrations live behind optional extras.
The browser example under `examples/` is framework-free HTML/CSS/JS and is not
imported by the Python package. One wheel currently ships two packages with a
strictly one-way dependency: no code under `src/dungeonmind` imports
`dungeonmind_dnd`, and `dungeonmind_dnd` imports only a path-sensitive
kernel allowlist (B.2c modules: contract/canonical; B.2d planning modules
additionally: graph snapshot + contribution/graph/identity/vocabulary
  contracts — and the B.2e review adapter additionally the generic
  contribution/review contracts — never repositories/infrastructure/service/agents, no providers,
no registration side effects, no import-time resource reads). Profile
resolution flows through the `SemanticProfileRegistry` port and operator
config, never through imports.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: small reviewable PRs, the
PR description is the merge contract, durable contracts are versioned, corpus
prose / model weights / secrets never enter git, the kernel never imports
profile packages, and every durable write is explicit and auditable.
