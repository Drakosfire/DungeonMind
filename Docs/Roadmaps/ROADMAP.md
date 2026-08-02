# DungeonMind — Roadmap and PR ladder

**Status:** PR A / A.1 / B / B.1a / B.1b / B.2a / B.2b landed. PR B.2c
(DungeonMindDnD Threat vocabulary and extraction candidates) is the current
DungeonMind-owned slice. External RulesIngestion PR C and product-surface
adoption of `mind_turn_v1` remain independent successors. Ownership per
ADR-0002, ADR-0004, and ADR-0005.

Each PR is independently reviewable, in its named repository. Cross-repo work
is never one PR.

## Sequence (amended)

```text
A     repository foundation ✅
A.1   foundational invariant hardening ✅
B     minimal PostgreSQL/pgvector substrate ✅
B.1a  thin read-only Mind Turn API host ✅
B.1b  DungeonMind-owned curated browser consumer proof ✅
B.2a  assertion-scoped alias/summary read projection ✅
B.2b  semantic profile boundary + dm_union_graph_v3 ✅
B.2c  DungeonMindDnD Threat vocabulary + extraction candidates ← current
B.1c* external product-surface adoption of mind_turn_v1 (e.g. LandingPage) — outside this repo
C     RulesIngestion pgvector benchmark backend
D     embedding model bakeoff
E     DungeonMindServer retrieval seam
F     production infrastructure hardening (DungeonOverMind)
```

\* B.1c is named only as an external successor. It is not claimed by B.1b/B.2a
and must land as a separate PR in the owning product repository.

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

## PR B.1b — Curated browser surface consumer proof ✅

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

## PR B.2a — Assertion-scoped alias and summary read projection ✅

**Repository:** DungeonMind only

Outcome:

```text
dm_union_graph_v2 revision
→ core object evidence remains coarse
→ each alias / summary admitted independently from its evidence
→ player and GM receive different safe field projections
→ same exact revision; v1 coarse behavior unchanged
```

Adds a second stored graph schema. Does **not** introduce a generic assertion
framework, assertion authoring, migrations, public contract changes, source
opening, Hermes, or product-surface adoption. Relationships remain coarse.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md`](../Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md).

## PR B.2b — Semantic profile boundary and dm_union_graph_v3 ✅

**Repository:** DungeonMind only

Outcome:

```text
dm_union_graph_v3
→ exact semantic-profile ref
→ qualified opaque semantic terms
→ generic registry/config
→ DungeonMindDnD sibling package
→ non-D&D canary
```

Adds a third stored graph schema whose payload pins one exact semantic
profile (`profile_id` + `profile_revision` + `descriptor_sha256`) and whose
node kinds and relationship predicates are qualified `namespace:local`
terms admitted by the pinned descriptor. Resolution flows through a generic
registry port fed by local operator config
(`DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH`); the default registry is
empty, so v3 fails closed with no silent D&D default. The D&D 5e descriptor
ships as package data in a data-only sibling package
(`src/dungeonmind_dnd/`, same repository and wheel, one-way dependency
enforced by test). The proof fixture pins the synthetic non-D&D
`test.narrative` profile: the canary proves kernel/profile decoupling, not
multi-system product support.

Does **not** introduce D&D mechanics or taxonomy in the kernel, a generic
ontology interpreter, executable plugins, public contract changes,
migrations, graph writes, source opening, Hermes, multi-system support, or
product-surface adoption. V1/v2 remain immutable and unqualified; their
fixture vocabulary is not canonical taxonomy. GM/player/canon/session
remains kernel policy, not claimed as universal TTRPG ontology.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2b-semantic-profile-boundary.md`](../Handoffs/HANDOFF-b2b-semantic-profile-boundary.md).
Decision record:
[`Docs/Decisions/ADR-0004-semantic-profile-boundary.md`](../Decisions/ADR-0004-semantic-profile-boundary.md).

## PR B.2c — DungeonMindDnD Threat vocabulary and extraction candidates

**Repository:** DungeonMind only

Outcome:

```text
dnd5e-profile-v2
→ threat-v1 vocabulary catalog (4 kinds / 4 predicates + direction)
→ strict provenance-bearing node/relationship candidate contracts
→ deterministic domain/range + evidence-ledger validation
→ deterministic JSON Schema + controlled-vocabulary prompt fragment
→ synthetic existing-node reference proof (Tripod Null-Calf)
```

Makes `dungeonmind_dnd` the first executable semantic-profile package
(ADR-0005): it loads one immutable profile revision and one immutable
Threat vocabulary catalog from package data, exposes strict versioned
candidate contracts suitable for structured LLM output or human-authored
JSON, renders deterministic JSON Schema and a catalog-derived prompt
fragment, and validates candidate terms, predicate direction/domain/range,
endpoint resolution, and a closed evidence ledger — while producing no
stable IDs, merge decisions, graph contributions, or durable writes.
Threat is modeled only as the contextual `dnd5e:threatens` relationship,
never as an object kind. The synthetic fixture connects new candidates
(`cand:tripod-null-calf`, `cand:north-gate-breach`) to an explicit existing
object reference (`obj:north-gate`) without claiming identity resolution or
graph read authority.

Does **not** change any file under `src/dungeonmind/`, call an LLM, read a
graph, resolve identity, plan contributions, publish revisions, model
mechanics/statblocks, add a generic interpretation layer, or add another
game system. The kernel remains D&D-blind (namespace admission only); the
v1 descriptor remains byte-for-byte immutable.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2c-dnd-threat-vocabulary-candidates.md`](../Handoffs/HANDOFF-b2c-dnd-threat-vocabulary-candidates.md).
Decision record:
[`Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md`](../Decisions/ADR-0005-dnd-profile-executable-boundary.md).

## Named future lanes (no dates claimed)

These lanes are named so successors can be dispatched deliberately. None is
scheduled, and none may be smuggled into an unrelated PR.

- **B.2d — graph-aware candidate resolution and contribution planning** —
  validated D&D candidates → graph-aware existing-node verification →
  exact-match identity blocking → explicit unresolved/merge/new outcomes →
  a non-mutating, reviewable contribution plan. Still no automatic
  publication.
- **B.3 — Threat mechanics-resource binding** — approved Threat graph
  identity → exact external statblock/mechanics resource ref →
  revision/digest pin → profile-owned hydration contract. Mechanics stay
  outside the graph body.
- **DungeonMindDnD further concrete semantics** — additional D&D
  vocabulary slices (classification, mechanics), owned by the profile
  package and landed only when demanded by a real consumer.
- **Profile interpretation layer** — anything beyond admit/reject
  (taxonomy reasoning, cross-profile mapping), only after a concrete
  second-system pressure proves what abstraction is needed.
- **Audience-policy generalization** — GM/player/canon assumptions
  revisited separately if a supported game requires it; kernel policy
  until then.

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
(charter §10.3). Can start in parallel with B.2b.

## PR F — deployment/IaC integration

**Repository:** DungeonOverMind (deployment orchestrator per ADR-0002)

Outcome: PostgreSQL lifecycle ownership explicit; private networking +
persistent volume; dedicated `dungeonmind` database and least-privilege role
(no generic/example credentials); backups + restore expectations documented;
resource limits + health checks; production/development configuration cannot
be confused accidentally.
