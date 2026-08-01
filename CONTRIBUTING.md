# Contributing to DungeonMind

## Toolchain

- Python `>=3.11`, managed with **uv**. Never run bare `python`/`pip`; use
  `uv run python ...`, `uv run pytest`, `uv add <pkg>`.

```bash
uv sync                 # package + dev tools
uv run pytest           # unit tests (no services required)
uv run pytest -m integration   # opt-in: requires DUNGEONMIND_DATABASE_URL (PR B+)
uv run pytest -m conformance   # behavior pinned to DungeonMindBuddy-derived fixtures
uv run ruff check .
uv run pyright          # static type check over src/
```

## Engineering rules

1. **Layering is enforced by tests** (`tests/unit/test_import_boundaries.py`):
   `contracts` imports only stdlib+pydantic; `domain` adds `contracts`;
   `application` adds `domain`; `infrastructure/*` and `agents/*` may import all
   three but never each other's sibling adapters. Nothing in `src/` imports
   FastAPI, Torch, SentenceTransformers, database drivers, Hermes, `apps.*`
   (DungeonMindBuddy), or any sibling repository / UI package.
2. **Core stays light.** Importing `dungeonmind` must never require optional
   extras (`postgres`, `api`, future `embeddings`/`hermes`) and must never
   initialize clients, models, or connections at module import time.
3. **Every durable contract is versioned** (`schema_version` literal, e.g.
   `dm_graph_revision_v1`). Changing a contract means a new version and a
   migration/compat story, not a silent field edit.
4. **IDs are opaque and stable.** Never use labels, names, or array positions
   as identity. Never expose tenant/authorization semantics through `world_id`.
5. **Repository protocols in `application/`**; adapters in `infrastructure/`.
   Unit tests run against in-memory adapters. Integration tests run against
   real PostgreSQL semantics and are opt-in locally, active in CI.
6. **pgvector is a derived index.** Embeddings are always rebuildable from
   durable source and graph records. Re-embedding creates a new materialization
   run; it never silently overwrites provenance (ADR-0003).
7. **No silent durable writes.** Agents and surfaces receive typed capabilities
   only; durable writes are explicit, auditable operations (today: graph
   revision publication with stale-parent rejection).
8. **Type hints required** (ruff `ANN` rules active for `src/` and `scripts/`).

## Semantic profile boundary (hard rules, ADR-0004)

- **No code under `src/dungeonmind` imports `dungeonmind_dnd`** — enforced by
  `tests/unit/test_import_boundaries.py`. `dungeonmind_dnd` also stays
  data-only: no kernel layer imports, no registration side effects.
- **No unqualified new semantic kinds/predicates in `dm_union_graph_v3`
  fixtures.** Every v3 `kind` and `predicate` is a qualified
  `namespace:local` term admitted by the fixture's pinned profile.
- **No D&D mechanics contract lands under `src/dungeonmind`.** Game meaning
  belongs to profile packages; the kernel owns admission, never
  interpretation.
- **Changing a profile descriptor requires a new immutable profile
  revision** — a new `profile_revision` pin and a new digest. Never edit a
  published descriptor in place; old revisions stay loadable for as long as
  graphs pinned to them must remain readable.
- **Config paths are never stored in graph payloads or public responses**
  (nor in error details). Durable identity is the pinned `profile_id` +
  `profile_revision` + `descriptor_sha256`; registry config paths are
  deployment-local locators only.

## Data hygiene (hard rules)

- Never commit secrets, `.env` files, credentials, or connection strings with
  passwords. Variable names only in docs/audits.
- Never commit model weights or corpus prose (campaign content contains
  real-person PII; rulebook text is licensed). Fixtures must be synthetic or
  hashed/referenced by digest.
- Never paste corpus content into external tools. Benchmark artifacts with raw
  text stay out of git unless the owning corpus policy explicitly permits.

## PR discipline

- Small, independently reviewable PRs following the ladder in
  [`Docs/Roadmaps/ROADMAP.md`](Docs/Roadmaps/ROADMAP.md).
- The PR description is the merge contract: restate the mission, list the
  evidence required to merge, record the evidence actually produced, and name
  what remains false. Use `Docs/Handoffs/HANDOFF-TEMPLATE.md` for dispatched
  slices.
- Cross-repository changes land as separate PRs per repository.
- Do not change production retrieval defaults without artifact-backed benchmark
  evidence and an explicit migration + rollback plan.
