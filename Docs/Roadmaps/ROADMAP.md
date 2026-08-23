# DungeonMind — Roadmap and PR ladder

**Status:** PR A / A.1 / B / B.1a / B.1b / B.2a / B.2b / B.2c / B.2d /
B.2e / B.2f-0 / B.2f-a / B.2f-b / B.2f-c / B.2f-d landed. R.1 (direct World
Graph projection service, PR #38) landed; R.2 (direct World Graph retrieval
primitives, PR #40) landed. **R.2a (World Graph read observability + cutover
benchmark baseline) is in review as PR #41 and must land before any Buddy
production-read cutover.**
Product-surface adoption remains a separate successor. External RulesIngestion
PR C and product-surface adoption of `mind_turn_v1` remain independent
successors. Ownership per ADR-0002, ADR-0004, ADR-0005, ADR-0006, ADR-0007,
ADR-0008, ADR-0009, ADR-0010, ADR-0011, and ADR-0012.

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
B.2c  DungeonMindDnD Threat vocabulary + extraction candidates ✅
B.2d  pinned create-or-connect contribution plan ✅
B.2e  finalized contribution review adoption ✅
B.2f-0 accepted-review materialization characterization ✅
B.2f-a finalized-review graph payload materializer ✅
B.2f-b expected-parent CAS publication ✅
B.2f-c durable publication identity + uncertain-outcome recovery ✅
B.2f-d service transport + external consumer contract ✅
R.1   direct World Graph projection service (PR #38) ✅
R.2   direct World Graph retrieval primitives (PR #40) ✅
R.2a  World Graph read observability + cutover benchmark baseline (PR #41, in review)
R.3   Buddy graph hydration removal from production reads (Buddy repo)
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

## PR B.2c — DungeonMindDnD Threat vocabulary and extraction candidates ✅

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

## PR B.2d — Pinned Threat create-or-connect contribution plan

**Repository:** DungeonMind only

Outcome:

```text
validated Threat candidate packet
+ exact dm_union_graph_v3 StoredGraphRevision
→ graph integrity / profile pin verification
→ explicit existing-object verification
→ exact label/alias create-or-connect proposal
→ ambiguity / collision / duplicate blockers
→ candidate-only GraphContribution preview
→ expected-parent pin (no append, no publish)
```

Adds a repository-blind, profile-owned planner
(`plan_threat_candidate_contribution`) that reconciles one B.2c packet
against one exact stored revision and emits a deterministic
`DndThreatContributionPlan`. Exact matching may propose identity; it never
confirms it. Ready plans carry a candidate/GM/asserted contribution preview
only; blocked plans carry machine-readable blockers and no contribution.
No kernel source, vocabulary, profile artifact, migration, or repository
adapter changes.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2d-pinned-threat-contribution-plan.md`](../Handoffs/HANDOFF-b2d-pinned-threat-contribution-plan.md).
Decision record:
[`Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md`](../Decisions/ADR-0006-pinned-profile-contribution-planning.md).

## PR B.2e — Finalized contribution review adoption

**Repository:** DungeonMind only

Outcome:

```text
ready B.2d plan
+ complete GM assertion and candidate-identity verdicts
+ exact confirm_commit capability and confirmation receipt
→ current-head / exact-parent preflight
→ atomic superseded candidate contribution
→ active reviewed successor contribution
→ finalized review record
→ exact reload and idempotent replay
```

B.2e introduces generic review contracts, the repository-blind D&D
ready-plan adapter, the kernel authority service, and in-memory/PostgreSQL
review repositories. It does not create graph objects, append global identity
decisions, construct a publication command, advance the graph head, or add a
mutable review/API/UI/tool lifecycle.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2e-finalized-contribution-review-adoption.md`](../Handoffs/HANDOFF-b2e-finalized-contribution-review-adoption.md).
Decision record:
[`Docs/Decisions/ADR-0007-finalized-contribution-review-adoption.md`](../Decisions/ADR-0007-finalized-contribution-review-adoption.md).

## PR B.2f-a — Finalized-review graph payload materializer

**Repository:** DungeonMind only

Outcome:

```text
finalized ContributionReviewState
+ exact pinned StoredGraphRevision
+ matching GraphSnapshotReader
→ deterministic dm_union_graph_v3 payload
→ output reparse and semantic-profile validation
→ ephemeral result bound to review, parent, and payload digests
```

B.2f-a promotes the accepted B.2f-0 review-to-effects mapping into a generic,
side-effect-free kernel application seam. It materializes accepted node fields,
evidence, and deterministic relationships while preserving untouched parent
records and rejecting unsupported or colliding effects. It does not construct a
revision, read or advance a head, publish, persist, append identity decisions,
or expose transport.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2f-a-finalized-review-graph-materializer.md`](../Handoffs/HANDOFF-b2f-a-finalized-review-graph-materializer.md).
Decision record:
[`Docs/Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md`](../Decisions/ADR-0009-b2f-a-finalized-review-graph-materializer.md).

## PR B.2f-b — Finalized-review expected-parent CAS publication

**Repository:** DungeonMind only

Outcome:

```text
durable finalized review ID
+ exact current parent
+ B.2f-a materialization
→ one PublishRevisionCommand
→ atomic expected-parent CAS
→ immutable child revision + advanced head
→ ephemeral review/revision binding
```

B.2f-b is the first graph-head mutation for finalized reviews. The application
seam accepts only `(world_id, review_id)` plus the caller's publication
timestamp; it loads the exact durable B.2e review, rejects a stale preflight,
loads the pinned parent, materializes through B.2f-a, maps
`operation_ids=[review.operation_id]`, and invokes the existing repository CAS
once. It verifies the returned revision envelope and performs no post-commit
read, retry, recovery, identity-decision append, review mutation, or transport.

Still false after this PR: durable review-to-revision identity, retry-as-success,
uncertain-outcome recovery, public write surfaces, global identity-decision
append, and product-surface adoption.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2f-b-finalized-review-expected-parent-cas-publication.md`](../Handoffs/HANDOFF-b2f-b-finalized-review-expected-parent-cas-publication.md).
Decision record:
[`Docs/Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md`](../Decisions/ADR-0010-b2f-b-finalized-review-expected-parent-cas-publication.md).

## PR B.2f-c — Durable finalized-review publication identity and recovery

**Repository:** DungeonMind only

Outcome:

```text
durable finalized review ID
+ exact pinned parent
+ B.2f-a materialization
→ deterministic revision identity
→ one atomic revision + head CAS + publication record
→ exact durable replay or bounded predecessor adoption
→ one recovery probe after response loss
```

B.2f-c promotes the ephemeral B.2f-b binding to a versioned terminal
`dm_finalized_review_publication_v1` contract. A publication repository
cross-verifies the command against the finalized review and owns the same
transaction/lock as graph revision insertion, head advancement, and the normal
head event. Exact replay returns the original record before reading the parent
or graph reader, preserves its original timestamp, and remains valid after
descendants or explicit rollback.

If a publication call raises, the application probes once for the exact
durable record. A recovered record is success; otherwise an unexpected or
unavailable outcome becomes a sanitized retry-safe
`finalized_review_publication_outcome_unknown` error. The only predecessor
recovery is adoption of the exact deterministic B.2f-b revision, with no head
mutation or second head event. Same-review concurrency returns one record;
different reviews still rely on expected-parent CAS.

Still false after this PR: pending or failed publication lifecycle, attempts,
workers, queues, leases, retry schedulers, arbitrary history inference,
identity-decision append, review/contribution lifecycle mutation, public
transport, or product-surface adoption.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2f-c-durable-finalized-review-publication-recovery.md`](../Handoffs/HANDOFF-b2f-c-durable-finalized-review-publication-recovery.md).
Decision record:
[`Docs/Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md`](../Decisions/ADR-0011-b2f-c-durable-finalized-review-publication-recovery.md).

## PR B.2f-d — Finalized-review publication service transport

**Repository:** DungeonMind only

The separate publication host exposes `/healthz`, `/readyz`, and one
`POST /v1/finalized-review-publications` route. Callers submit only the strict
versioned `world_id + review_id` request. A one-world bearer digest authorizes
the edge, the server owns publication time, and the route delegates unchanged
to B.2f-c. Fresh success, exact durable replay, and response-loss recovery
return the same terminal publication record with `Cache-Control: no-store`.

The implementation includes sanitized error mappings, infrastructure-only
readiness, no CORS/browser write surface, OpenAPI separation, and a
standard-library-only external client with exact replay verification.

Still false after B.2f-d: review creation/edit/finalization transport, pending
or failed publication lifecycle, attempts, queues, workers, leases, schedulers,
automatic retries, GET polling, current-head success inference, identity-ledger
append, production auth, product adoption, and Threat mechanics/resource
binding.

Canonical handoff:
[`Docs/Handoffs/HANDOFF-b2f-d-finalized-review-publication-service-transport.md`](../Handoffs/HANDOFF-b2f-d-finalized-review-publication-service-transport.md).
Decision record:
[`Docs/Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md`](../Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md).
Runbook:
[`Docs/Runbooks/RUNBOOK-b2f-d-finalized-review-publication-service.md`](../Runbooks/RUNBOOK-b2f-d-finalized-review-publication-service.md).

## Buddy graph retirement cutover (R lane)

DungeonMindBuddy currently hydrates and reads through its own legacy graph
kernel even though DungeonMind is the graph authority. The R lane retires that
kernel by exposing DungeonMind's exact, admissibility-scoped graph reads
directly, measuring that authority seam deliberately, then deleting the
Buddy-side graph stack.

- **R.1 — direct World Graph projection service** — PR #38 ✅ (merged at
  `70f2f00a`). `WorldGraphProjectionService` resolves one exact revision (pin
  or current head), parses through an injected `GraphSnapshotReader`, and
  applies the existing campaign/admissibility/provenance projection —
  including the additive `world_cross_campaign` scope mode in the new v2
  projection contracts (cross-campaign lens: world-owned plus every campaign
  scope in one exact revision; the frozen v1 `world` mode remains world-owned
  only; admissibility is an independent axis, so PLAYER reads under the
  lens still fail closed on GM-only content). No Buddy DTOs, no write path, no
  semantic search.
- **R.2 — direct World Graph retrieval primitives** — PR #40 ✅ (merged at
  `fd0b7605`). `WorldGraphRetrievalService` composes the R.1 v2 projection
  exactly once
  per operation and owns the five graph-semantic capabilities needed to
  retire Buddy kernel reads: exact object lookup, deterministic graph-only
  search/referent resolution, bounded depth-1/depth-2 neighborhood expansion
  (depth 2 is required by the current production Hermes expansion contract),
  evidence retrieval by native object/relationship/assertion identity with
  per-chain provenance revalidation, and admitted source-anchor derivation
  with opaque context-bound revalidation. Search is lexical only — no vector
  store, semantic index, LLM, or file-search fallback. Anchor identity binds
  the complete v2 scope/revision/provenance context; no source body is opened.
- **R.2a — World Graph read observability + cutover benchmark baseline**
  (**first priority immediately after R.2; must precede R.3**) — PR #41 (in
  review). Delivered: the application-owned, vendor-neutral
  `WorldGraphReadObserver` seam (closed vocabularies, structural content
  safety, fail-open dispatch, no-op default) spanning R.1 projection
  (`head_lookup` / `revision_load` / `parse` / `scope_projection`) and all
  R.2 retrieval operations (operation-specific phases; exactly one nested
  project event plus one outer operation event per call); the deterministic
  synthetic-v6 + D&D v3 pyperf harness (dev-only) with digest preflight as
  a correctness gate; checked-in latency and traced-memory baselines over
  the 100/1k/5k/10k reference ladder; an informational CI benchmark-smoke
  artifact with no performance gate. Characterization findings (recorded,
  not optimized): full projection per operation is the structural read-cost
  floor (any read ≥ whole-graph projection; `get_object`@10k = 6.97s vs
  projection 6.74s); lexical search (+3.2s over projection at 10k) and
  deliberately-late anchor derivation (+2.8s) are the confirmed superlinear
  adders; peak traced memory is linear at ~32 KiB per admitted object
  (318 MiB at 10k, anchor resolution +50 MiB). Candidate optimization lanes
  (projection memoization keyed by content-addressed revision/scope/
  admissibility/profile, incremental parse, anchor supporter indexing) are
  named for successors, not this PR. Original lane scope: make the
  DungeonMind graph authority seam intentionally observable before Buddy
  switches production reads. DungeonMind owns the semantic observation model;
  hosts/adapters own export. Add a dependency-light/no-op-default observer port
  spanning R.1 projection and R.2 retrieval operations, with privacy-safe,
  low-cardinality signals for operation/phase duration, success/failure class,
  exact-pin vs head reads, scope mode/admissibility, graph/result sizes,
  truncation, neighborhood depth, provenance rejection/gap counts, and anchor
  resolution outcomes. Do not emit query text, labels/aliases, graph/source
  IDs, world/campaign IDs, or revision IDs as metric attributes. Establish
  latency distributions and scaling behavior before defining SLOs.

  Add a reproducible benchmark corpus over generated v6 graphs at multiple
  controlled sizes/densities and benchmark projection, exact lookup, search,
  depth-1/depth-2 neighborhood, evidence, and anchor resolution independently.
  Prefer a dedicated dev-only benchmark harness (e.g. `pyperf`) over ad-hoc
  stopwatch loops; record machine/environment metadata and comparable baseline
  artifacts. CI benchmark reporting should start informational rather than
  enforce brittle absolute latency thresholds. Explicitly characterize
  algorithmic scaling, especially full-projection cost and
  `resolve_source_anchor` behavior as graph/evidence volume grows.

  R.2a exit: DungeonMind can explain where graph-read time is spent and expose
  stable, privacy-safe operational signals without binding core to a telemetry
  vendor; a checked-in benchmark baseline records distributions/scaling for
  the native read path; the R.3 cutover has a named parity/performance witness
  shape ready to compare Buddy-hydrated and direct-DungeonMind reads.
- **R.3 — Buddy graph hydration removal** (DungeonMindBuddy repo, named
  successor after R.2a) — `CUTOVER: remove Buddy graph hydration from
  production reads`: pin the landed DungeonMind R.2/R.2a dependency; adapt
  Buddy `campaign` → v2 `campaign` and Buddy `world` → v2
  `world_cross_campaign`; replace `world_graph_projection` /
  `world_graph_retrieval` kernel calls with DungeonMind native reads; during
  cutover, compare normalized semantic parity and performance/operational
  signals between the Buddy-hydrated and direct-DungeonMind paths before
  deleting the old read path; move/retain the legitimate product-owned
  source-body opener outside `graph_memory` after DungeonMind validates the
  anchor; delete private Buddy revision translation and the frozen-store
  dependency from production read paths. Not write-path retirement.

Canonical handoffs:
[`Docs/Handoffs/HANDOFF-cutover-direct-world-graph-projection.md`](../Handoffs/HANDOFF-cutover-direct-world-graph-projection.md)
(R.1),
[`Docs/Handoffs/HANDOFF-cutover-direct-world-graph-retrieval.md`](../Handoffs/HANDOFF-cutover-direct-world-graph-retrieval.md)
(R.2), and
[`Docs/Handoffs/HANDOFF-cutover-world-graph-read-observability-benchmark.md`](../Handoffs/HANDOFF-cutover-world-graph-read-observability-benchmark.md)
(R.2a, this lane).

## Named future lanes (no dates claimed)

These lanes are named so successors can be dispatched deliberately. None is
scheduled, and none may be smuggled into an unrelated PR.

- **B.2f-d — service transport and external consumer contract** —
  expose the already-proven terminal publication/recovery seam to an external
  caller. Transport must not add a pending lifecycle, second confirmation,
  identity-ledger append, or product-specific authority.
- **B.3a — Threat mechanics-resource binding** ✅ — approved Threat graph
  identity → exact external statblock/mechanics resource ref →
  revision/digest pin → profile-owned hydration contract (historical
  `dnd5e-profile-v2` / `threat-v1` path; hostility-gated).
- **World-object mechanics re-anchor (ADR-0013)** ✅ — additive
  `dnd5e-profile-v3` / `world-object-v1` with persistent Threat/NPC/PC kinds
  and hostility-independent exact mechanics attachment (zero/one/many
  statblock roles). Transport, Buddy bridge, shadow, and Play remain
  successors.
- **DungeonMindDnD further concrete semantics** — additional D&D
  vocabulary slices, owned by the profile package and landed only when
  demanded by a real consumer.
- **Buddy → DungeonMind conformance bridge** — adapt exact Buddy
  world-object/mechanics identity into the re-anchored D&D contract
  (fixture/test-backed first; not live shadow).
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
