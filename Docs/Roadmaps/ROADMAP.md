# DungeonMind — Roadmap and PR ladder

**Status:** PR A landed; PR A.1 (invariant hardening) in flight. Ladder
amended after founding review: the curated read-only Mind Turn demo moves
immediately after the minimal PostgreSQL substrate, before cross-repo
benchmarking and production IaC. Ownership per ADR-0002.

Each PR is independently reviewable, in its named repository. Cross-repo work
is never one PR.

## Sequence (amended)

```text
A   repository foundation ✅
A.1 foundational invariant hardening   ← current
B   minimal PostgreSQL/pgvector substrate
B.1 thin read-only Mind Turn API + LandingPage demo (curated fixture)
C   RulesIngestion pgvector benchmark backend
D   embedding model bakeoff
E   DungeonMindServer retrieval seam
F   production infrastructure hardening (DungeonOverMind)
```

The demo may use deterministic fixture embeddings or the benchmark baseline.
It proves the replaceable UI-to-Mind seam before several PRs optimize and
operationalize retrieval.

## PR A — DungeonMind repository foundation ✅

**Repository:** DungeonMind

Delivered: package scaffold (`uv`, Pydantic v2); contract families; domain
logic; application repository ports; in-memory adapters; curated fixture;
unit tests; lint+CI; founding docs (architecture, authority, ADRs 0001–0003,
recon report, handoff template).

## PR A.1 — Foundational invariant hardening

**Repository:** DungeonMind

Exit proof:

- Explicit, fail-closed admissibility/visibility on all request contracts
  (absence never means GM).
- Parent/head lineage equality on normal graph publication
  (`parent == expected == current_head`).
- Deep-copy immutability for stored graph payloads.
- Canonical idempotency conflicts for source, semantic, thread, and embedding
  records.
- Cross-field validators for evidence, source types, semantic documents,
  identity decisions, focus, scope, claims, and accepted assertions.
- Thread binding and turn-correlation enforcement.
- Sanitized agent-adapter input (no caller/tenant auth metadata).
- Static type checking (Pyright) in CI.
- This roadmap update placing the curated demo after PR B.

## PR B — PostgreSQL/pgvector development substrate

**Repository:** DungeonMind (+ deployment owner only if dev/CI wiring needs it)

Outcome:

- `migrations/` (Alembic) implementing the minimum schema families
  (charter §7.2) with relational identity/lifecycle columns + JSONB payloads;
- pinned dev/CI pgvector image + compose; health check verifies PostgreSQL
  and the pgvector extension;
- `infrastructure/postgres/` adapters for the repository ports, behind the
  `postgres` extra;
- graph revision/head CAS proven against real PostgreSQL (row-lock,
  stale-parent rejection, failed-write readability, auditable rollback);
- semantic documents inserted and exactly searched (dense + full-text +
  exact + fusion + filters);
- integration tests opt-in locally, required in CI.

## PR B.1 — Thin read-only Mind Turn demo

**Repositories:** DungeonMind (API host) + LandingPage (static route)

Outcome:

```text
static LandingPage route
→ surface context and user question
→ DungeonMind Mind Turn API (mind_turn_v1)
→ exact graph revision
→ hybrid candidate retrieval (fixture embeddings acceptable)
→ graph traversal and admitted evidence
→ agent adapter answer (Hermes or stub)
→ semantic UI projections
```

Curated, read-only fixture first (`tests/fixtures/curated_world_v1.json` is
the seed); no live graph writes or broad ingestion. Does **not** require a
production embedding-model decision, RulesLawyer migration, production
backup wiring, or completed cross-repository retrieval benchmarking.

## PR C — pgvector retrieval benchmark backend

**Repository:** RulesIngestion (benchmark client) — **Option B** per ADR-0001
and recon §C: RulesIngestion materializes an exact corpus + benchmark
projection and invokes DungeonMind's pgvector retriever as an external
backend. DungeonMind never imports RulesIngestion; RulesIngestion never
becomes a DungeonMind runtime dependency.

Outcome: existing corpus/projection contracts drive pgvector; exact dense and
hybrid PostgreSQL conditions run; artifacts reproducible; existing model
baselines preserved; no production behavior changes.

## PR D — embedding model bakeoff

**Repository:** RulesIngestion (benchmark owner)

Outcome: BGE-M3 (production-code baseline), all-mpnet-base-v2 (cross-corpus
benchmark baseline), and ≥1 materially smaller CPU-oriented candidate
(selected from current model-card research — license, dimensions, context,
instruction format, CPU/quantization support — never from memory) compared on
one corpus fingerprint, one knob at a time; quality + operational metrics
recorded; evidence-backed recommendation; **campaign-prose benchmark debt
named** (rulebook results do not prove narrative retrieval quality). May
combine with PR C only if the backend is already proven and the diff stays
reviewable.

## PR E — DungeonMindServer retrieval seam

**Repository:** DungeonMindServer

Outcome: current local behavior preserved; hard-coded model identity replaced
by validated configuration; embedding-provider and retrieval-store protocols;
local-NumPy and pgvector adapters behind a feature flag (opt-in / shadow /
benchmark only — no silent production switch); disabled RulesLawyer
capability must not load the model; readiness distinguishes model-unavailable
from database-unavailable; Mongo env-var naming reconciled; privacy-safe
diagnostics; API contract unchanged. No DungeonMind domain ownership moves
(charter §10.3). Can start in parallel with B.1.

## PR F — deployment/IaC integration

**Repository:** DungeonOverMind (deployment orchestrator per ADR-0002)

Outcome: PostgreSQL lifecycle ownership explicit; private networking +
persistent volume; dedicated `dungeonmind` database and least-privilege role
(no generic/example credentials); backups + restore expectations documented;
resource limits + health checks; production/development configuration cannot
be confused accidentally.
