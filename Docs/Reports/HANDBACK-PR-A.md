# HANDBACK — PR A: DungeonMind repository foundation

**Date:** 2026-07-29
**Charter:** `Docs/Handoffs/HANDOFF-found-dungeonmind-repository.md` §16

---

## 1. Repositories and revisions

```text
Repository   Drakosfire/DungeonMind (private, created this slice)
Branch       main
Base SHA     (none — founding commit)
Head SHA     a971c299ef993e52388dc0f12256475654e260d5
PR           n/a — founding commit pushed directly to main; PR flow starts at PR B
Status       LANDED
```

Sibling repositories touched: **none.** No DungeonMindBuddy, DungeonMindServer,
RulesIngestion, DungeonOverMind, or LandingPage files were modified.

Stop conditions (charter §15): none triggered. §15.1 checked first —
`Drakosfire/DungeonMind` did not exist at dispatch (name previously held by
what is now DungeonMindServer; renamed, so available; no conflicting content).

## 2. Decisions

### D1 — Primary datastore

```text
Question             PostgreSQL+JSONB+pgvector vs MongoDB vs Firestore+external vector
Evidence inspected   recon §B/D; charter §5.4 requirements; statblocks_v1 discipline
Decision             PostgreSQL + JSONB + pgvector (ADR-0001); hybrid relational/document v1
Rejected alternatives MongoDB + app-managed integrity (CAS/constraints move to app code;
                     Atlas Search splits the boundary); Firestore + external vector
                     (no CAS/full-text/recursive queries; boundary split);
                     LibreChat pgvector instance reuse (ownership/credentials/verification)
Consequences         PR B adds Alembic migrations + postgres adapters behind an extra;
                     normalization deferred until benchmarks demand it
Reversal path        Repository ports are the seam; contracts/domain unchanged by store swap
```

### D2 — Persistence lifecycle ownership

```text
Question             Who owns schema/migrations vs PostgreSQL service lifecycle
Evidence inspected   DungeonOverMind root Dockerfile/compose/Caddyfile/Makefile;
                     DungeonMindServer stateless-container evidence; LibreChat vendored
                     pgvector compose (pg16, unverified, generic example credentials)
Decision             DungeonMind owns schema/migrations/adapters/reconstruction/dev-CI
                     substrate; DungeonOverMind (deployment orchestrator) owns production
                     PostgreSQL lifecycle (PR F); DungeonMindServer = consumer config only;
                     RulesIngestion = benchmark methodology (ADR-0002)
Rejected alternatives DungeonMindServer as lifecycle owner (no evidence it owns shared
                     data infrastructure); LibreChat instance reuse; new dedicated IaC
                     repo (deferred)
Consequences        PR F must wire private networking, persistent volume, dedicated
                     dungeonmind db + least-privilege role, backups, resource limits
Reversal path       Orchestrator choice moves by moving compose/secrets wiring;
                     the DungeonMind-owned half is invariant
```

### D3 — pgvector role

```text
Question             What pgvector is allowed to be
Evidence inspected   charter §8; RulesLawyer hybrid_retriever min-max fusion behavior;
                     RulesIngestion benchmark contracts
Decision             Derived, disposable candidate-retrieval index only (ADR-0003);
                     exact search first, HNSW only after measured justification;
                     embeddings always rebuildable; re-embedding = new run;
                     RRF chosen default fusion; weighted min-max preserved verbatim
                     (including degenerate single-channel normalization) as parity baseline
Rejected alternatives Vector-score-as-fact (plain RAG posture); embeddings inside revision
                     payloads; default HNSW at bootstrap
Consequences        PR C can compare DungeonMind pgvector retrieval against RulesIngestion
                     baselines exactly; model experiments are additive, never mutations
Reversal path       Non-coupling by construction; index/fusion choices are config + new runs
```

### D4 — Mind Turn contract shape

```text
Question             How mind_turn_v1 deviates from the charter §4.2 conceptual target
Evidence inspected   Buddy interaction contracts + projection vocabulary (recon §A/F)
Decision             Explicit caller_scope; shared projection vocabulary; response reuses
                     retrieval-session sub-records; no surface-layout or Hermes names in types
Rejected alternatives Parallel type hierarchy for turns (would fork the read model)
Consequences        A Mind Turn is a projection over the same read model as a retrieval
                     session; surfaces cannot smuggle graph semantics through the envelope
Reversal path       Versioned supersession: mind_turn_v2 may replace v1 additively
```

### D5 — Module dispositions (charter §5.1)

Full table in recon §A.2. Headlines: kernel models/projection contracts =
MOVE_WITH_MINIMAL_CHANGE; store/identity/evidence/interaction/hermes-capability
= ADAPT; world_supergraph service/query/timeline = REIMPLEMENT_BEHIND_PORT;
evals + 56 test files = CONFORMANCE_FIXTURE_ONLY; apps graph services =
EXCLUDE/INSTRUCTIVE_ONLY. Drift register (recon §G): DungeonMind follows
Buddy's closed decisions where Buddy's implementation disagrees with them
(campaign-as-scope, extra=forbid, five-category fail-closed capability, no
apps imports, no preview authority paths).

## 3. Verification (exact commands and results)

Run in the repo root on the founding machine (uv 0.9.x, Python 3.12):

```bash
uv sync --locked          # Audited 12 packages — OK
uv run ruff check .       # All checks passed! (E,F,I,UP,B,SIM,RUF,ANN)
uv run pytest             # 74 passed in 0.09s
uv run --no-dev python -c "import dungeonmind"   # OK — no dev/heavy deps
```

Coverage of charter §13 repository-foundation gates:

- [x] `uv sync` succeeds (locked)
- [x] Core imports without optional infra/model deps (`--no-dev` import gate;
      also enforced structurally: only pydantic in base dependencies)
- [x] `uv run pytest` passes (74 tests)
- [x] `uv run ruff check .` passes
- [x] Import-boundary tests fail on reverse dependencies
      (`tests/unit/test_import_boundaries.py`: forbidden roots, layering
      contracts ← domain ← application ← infrastructure/agents, no sibling
      repos, no `apps.*`; layering violations injected-and-verified by the
      test's own positive/negative cases)
- [x] Public contracts round-trip exactly
      (`tests/unit/test_contract_roundtrip.py`: every contract family
      JSON round-trip + extra-field rejection)
- [x] README and architecture agree on ownership (README boundary section =
      ARCHITECTURE.md §2/§4)
- [x] No sibling repository runtime imports (test-enforced)

PostgreSQL / retrieval / DungeonMindServer / deployment gates: **not in PR A
scope** — scheduled at PRs B/C/E/F respectively. Not attempted, not claimed.

## 4. Benchmark summary

None in PR A (no retrieval runs yet). Benchmark program is contract-ready:
fusion parity baseline (`weighted_minmax_fusion`, degenerate normalization
verified against `ruleslawyer/hybrid_retriever.py` `_normalize` →
`np.zeros_like` behavior, test-pinned), `SemanticQuery`/candidate-channel
diagnostics, corpus-fingerprint-ready `EmbeddingRun` provenance. PR C/D own
the first runs under RulesIngestion discipline (Option B, external backend).

## 5. Current architecture

```text
where PostgreSQL runs:        nowhere yet (PR B: dev/CI containers; PR F: production)
which repository owns it:     lifecycle: DungeonOverMind (ADR-0002); schema/migrations: DungeonMind
which service consumes it:    none yet; DungeonMindServer becomes a consumer at PR E
how DungeonMind is invoked:   as a Python package (ports + in-memory adapters);
                              no API host yet (service/api lands with the demo slice)
where embedding models run:   nowhere in this repo; RulesLawyer's BGE-M3 stays
                              in DungeonMindServer until PR E; PR D benchmarks candidates
how vectors are rebuilt:      re-materialization from durable records under a new
                              EmbeddingRun (ADR-0003); tooling lands with PR B/C
what remains local/in-memory: all of DungeonMind (PR A is ports + memory adapters)
what remains Mongo-backed:    RulesLawyer catalog/retrieval data (unchanged; PR E seam)
```

## 6. What remains false

- **The demo does not exist.** No Mind Turn host, no LandingPage route.
- **Live ingestion does not exist.** Contribution ports exist; no ingestion
  pipeline or API.
- **Writes are not enabled** anywhere outside tests. Memory adapters implement
  CAS semantics for tests only; no durable store is wired.
- **Production RulesLawyer does not use pgvector.** Unchanged: BGE-M3,
  in-process NumPy, Mongo.
- **No model replacement was promoted.** No bakeoff run yet (PR D).
- **Campaign-prose retrieval is not benchmarked.** Named debt; successor
  benchmark must be created (rulebook results don't transfer).
- **LandingPage does not consume DungeonMind.**
- **DungeonMindBuddy has not been migrated** (and must not be — charter §14).
- **HNSW is not enabled** anywhere (exact search only, by policy).
- **Production backup/restore has not been tested** (no production PostgreSQL
  exists; PR F owns this).
- **No CI has run on GitHub yet** (workflow lands with this commit; first run
  triggers on next push/PR).

## 7. Named next slices

1. **PR B — PostgreSQL/pgvector development substrate** (DungeonMind).
   Handoff seed: ROADMAP PR B; migrations families per charter §7.2; CAS
   proof per §7.3; acceptance gates §13/PostgreSQL.
2. **PR E-prep — DungeonMindServer RulesLawyer audit → seam design**
   (DungeonMindServer, narrow). Recon §B already answers most of §10.1; the
   slice turns it into the feature-flagged provider/store protocol without
   touching production behavior. Independent of PR B; can start immediately.
3. **PR C — RulesIngestion external pgvector benchmark backend**
   (RulesIngestion). Depends on PR B (needs the DungeonMind retriever to
   invoke). Option B shape recorded in ADR-0001/recon §C.
4. **PR D — embedding bakeoff** (benchmark owner). Depends on PR C; must name
   the campaign-prose successor benchmark in its handback.
5. **PR F — DungeonOverMind production PostgreSQL wiring.** Depends on PR B
   (migrations exist to deploy); can be specced in parallel from ADR-0002.

## 8. §17 success-condition self-check

A fresh engineer cloning the repo can answer, from checked-in sources:

- What DungeonMind owns / what surfaces own / what DungeonMindServer owns →
  README + ARCHITECTURE.md §4
- What is authoritative vs derived → ADR-0003 + ARCHITECTURE.md §2
- Which revision is read; how head publication is atomic → contracts/graph.py
  + ARCHITECTURE.md §3 (PostgreSQL proof pending PR B — stated, not hidden)
- Source/evidence identity preservation → contracts/evidence.py + recon §A
- Embedding rebuilds; active model; benchmark support → ADR-0003 (rebuilds);
  "no model active in this repo" (stated plainly); PR C/D for benchmarks
- Where PostgreSQL runs; who owns migrations/backups/secrets → ADR-0002 +
  §5 above ("nowhere yet" is an explicit, checked-in answer)
- How a surface submits context → contracts/mind_turn.py
- How Hermes is replaced → agents/protocol.py (adapter port)
- Which durable writes are currently impossible → §6 above + capability
  contract (fail-closed; no write path exists outside tests)

Not complete because a repo exists — complete when the seam is explicit,
executable, tested, and hard to violate. PR A lands the seam; PRs B–F make it
durable, measured, and consumable.
