# Report — 2026-08-30 K0.1 current consumer and public-surface inventory

**Status:** observational evidence for K1 eligibility; not a deletion authorization  
**Ledger (generated):** [`K0-surface-inventory.json`](K0-surface-inventory.json)  
**Dispositions (human-authored):** [`K0-dispositions.toml`](../Inventory/K0-dispositions.toml)  
**Schema:** `dm_k0_surface_inventory_v1`  
**Formal review cycles:** 5 (includes PR #48 audit-correctness passes)

`NO_KNOWN_EXTERNAL_CONSUMER` means exactly that. It is not permission to delete.

## 1. Inputs, anchors, and reproduction

```text
dungeonmind_runtime_anchor              = 5ca5d688612349034f8ca490d465af166d883e6e
dungeonmind_steward_base                = 84a4479494a37d8b5bd550465d17ff29f0e359ec
runtime_tree_digest                     = sha256:0fa4c6042ae6ee8c51a19c1b20f76b095ab6885e0587156c5d57e9d49fbbc700
dungeonmind_module_string_scan_ref      = 5ca5d688612349034f8ca490d465af166d883e6e
dungeonmind_module_string_corpus_digest = sha256:044984424db62ddefcf0279e29fdd2cc16c868390fa29c9c5e4166856d259814
buddy_anchor                            = a9d4c61d04f2a4a5f92cb6947442d8173079454c
buddy_dungeonmind_pin                   = 5ca5d688612349034f8ca490d465af166d883e6e
buddy_import_scan_ref                   = a9d4c61d04f2a4a5f92cb6947442d8173079454c
buddy_import_corpus_digest              = sha256:9db4711fe4205e7934be173d4e4ed6d866f0a1fcf3de085081c1fd9560246418
buddy_module_string_scan_ref            = a9d4c61d04f2a4a5f92cb6947442d8173079454c
buddy_module_string_corpus_digest       = sha256:84cc945aee63e9f883d9364790095e5ac1a317f422493c25d66dcfb8822e0e05
```

The generated ledger describes the audited runtime tree at `dungeonmind_runtime_anchor`. It does **not** record the commit that contains the JSON artifact (no self-referential `dungeonmind_scanned_head`). PR/branch provenance belongs in git history and this report, not in the machine ledger. DungeonMind module-string evidence is taken from that same runtime-anchor tree (`dungeonmind_module_string_scan_ref` + `dungeonmind_module_string_corpus_digest`), so report/runbook edits on this branch are not undeclared inputs.

The generator fails closed if Buddy lacks the required anchor object / pin, or if `src` / `migrations` / `pyproject.toml` / `uv.lock` differ from the runtime anchor.

```bash
uv run python scripts/k0_surface_inventory.py \
  --dungeonmind-root . \
  --dungeonmind-code-anchor 5ca5d688612349034f8ca490d465af166d883e6e \
  --buddy-root ../DungeonMindBuddy \
  --buddy-anchor a9d4c61d04f2a4a5f92cb6947442d8173079454c \
  --expected-buddy-dungeonmind-pin 5ca5d688612349034f8ca490d465af166d883e6e \
  --output Docs/Reports/K0-surface-inventory.json
```

Curated architecture judgments live in TOML; the scanner combines derived facts + dispositions into the JSON snapshot.

Buddy and DungeonMind consumer evidence are both scanned from exact git trees at their declared SHAs (imports + module strings). A dirty Buddy worktree or untracked file cannot mutate the ledger while `inputs.buddy_anchor` stays fixed.

## 2. Headline counts

| Measure | Count |
|---|---|
| Buddy files importing `dungeonmind*` | 16 |
| Distinct imported modules | 28 |
| Distinct imported symbols | 89 |
| Explicit exported symbols inventoried | 444 |
| Repository protocol/bundle entries | 14 |
| PostgreSQL tables | 20 |
| Import-boundary exceptions | 9 |
| Dynamic-import findings (importlib/`__import__`) | 0 |
| Module-string / deployment findings (Buddy + DungeonMind) | 3220 |
| Subsystem USED | 9 |
| Subsystem UNUSED | 9 |
| Subsystem HISTORICAL-COMPAT | 4 |
| Subsystem UNKNOWN | 3 |

Import statements: 73 production, 54 test. Tests are recorded as imports; they do not by themselves make a subsystem `USED`.

## 3. Current Buddy import surface

Production consumers are only the live-control DungeonMind integration:

- `apps/live_control_server/integrations/dungeonmind/world_graph_reads.py`
- `apps/live_control_server/integrations/dungeonmind/world_graph_writes.py`
- `apps/live_control_server/integrations/dungeonmind/world_graph_source_admission_adapter.py`
- `apps/live_control_server/integrations/dungeonmind/world_graph_initialization_adapter.py`
- `apps/live_control_server/integrations/dungeonmind/contribution_mapping.py`
- `apps/live_control_server/integrations/dungeonmind/assertion_qualification.py`

That surface is World read, source admission, reviewed first-world init, contribution review, and exact-parent publication. Buddy constructs `PostgresDatabase` + `PostgresRepositoryBundle` and `VersionedUnionGraphSnapshotReader`.

`dungeonmind_dnd` production imports are only `load_builtin_v3_descriptor` and `load_builtin_world_object_v5_vocabulary`.

Hermes/agent code at this Buddy pin does not import `dungeonmind.application.mind_turn` or `dungeonmind.agents`.

Buddy tests additionally import in-memory adapters, `PublishRevisionCommand`, adoption receipt types, and `PostgresDatabase` for cutover proofs. Those are consumer-test imports, not a second production path.

## 4. Explicit export surface

Package `__init__` re-exports are a museum: 444 names. Export consumer matching now distinguishes **re-export path** imports from **origin-module** symbol imports (`buddy_direct_reexport_import`, `buddy_origin_symbol_import`). Example: Buddy imports `WorldGraphProjectionService` from `dungeonmind.application.world_graph_projection`, so the re-export at `dungeonmind.application` is marked `known_external_consumer: YES` via the origin path even though Buddy never imports through the package facade.

`PostgresRepositoryBundle` is a current production import and is **not** listed in `dungeonmind.infrastructure.postgres.__all__`. `__all__` is not the consumer map.

This inventory does not promote the museum into a supported public API.

## 5. Repository and table classification

Current World authority ports (`USED`): `WorldGraphRepository`, `SourceRepository`, `ContributionRepository`, `ContributionReviewRepository`, `FinalizedReviewPublicationRepository`, `IdentityDecisionRepository`, `ExistingWorldAdoptionRepository` (receipt **read** for genesis), `ReviewedWorldInitializationRepository`, and `PostgresRepositoryBundle`.

Founding-runtime ports with no Buddy/World call path (`UNUSED` code, tables stay): `MindThreadRepository`, `RetrievalSessionRepository`, `SemanticDocumentRepository`, `EmbeddingRunRepository`, `SemanticSearchPort`.

Bundle construction instantiates the unused adapters. Construction is not use.

| Tables `USED` | Tables `HISTORICAL-COMPAT` (K1 may excise runtime while the table remains) |
|---|---|
| worlds, campaigns, graph_revisions, world_graph_heads, world_graph_head_events, source_artifacts, source_revisions, evidence_refs, graph_contributions, identity_decisions, contribution_reviews, finalized_review_publications, existing_world_adoptions, reviewed_world_initializations | retrieval_sessions, mind_threads, mind_turns, embedding_runs, active_embedding_runs, semantic_documents |

Alembic creates tables via `op.execute("CREATE TABLE {SCHEMA}.…")`, not `op.create_table`. The scanner parses that SQL. 20 tables, each once. Migrations 0004/0005 only alter `source_artifacts`.

## 6. Subsystem demolition ledger

### USED

- World graph projection/retrieval
- source/evidence repositories
- contribution review/publication
- reviewed first-world initialization
- existing-world adoption **receipt read** (Buddy genesis binder)
- versioned union-graph snapshot dispatch
- semantic-profile registry
- D&D profile/planning/mechanics packages (Buddy uses vocabulary/descriptor loaders; remaining profile application logic is still current package authority)
- CapabilityPolicy as **contribution-review authorization** (Buddy `world_graph_writes.py`)

### UNUSED — K1 code-eligibility only

K1 still needs its own PR-level proof. These are not already deleted.

| Target | Falsification sought |
|---|---|
| MindTurn contracts + MindTurnService | Buddy/Hermes/World-path imports of `mind_turn`; none at the pin. Remaining callers: optional FastAPI host, curated scripts, DungeonMind tests |
| agents/ protocol + fixture | Buddy/Hermes `dungeonmind.agents`; none. Only MindTurnService |
| CapabilityPolicy as **agent-visible tool authority** | Buddy `evaluate_capability` / `permitted_tool_names`; none. The CapabilityPolicy **type** is USED for review and is a separate row |
| context assembly / MindTurn budgeting | only `MindTurnService` imports `assemble_agent_context` |
| MindThread / RetrievalSession / SemanticDocument / EmbeddingRun / semantic-search runtime | no Buddy call; World retrieval is graph-only. Physical tables remain `HISTORICAL-COMPAT` |

### HISTORICAL-COMPAT — blocks physical deletion

- existing-world adoption **write/command** (living Eldyrwild genesis)
- adoption repair (durable V4 M0/M1 authority)
- correspondence (adopted membership re-proof)
- v1-v5 historical graph schema codecs (dispatched on the current read path so historical pins remain readable)

### UNKNOWN — blocks demolition

- claim / answer-validation machinery: Claim ledger shares `contracts/retrieval.py` with `ResolvedReferent` used by current World retrieval. Split the module first.
- optional FastAPI/httpx D&D transport / statblock resource resolver: Buddy uses `dungeonmind_statblocks`, not this extra. Another deployment might. Do not guess.
- demo_access / curated MindTurn host: runbook at the runtime-anchor tree documents `uvicorn …dungeonmind.service.bootstrap:create_demo_app`. No Buddy consumer, but static-import absence alone is insufficient for demolition. Auto-downgraded from a would-be `UNUSED`.

## 7. Module-string and deployment evidence

Beyond Python `import` AST scanning, the ledger records conservative module-string hits from both repos: `uvicorn package.module:app`, `python -m …`, `pyproject.toml` script values, compose/Docker/shell/markdown/runbook text, and subprocess command arrays where present.

**DungeonMind module-string evidence is scanned from the exact git tree at `dungeonmind_runtime_anchor` (`inputs.dungeonmind_module_string_scan_ref`), not from the mutable PR worktree.** Buddy imports and module-string evidence are likewise scanned from the exact git tree at `buddy_anchor` (`buddy_import_scan_ref`, `buddy_module_string_scan_ref`) with declared corpus digests. Dirty tracked files and untracked paths cannot change the machine ledger without changing a declared input.

Findings are tagged by `consumer_kind` (`production`, `documented_deployment`, `deployment_or_tooling`, `documentation`, `inventory_tooling`, `test`). Only production/deployment/runbook hits can auto-downgrade an `UNUSED` subsystem to `UNKNOWN`.

Buddy AST dynamic-import findings remain 0 at this pin.

## 8. Import-boundary exceptions

| Exception | Protects |
|---|---|
| application ↔ agents mutual allowance | `HISTORICAL_OR_FOUNDING` |
| postgres-only roots (`psycopg`, `pgvector`) | `CURRENT_REQUIRED` |
| forbidden roots | `CURRENT_REQUIRED` |
| D&D planning / review / mechanics allowlists | `CURRENT_REQUIRED` |
| api-only roots (`fastapi`, …) | `UNKNOWN` — `service/api.py` hosts MindTurn **and** publication / fictional-time HTTP |
| D&D transport FastAPI and resource httpx | `UNKNOWN` |

This PR does not change the import rules.

## 9. Optional dependency / import findings

`import dungeonmind` loads no postgres/api extras and does not load `dungeonmind_dnd`.

`import dungeonmind_dnd` still loads no `fastapi`, `psycopg`, `sqlalchemy`, or `httpx`.

This matches `tests/unit/test_import_boundaries.py`.

## 10. Unknowns

See ledger `unresolved_questions`. Headline blockers: mixed retrieval contracts; optional D&D HTTP extra; mixed FastAPI host; documented demo/bootstrap deployment without Buddy consumer.

## 11. K1 eligibility list

Only `UNUSED` targets above. Warning: K1 still needs its own proof. Do not delete historical tables, codecs, adoption receipts, or mixed modules.

Blocked:

- `HISTORICAL-COMPAT`: adoption write, repair, correspondence, v1-v5 codecs, and the six semantic/thread tables
- `UNKNOWN`: claim/answer module, D&D optional HTTP, demo_access / curated MindTurn host
- `USED`: World read/write/init/source/review/publication/profile

## Review telemetry

### Cycle 1 — coverage / false-negative review

Findings and fixes:

1. Buddy `from dungeonmind.application import reviewed_world_initialization` is a submodule import. The resolver now accepts package-submodule names, not only `__init__` bindings.
2. Alembic tables are created with `op.execute` SQL and `{SCHEMA}.table`, not `op.create_table`. The scanner parses that form; coverage is 20/20.
3. `VersionedUnionGraphSnapshotReader` lazily imports v4/v5/v6. Those codecs stay `HISTORICAL-COMPAT` even though they sit on the hot path.
4. `PostgresRepositoryBundle` constructs unused semantic/thread adapters. Construction was not treated as `USED` for those ports.
5. `provider="dungeonmind"` and `dungeonmind.dungeonbuddy-statblocks` are product strings, not Python imports. After tightening the module regex and limiting dynamic detection to `import_module` / `__import__` / `run_module`, dynamic-import findings are 0.
6. FastAPI `service/api.py` also serves publication and fictional-time routes. The `api` extra is not automatically founding-only.

### Cycle 2 — demolition-safety adversarial review

Every `UNUSED` row was challenged (indirect Buddy use, World path, living DB, compatibility reader, dynamic load).

Downgrades:

- **claim / answer-validation** from a would-be `UNUSED` to `UNKNOWN` because `contracts/retrieval.py` is shared with current World retrieval.
- **CapabilityPolicy** split: agent-visible tool authority remains `UNUSED`; review authorization is `USED` (Buddy import).
- **existing-world adoption** split: receipt read is `USED`; write/command is `HISTORICAL-COMPAT`.
- Semantic/thread **tables** stayed `HISTORICAL-COMPAT` even where runtime is `UNUSED`.

No remaining `UNUSED` target has a Buddy import of its covered prefix. Living-database contents were not queried (handoff forbids Eldyrwild). Table protection is the substitute for that unknown.

### Cycle 3 — PR #48 audit-correctness (review 5063054103)

Fixes:

1. Removed self-referential `dungeonmind_scanned_head`; ledger identity uses `inputs.runtime_tree_digest` at the fixed runtime anchor.
2. Split curated judgments into `Docs/Inventory/K0-dispositions.toml`; JSON is generated-only evidence with `dispositions_digest`.
3. Export consumer map matches origin-module symbol imports, not only re-export `(module, name)` pairs.
4. Expanded module-string/deployment scanning; `demo_access` downgraded to `UNKNOWN` on runbook uvicorn bootstrap evidence.
5. Recorded known red `benchmark-smoke` baseline (pre-existing at anchor; not repaired in K0.1).

### Cycle 4 — PR #48 second-pass (review 5068857983)

Fixes:

1. DungeonMind module-string scan pinned to exact `dungeonmind_runtime_anchor` git tree (not PR worktree); corpus digest recorded in `inputs`.
2. Human report `UNUSED`/`UNKNOWN`/blocked-summary aligned with machine ledger for `demo_access`.
3. TOML dispositions loader rejects duplicate curated IDs.

### Cycle 5 — PR #48 third-pass (review 5069068685)

Fixes:

1. Buddy imports and module-string evidence pinned to exact `buddy_anchor` git tree (not filesystem checkout); pin read from that tree; corpus digests recorded in `inputs`.
2. Report formal review-cycle count corrected to match documented cycles.

## Known CI baseline (not repaired in K0.1)

| Job | Status at runtime anchor | Disposition |
|---|---|---|
| `core` | green | — |
| `integration` | green | — |
| `benchmark-smoke` | **red** | pre-existing defect |

Failure: `WorldGraphProjectionService.__init__() missing required keyword-only argument: 'reviewed_world_initializations'` in `benchmarks/world_graph_reads.py`. The benchmark harness at anchor `5ca5d688…` constructs the service without that repository while the service already requires it. Corrective slice: repair benchmark construction; do not fold runtime fixes into K0.1.

## Verification

| Gate | Result |
|---|---|
| Deterministic generator rerun (`cmp`) | identical |
| `uv run pytest tests/unit/test_k0_surface_inventory.py tests/unit/test_import_boundaries.py` | green |
| `uv run ruff check .` | green |
| `uv run pyright` | 0 errors |
| `uv run pytest -m "not integration"` | green |
| Disposable Postgres integration (`uv sync --locked --extra postgres --extra api`, `alembic upgrade head`, `pytest -m integration` on `127.0.0.1:54329`) | green |
| `git diff --exit-code 5ca5d688… -- src alembic pyproject.toml uv.lock` | no diff |
| Buddy worktree `a9d4c61…` pin `5ca5d688…` | matched |

Buddy was not modified and was not repinned.

## What this does not prove

K0.1 does not prove that any `UNUSED` target has been deleted; that MindTurn/agents/semantic runtime are physically removable without K1 tests; that historical tables/codecs may be dropped; that the public API has been consolidated; that DungeonMind is domain-neutral; that RulesKnowledge is supported; that performance improved; that K2 passed; or that Buddy may be repinned.

## Named next slices

1. K0.2 — Golden semantic witness
2. K0.3 — Performance baseline expansion
3. K1.1 — Runtime/public excision, only after K0 is complete and only against targets this ledger marks `UNUSED`
