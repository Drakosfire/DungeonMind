# HANDOFF — FT1b Exact-revision Fictional-time Shadow Query Transport

**Created:** 2026-08-04  
**Status:** ACTIVE  
**Canonical path:** `Docs/Handoffs/HANDOFF-ft1b-fictional-time-shadow-query-transport.md`  
**Flow:** TIMELINE  
**Repository:** Drakosfire/DungeonMind  
**Branch:** `timeline/ft1b-fictional-time-shadow-query-transport`  
**PR title:** `TIMELINE: serve exact-revision fictional-time shadow queries`  
**Base:** `52a683755b9af0a8b54b65018fa64cd9c2b91f96` (PR #18 merge)  
**Predecessor:** PR #18 (FT1a). **Concurrent:** PR #17 owns only `src/dungeonmind_dnd/**`.  
**Successor:** FT1c Buddy client + operator diagnostic. Not FT2.

## 0. Mission

Bearer-gated read-only HTTP host that loads one exact stored graph revision and delegates unchanged to FT1a `evaluate_fictional_time_query`. Shadow authority only. No head read, persistence of request/bundle/result, CORS, providers, Buddy, UI, Hermes, or temporal canon.

**Invariant:** valid `dm_fictional_time_shadow_query_request_v1` + Bearer + one-world access binding + `WorldGraphRepository` + matching `GraphSnapshotReader` → authorize before repo → reload request (`exclude_unset=True`) → `get_revision(world_id, graph_revision_id)` exactly → never `get_head` → 404 if absent → FT1a evaluate → `dm_fictional_time_query_result_v1` with `Cache-Control: no-store` → sanitized typed errors only.

## 1. Allowlist (exactly 13 paths)

**Create:** this handoff; `contracts/fictional_time_transport.py`; `application/fictional_time_query_service.py`; `service/fictional_time_access.py`; `tests/unit/test_fictional_time_{transport,query_service,api}.py`; `tests/integration/test_postgres_fictional_time_query.py`.

**Modify:** `contracts/__init__.py`; `application/__init__.py`; `service/api.py`; `service/bootstrap.py`; `service/error_mapping.py`.

**Forbidden:** FT1a contracts/evaluator/fixtures/conformance; migrations; `dungeonmind_dnd/**`; Mind Turn / publication semantics changes; Buddy; architecture docs.

## 2. Line ceilings

| Path | Ceiling |
|------|---------|
| `fictional_time_transport.py` | 140 nonblank |
| `fictional_time_query_service.py` | 130 |
| `fictional_time_access.py` | 110 |
| Net new in `api.py` | 190 |
| Net new in `bootstrap.py` | 150 |
| Net new in `error_mapping.py` | 45 |
| Each unit test module | 375 |
| Postgres integration test | 275 |

## 3. Contract

`FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA = "dm_fictional_time_shadow_query_request_v1"`

`FictionalTimeShadowQueryRequest`: `schema_version`, `world_id`, `graph_revision_id`, `claim_bundle`, `query`. Nonblank world/revision; world/revision equal nested bundle; shadow via FT1a; `extra=forbid`. Reload with `exclude_unset=True`.

Response: existing `FictionalTimeQueryResult` unchanged.

## 4. Application / access / API

- `query_fictional_time_shadow_at_revision(request, *, world_graph_repository, graph_reader)` — reload → `get_revision` → missing → `RevisionNotFoundError` → else FT1a evaluate.
- `FictionalTimeQueryAccessBinding` / `authorize_fictional_time_query_request` — mirror publication access (digest-only, redacted repr, hmac.compare_digest, world match, deep copy). Reason `fictional_time_query_access_denied`.
- `create_fictional_time_query_app` — `/healthz`, `/readyz`, `POST /v1/fictional-time-shadow-queries`; no CORS; no-store; sanitized handlers.
- Env: `DUNGEONMIND_DATABASE_URL`, `DUNGEONMIND_FICTIONAL_TIME_WORLD_ID`, `DUNGEONMIND_FICTIONAL_TIME_BEARER_TOKEN`.
- Uvicorn factory: `create_fictional_time_query_service_app`.
- Readiness: DB + `graph_revisions` table readable; no head required.

## 5. Error matrix

| Condition | HTTP | Code |
|-----------|------|------|
| Access denied | 403 | capability_denied |
| Validation | 422 | request_validation_error |
| Missing revision | 404 | revision_not_found |
| FT integrity | 409 | fictional_time_integrity_error |
| Persistence unavailable | 503 | persistence_unavailable |
| Persistence integrity | 500 | persistence_integrity_error |
| Unexpected | 500 | internal_error |

Allowed integrity details: `reason`, sanitized `object_id`, opaque `world_id`/`revision_id` for missing revision.

## 6. Evidence (E1–E14)

See dispatch brief: transport strictness; auth-before-read; exact get_revision/no head; missing 404; four gold HTTP; forgery/reload 409; sentinel sanitization; validation/500; no-store/replay; head-independent readiness; static no-head guard; R1 after R2 head move; Postgres restart; ruff/pyright/import/conformance/non-integration/scope.

## 7. Nano-commits

1. `feat(timeline): add fictional-time shadow transport contract`  
2. `feat(timeline): load exact revision for shadow query`  
3. `feat(timeline): add bearer-gated shadow query host`  
4. `test(timeline): prove pinned transport and fail-closed errors`  
5. `docs: complete FT1b implementation handback only if repository practice requires it`

## 8. Completed implementation handback

**PR / branch / head:** open on `timeline/ft1b-fictional-time-shadow-query-transport` (use PR head SHA; do not treat this line as a frozen tip).  
**Exact base SHA (PR #18 merge):** `52a683755b9af0a8b54b65018fa64cd9c2b91f96`

**Mission / invariant:** Bearer-authorized exact `get_revision` + unchanged FT1a evaluation over a separate no-store host; no head, persistence, CORS, or product adoption.

**Changed paths (exact §4 list):** 13 allowlisted paths only.

**Request schema and route:** `dm_fictional_time_shadow_query_request_v1` via `POST /v1/fictional-time-shadow-queries` on `create_fictional_time_query_app`.

**Authorization binding:** `FictionalTimeQueryAccessBinding` (digest-only, redacted repr, hmac.compare_digest, world match before repository access).

**Exact repository read proof:** unit spy rejects `get_head`/`publish`/`rollback`; service calls `get_revision` once.

**Four gold HTTP results:** entailed tree→beetles; unresolved absolute; Lysandra before/after gate (false/true); `authority_mode=shadow`.

**Error/status matrix:** 403/422/404/409/500/503 as specified; validation strips input/ctx/url.

**Head-movement result:** memory R1 query byte-equivalent after R2 head advance.

**PostgreSQL restart result:** integration test present; skipped locally without `DUNGEONMIND_DATABASE_URL` (CI integration job required).

**No-store / no-persistence proof:** `Cache-Control: no-store`; identical POST bodies byte-equivalent; no request/result store.

**E1–E14:** focused unit green; FT1a conformance green; full non-integration green; ruff/pyright/import green; integration pending CI/DSN.

**Nano-commit story:** contract → application service → bearer host → tests → handback.

**Nonblank line counts / net additions:** all under §2 ceilings.

**Baseline failures or waivers:** none locally; Postgres integration not executed without DSN.

**Stop conditions encountered:** none.

**Named retained paths and remaining consumers:** FT1a evaluator unchanged; FT1c Buddy client next.

**Disposition:** `FT1B_READY_FOR_BUDDY_SHADOW_CLIENT`
