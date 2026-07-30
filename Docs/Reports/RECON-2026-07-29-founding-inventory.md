# REPORT — Founding reconnaissance and dependency inventory

**Date:** 2026-07-29
**Status:** accepted founding record
**Scope:** charter §5.1 (Buddy module inventory), §2.2/§10.1 (DungeonMindServer
+ RulesLawyer audit), §2.3 (RulesIngestion benchmark contracts), §5.2–5.3
(infrastructure + IaC ownership). Feeds ADR-0001/0002/0003 and the PR ladder.

All paths below are relative to the repos as checked out in the
`DungeonOverMind` workspace at founding. Line numbers are point-in-time
citations; GitHub current state wins on drift.

---

## §A DungeonMindBuddy — module inventory and classification

Classification vocabulary per charter §5.1. Full inventory covers 69
`graph_memory` Python files and 56 `tests/test_graph_*` files; the table
records the load-bearing units.

### A.1 Authority extraction (closed decisions confirmed)

Confirmed against `Docs/Design/ARCHITECTURE-campaign-supergraph.md`,
`ROADMAP-campaign-supergraph.md`, `PR-TRACKER-campaign-supergraph.md`,
`STATUS-world-graph-continuity-spine.md`, `CONTRACT-graph-kernel-boundary.md`,
`ARCHITECTURE-hermes-campaign-authoring-foundation.md`. The adopted decision
set is recorded in `Docs/Architecture/ARCHITECTURE.md` §3; supporting details:

- **Identity**: `GraphIdentityResolver` (deterministic-first, adjudication
  second, confidence never authority); outcome vocabulary
  `resolved_existing | created_new | provisional_new | ambiguous |
  blocked_collision | rejected | human_override`; merge/split/unmerge as
  durable replayable decisions
  (`kernel/identity.py`, `kernel/identity_decisions.py`,
  `identity_resolution.py`).
- **Revisions**: `ContentAddressedGraphStore` (`store.py`) — content-addressed
  append-only revisions, head advanced only by explicit publish with
  stale-parent rejection, three-way merge for publish conflict;
  `GraphIntegrityVerifier` (`verify.py`) — seven ordered checks; rollback is
  auditable repoint, never delete.
- **Contributions** are the sole write unit, lifecycle
  `active | superseded | retracted | failed` with mandatory audit fields;
  preview/fact paths must feed the reducer (`STATUS-world-graph-continuity-
  spine.md` §2.1–2.5, 4.1; `world_supergraph/persistence.py`).
- **Projections**: campaign/focus lenses with typed `Admissibility`
  (hard assertions/beliefs/claims vs soft focus-overlays); session = lens.
- **Retrieval**: read-only `GraphRetrievalSession` over exact revision with
  claim ledger, source anchors/reads, coverage, evidence admission
  (`interaction/graph_retrieval_session.py`, `query_plan.py`,
  `context_budget.py`, `answer_validator.py`, `contracts.py`).
- **Capability policy**: five categories
  `read_only | draft_only | preview_write | confirm_commit |
  admin_diagnostic`; fail closed; tool approval/config ≠ durable write
  authority; durable writes require typed capability + confirmation
  (`ARCHITECTURE-hermes-campaign-authoring-foundation.md` §7–9;
  `hermes/capability_policy.py`, `hermes/plugin_graph_tools.py`).

### A.2 Classification table (load-bearing modules)

| Module / file | Class | Notes |
| --- | --- | --- |
| `kernel/graph_memory.py` (WorldGraph, WorldGraphNode, WorldGraphRelationship, GraphDelta/Operation; `world_graph_schema_v1`/`_v2`) | MOVE_WITH_MINIMAL_CHANGE | Boundary-clean, stdlib+pydantic only. Apply: narrow `observed_kinds`; add `schema_version` literals; split mutable draft from immutable snapshot. |
| `kernel/models.py` (Contributor, CanonClassification, ContextSnapshotRef) | MOVE_WITH_MINIMAL_CHANGE | Same hygiene as above. |
| `kernel/store.py` (ContentAddressedGraphStore) | ADAPT | Correct semantics (content addressing, CAS, stale-parent, merge); replace dataclasses+`Path` blobs with protocol ports + opaque IDs. |
| `kernel/identity.py` (GraphIdentityResolver), `kernel/identity_decisions.py`, `identity_resolution.py` | ADAPT | Keep outcome vocabulary and adjudication order; replace alias-file/duck-typed internals. |
| `kernel/merge.py`, `kernel/verify.py`, `kernel/repair.py` | ADAPT | Semantics keep; express over snapshot payloads, not blobs. |
| `kernel/snapshots.py`, `kernel/publication.py`, `kernel/compaction.py` | ADAPT | Publication/compaction semantics keep; drop `Path` coupling. |
| `kernel/extraction_promotion.py` | ADAPT | Keep reducer-only write rule. |
| `kernel/ledger.py` | CONFORMANCE_FIXTURE_ONLY | Ledger semantics only; projections never own a store. |
| `world_supergraph/models.py` (ContestedFact/ChallengeRecord/ObservationEvent/ObservationWindow), `persistence.py` (CampaignAssertionRecord, envelope) | ADAPT | Keep envelope + lifecycle + `supporting_assertions`; session-union root keys are normalized away (drift G.1). |
| `world_supergraph/service.py`, `query.py`, `timeline.py` | REIMPLEMENT_BEHIND_PORT | Orchestration + `apps` imports + HTTP. Keep assertions' lifecycle tests as fixtures. |
| `world_supergraph/challenge_workflow.py` | ADAPT | Pure reducer; duck types → typed contracts. |
| `projection/{projection_contracts,projection_state,projection}.py` | MOVE_WITH_MINIMAL_CHANGE | Clean lens vocabulary (campaign/focus/admissibility, revision-pinned, never store). Split the oversized `projection.py` as in A.3. |
| `projection/context_projector.py` | CONFORMANCE_FIXTURE_ONLY | Keep windowing contract; re-implement adapter-specific bits. |
| `projection/session_plane.py` | ADAPT | Session-plane contracts keep; normalize "campaign+focus union" semantics (G.1). |
| `interaction/{contracts,graph_retrieval_session,query_plan,context_budget,answer_validator}.py` | ADAPT | The retrieval-session core. Keep `world_graph_schema_v1`-era contracts stable; drop `apps.*` imports (G.4); keep claim/evidence/coverage semantics. |
| `interaction/contracts_context.py` | MOVE_WITH_MINIMAL_CHANGE | Context contracts; minor typing hygiene. |
| `evidence/models.py` | ADAPT | Keep evidence semantics; **change `extra="allow"` → `extra="forbid"`** (G.2); keep SourceArtifact identity + anchor contracts. |
| `hermes/capability_policy.py` | ADAPT | Keep five categories + fail-closed posture; align runtime enforcement with doc taxonomy (G.3). |
| `hermes/plugin_graph_tools.py` | ADAPT | Keep capability-gated tool shape; drop hermes import at module scope. |
| `graph_memory/hermes_graph_plugin.py` | INSTRUCTIVE_ONLY | Plugin seam shape only; DungeonMind's adapter protocol replaces it. |
| `apps/live_control_server/services/{graph_projection_service,graph_query_router,graph_router,graph_preview_service,plan_graph_service}.py` | EXCLUDE / INSTRUCTIVE_ONLY | Transport + apps wiring; not reusable in DungeonMind. Preview service is product debt (G.5). |
| `evals/graph_memory_layer/` (full pipeline: fixtures → world → projection → retrieval → context pack → simulated Hermes write gate) | CONFORMANCE_FIXTURE_ONLY | Benchmark/eval harness; not production code. |
| 56 × `tests/test_graph_*` | CONFORMANCE_FIXTURE_ONLY | Behavioral pins for adopted semantics; port as conformance fixtures, not imports. |

### A.3 Notable implementation lessons (INSTRUCTIVE_ONLY)

- `projection/projection.py` (2,389 LOC) carries ≥6 unrelated lens families —
  split by family in DungeonMind.
- `union_supergraph/session_plane.py` + `world_supergraph/persistence.py`
  (2,540/1,183 LOC) normalize "campaign+focus union" and session-slice
  semantics — DungeonMind keeps campaign strictly as scope.
- `live_control_server/services/*graph*.py` show the anti-pattern of
  transport owning projection logic.
- Authoring-boundary leak pattern: preview/fact writes bypassing the
  reducer — DungeonMind has no preview authority paths at all.

---

## §B DungeonMindServer + RulesLawyer audit (charter §2.2, §10.1)

### B.1 statblocks_v1 — the engineering reference (reuse discipline, not domain)

- `statblocks_v1/application/repositories.py`: transport-neutral async
  repository protocols (create/get/list/update/replace/delete/exists +
  ownership checks). Adopt the port shape in
  `application/repositories.py`.
- `statblocks_v1/infrastructure/memory_repositories.py` +
  `firestore_repositories.py`: same port, two adapters; memory adapter for
  unit tests — mirrored by `infrastructure/memory/`.
- `statblocks_v1/infrastructure/runtime.py`: composition root selecting
  adapters from config — adopt for PR B postgres wiring.
- `statblocks_v1/api/http/compose.py`: mounts versioned HTTP at
  `/api/statblockgenerator/v1` — model for a future `service/api` host.
- Revision lineage discipline: create copies previous version, derives
  `revision` (`_apply_revision_lineage`), and write operations return
  "existing entity or idempotency conflict" (`_existing_or_idempotency_error`)
  — the idempotency posture DungeonMind adopts.

### B.2 RulesLawyer retrieval path (as deployed)

- `routers/ruleslawyer_router.py`: endpoints
  `/api/ruleslawyer/query`, `/rulebook/ingest`, `/rulebook/status`,
  `/rulebooks`, `/rulebook/aliases`, `/health`.
- `ruleslawyer/ruleslawyer_helper.py`: loads embedding CSVs
  (`get_embedding_csv_path`), builds a NumPy matrix in process, computes
  cosine similarity locally; hard-coded `EMBEDDING_MODEL = "BAAI/bge-m3"`,
  `BGE_M3_REVISION`, loads via `SentenceTransformer(EMBEDDING_MODEL,
  revision=..., device="cpu")`; the model is cached at module scope, so
  **every process that imports the helper loads its own model copy**.
- `ruleslawyer/hybrid_retriever.py`: semantic + BM25-like lexical fused by
  min-max normalization (`_normalize` → zeros on degenerate channel) +
  weighted sum; optional graph-adjacency boost. The degenerate normalization
  is preserved in DungeonMind's `weighted_minmax_fusion` as the parity
  baseline (ADR-0003).
- MongoDB (`MongoDBConfig`, `dependencies.py::get_mongo_client`) is the
  RulesLawyer store; `.env.example` uses inconsistent variable names
  (`MONGO_DB_NAME` vs `MONGO_DATABASE`, `MONGO_USER` vs `MONGO_USERNAME`) —
  recorded for PR E, not cleaned up here (charter §3.2).
- Health: `routers/health.py` exists; readiness does not currently
  distinguish model-unavailable from database-unavailable (PR E work).
- Deployment: root `Dockerfile` (in DungeonOverMind) builds the server;
  Caddy routes to it; `DISABLE_API_AUTH` env exists for dev. Model load
  blocking startup is not guarded — recorded for PR E.

### B.3 Hard boundary confirmed

None of: DungeonMind domain models, World Graph identity rules, projection
semantics, evidence admission, Mind Turn orchestration, reusable pgvector
repository contracts, graph reconstruction, model benchmark authority — may
live in DungeonMindServer (charter §10.3). PR E is a *consumer seam* only.

---

## §C RulesIngestion — benchmark contracts (charter §2.3)

Source of benchmark discipline; **eval-only relationship, never a runtime
dependency of DungeonMind** (Option B, ADR-0001/ROADMAP).

- `evals/retrieval/contracts.py`:
  `CorpusDoc {doc_id, source, title, text, system, chunk_index, metadata}`
  and `BenchmarkQuery {query_id, query, gold_doc_ids, relevant_doc_ids,
  query_type, rulebook, notes}` — `gold_doc_ids` primary targets,
  `relevant_doc_ids` for recall; `query_type ∈ {factoid, narrative,
  cross_reference}`; `validate_benchmark_projection` enforces gold ⊆ corpus,
  no duplicates, non-empty text.
- `evals/retrieval/metrics.py`: `recall_at_k`, `mrr`, `ndcg_at_k`,
  `precision_at_k`, `hit_at_k`, `gold_in_candidates` (+`min_gold_rank`),
  plus `per_query_comparison` (wins/losses per query — required reporting).
- `retrieval_lab/`: corpus shaping discipline — lock corpus before embedding;
  corpus fingerprint bound to projection; runs recorded with
  model/recipe/corpus/run-id/retrieval-mode; never compare runs whose
  substrate and knobs both changed.
- `scripts/run_embedding_bakeoff_multivariate.py`: multivariate bakeoff
  harness (the PR D pattern).
- `Docs/Workflows/WORKFLOW-Retrieval-Best-Practices.md`,
  `Docs/Reports/REPORT-Embedding-Bakeoff-Comprehensive-2026-03-04.md`,
  `Docs/Reports/REFERENCE-Retrieval-Benchmark-Results-Timeline.md`,
  `Docs/Design/v1/retrieval_lab_v1.md`: methodology + March 2026 results
  (all-mpnet-base-v2 hybrid = best supported cross-corpus default;
  pplx-embed-v1-0.6B led Starfinder MRR; BGE-M3 had the largest
  candidate-coverage failure cluster). Rulebook-corpus results only;
  campaign-prose benchmark is named debt (PR D handback).

**PR C shape (Option B):** RulesIngestion materializes an exact corpus +
projection; DungeonMind's pgvector retriever is invoked as an external
backend. Keeps DungeonMind free of eval-harness code and RulesIngestion free
of production dependencies.

---

## §D Infrastructure inventory (charter §5.2–5.3)

### D.1 Where PostgreSQL runs today

- **Production composition** lives at the `DungeonOverMind` repo root:
  `Dockerfile` (builds DungeonMindServer), `docker-compose.prod.yml`
  (server + Caddy), `docker-compose.dev.yml` / `docker-compose.local.yml`
  (MongoDB, Redis, mailhog for dev), `Caddyfile`, `Makefile`.
  **No PostgreSQL service exists in the production or dev DungeonMindServer
  topology.**
- **The only pgvector material** is LibreChat's vendored compose
  (`Sizzek/DungeonMindOvermind/LibreChat/LibreChat-Docker/docker-compose.yaml`
  and `Sizzek/LibreChat/docker-compose.yaml`):
  `image: pgvector/pgvector:pg16`, db `librechat`, port 5433, example
  credentials in the file. **Unverified**: not proven running, backed up,
  network-reachable, capacity-checked, or credential-safe. Its lifecycle is
  owned by the LibreChat stack.

### D.2 IaC ownership decision

DungeonOverMind is the deployment orchestrator in practice (it owns the
compose/Caddy/Dockerfile layer for the server). DungeonMindServer is a
stateless compute backend (state in Mongo/Redis/Firestore/R2). Decision
recorded as ADR-0002: DungeonMind owns schema/migrations/adapters/dev-CI
substrate; DungeonOverMind owns production PostgreSQL lifecycle (PR F);
DungeonMindServer owns only consumer config (PR E); RulesIngestion owns
benchmark methodology. Rejected: DungeonMindServer-as-IaC-owner (no evidence
it owns shared data infrastructure); LibreChat-instance reuse (ownership +
credential + verification failures); new dedicated IaC repo (deferred).

### D.3 Not committed / not printed

No secrets were printed or committed during recon. The LibreChat compose
contains generic example credentials — flagged as "never reuse" (charter
§14), not copied.

---

## §E Database comparison

Performed in ADR-0001 (PostgreSQL+JSONB+pgvector selected; MongoDB and
Firestore+external-vector rejected with reasons; comparison not assumed).

---

## §F Mind Turn design inputs (charter §4.2)

Recorded deviations from the conceptual target, implemented in
`contracts/mind_turn.py` (`mind_turn_v1`):

1. `caller_scope` is explicit (CallerScope: caller id/kind + capabilities) —
  keeps tenant authorization separate from `world_id`.
2. Projection vocabulary (`ProjectionFocus`, `Admissibility`, `Visibility`,
  `ScopeMode`) is shared with the projection contract family rather than
  re-declared — surfaces cannot smuggle graph semantics through the turn
  envelope.
3. Response reuses the retrieval-session sub-records (`Claim`,
  `ResolvedReferent`, `SourceRead`, `SourceAnchor`, `Coverage`,
  `DiagnosticEntry`) so a Mind Turn is a projection over the same read model
  the retrieval session produces, not a parallel type hierarchy.
4. No LandingPage layout names (drawers/panes/rails/cards) and no Hermes tool
  names appear in any core type.

---

## §G Drift register — where Buddy's implementation disagrees with its own closed decisions

DungeonMind follows the decisions, not the drift:

1. **Session-union root keys**: `world_supergraph/persistence.py` durable
   payloads still carry campaign+focus session-union keys at the root;
   `union_supergraph/session_plane.py` normalizes similar unions. DungeonMind
   models campaign strictly as scope on records (invariant: one graph per
   world).
2. **`extra="allow"` evidence models**: `evidence/models.py` permits unknown
   fields; DungeonMind contracts are uniformly `extra="forbid"`.
3. **Capability taxonomy split**: doc-level five categories vs runtime
   `allowed_effects={"read"}` in `hermes/plugin_graph_tools.py`; DungeonMind
   implements the five categories with a fail-closed evaluator
   (`domain/capability.py`).
4. **`apps.*` imports from reusable code**: `interaction/query_plan.py`,
   `answer_validator.py`, `world_supergraph/service.py` import
   `apps.live_control_server.*`; DungeonMind forbids any such import
   (import-boundary test).
5. **Preview/latest-ingest authority paths**: `graph_preview_service.py` and
   latest-ingest read paths exist as product debt; DungeonMind has no preview
   authority paths — preview is an explicit projection admissibility, never a
   store.
