# DungeonMind — Roadmap and PR ladder

**Status:** PR A / A.1 / B / B.1a landed. PR B.1b (DungeonMind-owned curated
browser consumer proof) is the current DungeonMind slice. External
product-surface adoption of `mind_turn_v1` remains a separate, still-false
successor outside this repository. Ownership per ADR-0002.

Each PR is independently reviewable, in its named repository. Cross-repo work
is never one PR.

## Sequence (amended)

```text
A     repository foundation ✅
A.1   foundational invariant hardening ✅
B     minimal PostgreSQL/pgvector substrate ✅
B.1a  thin read-only Mind Turn API host ✅
B.1b  DungeonMind-owned curated browser consumer proof   ← current
B.1c* external product-surface adoption of mind_turn_v1 (e.g. LandingPage) — outside this repo
C     RulesIngestion pgvector benchmark backend
D     embedding model bakeoff
E     DungeonMindServer retrieval seam
F     production infrastructure hardening (DungeonOverMind)
```

\* B.1c is named only as an external successor. It is not claimed by B.1b and
must land as a separate PR in the owning product repository.

The demo may use deterministic fixture embeddings or the benchmark baseline.
It proves the replaceable UI-to-Mind seam before several PRs optimize and
operationalize retrieval.

## PR A — DungeonMind repository foundation ✅

**Repository:** DungeonMind

Delivered: package scaffold (`uv`, Pydantic v2); contract families; domain
logic; application repository ports; in-memory adapters; curated fixture;
unit tests; lint+CI; founding docs (architecture, authority, ADRs 0001–0003,
recon report, handoff template).

## PR A.1 — Foundational invariant hardening ✅

**Repository:** DungeonMind

Exit proof (initial hardening + contract-blocker closure):

- Explicit, fail-closed admissibility/visibility on all request contracts
  (absence never means GM).
- Parent/head lineage equality on normal graph publication
  (`parent == expected == current_head`).
- Deep-copy immutability for stored graph payloads.
- Canonical idempotency conflicts for source, semantic, thread, and embedding
  records.
- Cross-field validators for evidence, source types, semantic documents,
  identity decisions, focus, scope, claims, and accepted assertions.
- Closed admitted-evidence ledger on retrieval sessions and Mind Turn
  responses (no invented evidence/anchor grounding).
- Embedding-run monotonic lifecycle with typed transition errors and
  non-rewriting terminal retries; active-materialization semantics so only
  COMPLETED non-superseded runs participate in retrieval.
- Exact semantic-document provenance (`source_revision_id` /
  `graph_revision_id`) plus materialization-run metadata compatibility.
- v1 threads: caller-private, cross-surface; immutable
  world/campaign/caller/tenant binding; retry-safe `turn_id` append.
- One capability policy authority; permitted tools derived, never caller-supplied;
  `AgentTurnContext` rejects input/policy graph-scope disagreement.
- Unambiguous campaign/focus scope (no `campaign_id` on focus; world/campaign
  modes cannot contradict).
- Sanitized agent-adapter input (no caller/tenant auth metadata).
- Static type checking (Pyright) in CI.

## PR B — PostgreSQL/pgvector development substrate ✅

**Repository:** DungeonMind (+ deployment owner only if dev/CI wiring needs it)

Delivered:

- `migrations/` (Alembic) implementing the minimum schema families with
  relational identity/lifecycle columns + JSONB payloads;
- pinned dev/CI pgvector image + compose; health check verifies PostgreSQL
  and the pgvector extension;
- `infrastructure/postgres/` adapters for the repository ports, behind the
  `postgres` extra;
- graph revision/head CAS proven against real PostgreSQL;
- semantic documents inserted and exactly searched (dense + full-text +
  exact + fusion + filters);
- integration tests opt-in locally, required in CI.

## PR B.1a — Thin read-only Mind Turn API host ✅

**Repository:** DungeonMind

Delivered:

```text
MindTurnRequest
→ trusted demo-access authorization
→ exact graph revision pin
→ hybrid candidates + deterministic fusion
→ scoped graph resolution + evidence admission
→ context assembly + read-only fixture agent
→ MindTurnResponse + retrieval-session / thread persistence
```

Public endpoints remain exactly `/healthz`, `/readyz`, `/v1/mind-turn`.
Single-worker demo host; process-local request coordination is not claimed as
cross-worker exactly-once execution.

## PR B.1b — Curated browser surface consumer proof

**Repository:** DungeonMind only

Outcome:

```text
stdlib static example (examples/curated_mind_turn_surface)
→ second-origin browser
→ existing Mind Turn API (mind_turn_v1)
→ readiness, grounded answer, projections, abstention, exact replay,
  sanitized failure
```

Framework-free HTML/CSS/JS acceptance consumer. Proves cross-origin CORS
against the existing single configured origin. Does **not** move product UI
ownership into DungeonMind, add endpoints, expand contracts, open sources,
or adopt Hermes.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b1b-curated-browser-surface.md`](../Handoffs/HANDOFF-b1b-curated-browser-surface.md).
Runbook:
[`Docs/Runbooks/RUNBOOK-b1b-curated-browser-surface.md`](../Runbooks/RUNBOOK-b1b-curated-browser-surface.md).

## External successor — product-surface adoption (still false)

**Repository:** LandingPage or another product owner (not DungeonMind)

A future product route may consume `mind_turn_v1` the same way the B.1b
example does. That work is independently useful and must not be smuggled into
DungeonMind PRs.

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
(charter §10.3). Can start in parallel with B.1b.

## PR F — deployment/IaC integration

**Repository:** DungeonOverMind (deployment orchestrator per ADR-0002)

Outcome: PostgreSQL lifecycle ownership explicit; private networking +
persistent volume; dedicated `dungeonmind` database and least-privilege role
(no generic/example credentials); backups + restore expectations documented;
resource limits + health checks; production/development configuration cannot
be confused accidentally.
