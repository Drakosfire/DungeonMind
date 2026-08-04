# Runbook — B.2f-d finalized-review publication service

This service is a narrow service-to-service/operator transport for an already
finalized review. It is separate from the read-only Mind Turn host and is not a
browser or product API.

## Configuration

Required:

```text
DUNGEONMIND_DATABASE_URL
DUNGEONMIND_PUBLICATION_WORLD_ID
DUNGEONMIND_PUBLICATION_BEARER_TOKEN
```

Optional semantic profile configuration remains:

```text
DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH
```

The bearer token is a one-world shared-secret access binding, not production
user authentication and not a second GM confirmation. Keep it in the
operator's environment or secret manager. It is never part of a request body,
checked-in fixture, command-line argument, log, or response.

## Start

Install the optional service dependencies and run the factory:

```bash
uv sync --locked --extra postgres --extra api
uv run uvicorn dungeonmind.service.bootstrap:create_publication_service_app \
  --factory \
  --host 127.0.0.1 \
  --port 8001
```

The app exposes exactly `/healthz`, `/readyz`, and
`/v1/finalized-review-publications`. It has no CORS middleware.

## Check readiness

```bash
curl --fail http://127.0.0.1:8001/healthz
curl --fail http://127.0.0.1:8001/readyz
```

Readiness means the database connection and required publication tables are
visible for the configured world. It does not mean that a particular review is
present, materializable, publishable, or current at the graph head.

## Publish or retry

The caller sends only the exact versioned identity request:

```bash
export DUNGEONMIND_PUBLICATION_BEARER_TOKEN='local-secret-from-operator'
uv run python examples/finalized_review_publication_client/client.py \
  --base-url http://127.0.0.1:8001 \
  --world-id world:synthetic-gatewatch \
  --review-id review:cff0162637b428e634e8cccaa9958dc2 \
  --verify-replay
```

The response is the terminal `dm_finalized_review_publication_v1` record.
Retry the identical body after a 503 outcome-unknown response. Do not change
the timestamp, add graph fields, rebase, force, inspect the head, or create a
second confirmation. A successful replay preserves the original
`published_at`, even after descendants or explicit rollback.

## Failure handling

| HTTP | Meaning | Operator action |
| ---: | --- | --- |
| 403 | bearer/world binding denied | verify the configured secret and exact world |
| 404 | durable review or pinned parent unavailable | inspect the exact durable identifiers |
| 409 | stale parent, conflicting identity, or materialization failure | do not rebase; resolve the durable review/graph condition |
| 503 | persistence unavailable or outcome unknown | retry the identical request; outcome-unknown explicitly has `retry_safe=true` |
| 500 | stored authority integrity failure or sanitized internal error | stop and investigate persistence/service logs without exposing secrets |

The service never infers success from `world_graph_heads`. Only the exact
durable publication record proves a completed publication.

## Scope reminders

There is no review creation/edit/finalization API, GET publication polling,
pending lifecycle, attempt row, queue, worker, scheduler, product adoption,
browser write surface, CORS policy, identity-ledger append, or mechanics
binding in B.2f-d. DungeonMindBuddy adoption is a separate successor.
