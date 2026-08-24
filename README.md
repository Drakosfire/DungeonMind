# DungeonMind

DungeonMind is an independent governed world-knowledge library for persistent fictional worlds.

It owns durable world knowledge, immutable graph revisions, source/evidence provenance, scope and admissibility, graph projection and retrieval, semantic-profile identity, and governed publication. Products consume those capabilities through transport-neutral application services or optional service adapters.

DungeonMind does **not** own the product or the agent harness.

```text
DungeonBuddy / another client
  product UI + work context + agent harness + model/tool loop
                     │
                     ▼
                DungeonMind
  durable knowledge + evidence + revisions + scoped reads
            + governed publication
                     │
                     ▼
                 PostgreSQL
```

## Current state

DungeonMind has crossed the boundary from architecture experiment to independently exercised library.

A real external consumer, DungeonMindBuddy, has migrated the Eldyrwild World Graph authority into DungeonMind/PostgreSQL and proven a current-client read contract against DungeonMind-native semantics. The adopted world has immutable published revisions, a living PostgreSQL head, governed post-adoption publication, exact historical pinning, GM/PLAYER admissibility, campaign and cross-campaign projection, native lookup/search/neighborhood/evidence retrieval, and source-anchor derivation/revalidation.

The current active library lane is **R.3a — native World Graph read optimization**. The semantics are accepted; the remaining blocker to switching DungeonMindBuddy from its temporary hydrated read bridge to direct native reads is performance. The R.3 real-world witness measured roughly 20.7s for a direct projection versus roughly 1.7s for the hydrated compatibility path. R.3a must improve the native implementation without changing the accepted result contract.

The production direct-read rollout flag is owned by DungeonMindBuddy and remains default-off until that optimization is accepted. That rollout state is a client integration concern, not a second DungeonMind authority.

## Library boundary

DungeonMind owns:

- one World Graph per world;
- immutable, revision-addressed graph snapshots and atomic head publication;
- source artifacts, source revisions, evidence identity, and provenance admission;
- campaign/world scope and GM/PLAYER admissibility;
- semantic-profile identity and fail-closed qualified-term admission;
- exact revision projection;
- deterministic graph retrieval: object lookup, lexical/referent search, bounded neighborhood, evidence, and source-anchor identity/revalidation;
- governed contribution review and publication;
- repository ports plus in-memory and PostgreSQL implementations;
- optional service transports around library-owned capabilities.

DungeonMind does not own:

- product UI, surface state, document editors, or interaction flows;
- agent harnesses, model/provider selection, prompts, tool loops, retries, approvals, conversation state, or context budgeting across product tools;
- product-local source-body opening or presentation joins;
- DungeonMindBuddy compatibility behavior that has been intentionally retired;
- D&D meaning inside the generic kernel; game semantics live in versioned profile packages;
- deployment lifecycle for production PostgreSQL, backups, secrets, or networking.

See [ADR-0022](Docs/Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md) for the post-cutover library boundary.

## What the cutover proved

The first real consumer pressure produced evidence that several core abstractions are real rather than speculative:

- **Revision identity is useful.** Current and historical DungeonMind revisions can be selected explicitly and returned as re-pinnable public identity.
- **The authority boundary is meaningful.** DungeonMind semantics can differ intentionally from historical Buddy-kernel behavior without recreating compatibility machinery.
- **Evidence admission is part of knowledge semantics.** Per-chain provenance validation and fail-closed visibility are now accepted client behavior.
- **Profiles are separate from the kernel.** Eldyrwild uses a D&D profile while the generic read/write machinery remains profile-neutral.
- **The library can be a real external authority.** DungeonMindBuddy is now a consumer rather than the owner of graph truth.

The cutover also exposed the next design questions:

- native read performance needs a coherent reusable read context;
- source/provenance state means an authorized projection cannot be cached safely by graph revision alone;
- some founding-era MindTurn/agent/context machinery may not belong in the long-term independent library and will be evaluated rather than grandfathered in;
- extensibility must be demonstrated by additional consumers and profile pressure, not claimed from abstraction shape alone.

The reflection and evidence ledger live in [the post-R.3 library transition report](Docs/Reports/REPORT-2026-08-23-independent-library-transition.md).

## Architecture

The core read shape is:

```text
WorldGraphProjectionRequestV2
→ resolve exact head/revision
→ parse immutable graph revision
→ establish coherent source/provenance state
→ apply scope + admissibility + evidence admission
→ scoped projection
→ lookup / search / neighborhood / evidence / anchors
```

The core write shape is:

```text
candidate contribution
→ explicit review
→ finalized reviewed contribution
→ materialize against exact parent
→ atomic expected-parent publication
→ immutable child revision + new head
```

Durable knowledge remains separate from derived retrieval indexes. Vectors, if used, are rebuildable candidate-retrieval aids rather than graph authority.

Full boundaries: [Docs/Architecture/ARCHITECTURE.md](Docs/Architecture/ARCHITECTURE.md)  
Authority precedence: [Docs/Architecture/AUTHORITY.md](Docs/Architecture/AUTHORITY.md)  
Current roadmap: [Docs/Roadmaps/ROADMAP.md](Docs/Roadmaps/ROADMAP.md)

## Packages

```text
src/dungeonmind/
  contracts/       versioned transport-neutral contracts
  domain/          pure identity/revision/canonical logic and errors
  application/     read/write services and repository ports
  infrastructure/  in-memory and PostgreSQL adapters
  service/         optional transport hosts

src/dungeonmind_dnd/
  profiles/        immutable D&D semantic-profile descriptors
  vocabularies/    profile-owned terms
  contracts/       profile-owned candidate/plan contracts
  application/     pure validation/planning adapters
```

The dependency remains one-way: the generic `dungeonmind` package does not import `dungeonmind_dnd`. Deployments resolve profile descriptors through the registry port.

## Development

```bash
uv sync --locked
uv run pytest -m "not integration"
uv run ruff check .
uv run pyright
```

PostgreSQL integration:

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
uv run pytest -m integration
```

The R.2a benchmark baseline and the R.3a successor are documented under `Docs/Benchmarks/`.

## Engineering posture

DungeonMind is optimized for correctness and inspectability first, then measured simplification and performance.

A mechanism earns its place by doing at least one of the following:

1. serving a named current consumer;
2. preventing a demonstrated correctness or authority failure;
3. materially simplifying a concrete extension;
4. preserving a clean library boundary that would otherwise leak product semantics.

Speculative flexibility is not a sufficient reason to retain complexity. The post-R.3 roadmap explicitly includes architecture-fitness and deletion work after the native read path is healthy.
