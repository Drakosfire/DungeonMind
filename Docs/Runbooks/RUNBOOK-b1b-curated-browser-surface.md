# RUNBOOK — B.1b Curated browser surface consumer proof

**Purpose:** Prove the repository-local static browser example against a real
PostgreSQL-backed Mind Turn host on a second origin. This is an acceptance
consumer, not a product surface.

**Prerequisites**

* Docker with Compose
* `uv`
* A normal desktop browser (Chrome, Firefox, or Chromium)
* Ports `54329`, `8000`, and `8081` free on loopback

## 1. Start PostgreSQL and migrate

```bash
cd /path/to/DungeonMind
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
```

## 2. Seed the curated fixture (idempotent)

```bash
uv run python scripts/seed_curated_mind_turn.py
uv run python scripts/seed_curated_mind_turn.py
```

Expected: first run creates or confirms the fixture; second run reports an
exact idempotent replay (same world/revision/thread identifiers).

## 3. Start the Mind Turn API with browser CORS

In terminal A (single worker — required for B.1a process-local coordination):

```bash
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
export DUNGEONMIND_CORS_ORIGIN=http://127.0.0.1:8081
uv run uvicorn dungeonmind.service.bootstrap:create_demo_app --factory \
  --host 127.0.0.1 --port 8000 --workers 1
```

Smoke:

```bash
curl -sS http://127.0.0.1:8000/healthz
curl -sS http://127.0.0.1:8000/readyz
```

## 4. Start the static browser example

In terminal B:

```bash
uv run python scripts/serve_curated_mind_turn_surface.py
```

Expected console lines include:

* browser URL `http://127.0.0.1:8081/`
* required CORS origin `DUNGEONMIND_CORS_ORIGIN=http://127.0.0.1:8081`

## 5. Manual browser checklist

Open `http://127.0.0.1:8081/` (not `localhost` — origin must match CORS).

| Step | Action | Expected observation |
| --- | --- | --- |
| 1 | Page load | Readiness becomes ready; Ask enables; no external network/CDN requests in DevTools |
| 2 | Ask “Who safeguards the Sun Ledger?” | Answer contains Mere Astor; `revision_id` starts with `rev:`; entity briefs for Mere Astor and Sun Ledger; `safeguards` relationship; evidence IDs listed; status Grounded |
| 3 | Replay exact request | Status shows Exact replay matched; answer/revision/projections unchanged |
| 4 | Ask “Who is the Moon King?” | Abstaining answer; “No grounded objects returned”; no entity/relationship rows |
| 5 | Stop terminal A (API); Ask again | Network unavailable / error state; prior answer only under Prior result (stale), never styled as current success |
| 6 | Console | No uncaught exceptions; no requests outside `127.0.0.1:8000` and the static origin |

Changed-body request-ID conflict is covered by automated integration tests; do
not add a product-like browser control solely for that case.

## 6. Record handback evidence

Capture locally (do not commit unless the repository explicitly permits):

* screenshot: grounded success
* screenshot: exact replay matched
* screenshot: Moon King abstention
* screenshot: API unavailable / error
* note browser name/version, OS, and the exact commands used

Optional CORS header spot-check:

```bash
curl -sS -D - -o /dev/null \
  -H "Origin: http://127.0.0.1:8081" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://127.0.0.1:8000/v1/mind-turn

curl -sS -D - -o /dev/null \
  -H "Origin: http://127.0.0.1:9999" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://127.0.0.1:8000/v1/mind-turn
```

Allowed origin must receive `Access-Control-Allow-Origin: http://127.0.0.1:8081`.
Disallowed origin must not.

## 7. Stop

```bash
# Ctrl+C static server and uvicorn
docker compose -f compose.postgres.yml down
```

## Still false after this proof

* LandingPage or other product-surface adoption
* production authentication
* source opening (`open_source`)
* Hermes / network model providers
* graph writes
* multi-worker exactly-once adapter execution
* production deployment
