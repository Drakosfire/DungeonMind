# HANDOFF — B.2f-d finalized-review publication service transport

**Created:** 2026-08-04  
**Status:** IMPLEMENTED — local verification complete; awaiting review  
**Repository:** `Drakosfire/DungeonMind`  
**Branch:** `founding/pr-b2f-d-finalized-review-publication-service-transport`  
**Base SHA:** `71156b630a4370039dc749b548eb43828cce0e6d`  
**Predecessor:** merged PR #14 — B.2f-c durable publication identity and recovery  
**Decision:** [`ADR-0012`](../Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md)  
**Runbook:** [`RUNBOOK-b2f-d`](../Runbooks/RUNBOOK-b2f-d-finalized-review-publication-service.md)

## Delivered boundary

B.2f-d adds a separate FastAPI publication app with:

```text
GET  /healthz
GET  /readyz
POST /v1/finalized-review-publications
```

The request is exactly `dm_finalized_review_publication_request_v1` and contains
only `world_id` and `review_id`. The response is the existing terminal
`dm_finalized_review_publication_v1` record. The server owns the UTC timestamp,
the bearer digest is bound to one configured world, and the route delegates to
B.2f-c without reading the head, materializing a graph, retrying, or adding
transport state.

The dependency-free client lives under
`examples/finalized_review_publication_client/` and supports exact canonical
replay verification.

## Changed paths

```text
src/dungeonmind/contracts/review_publication_transport.py
src/dungeonmind/contracts/__init__.py
src/dungeonmind/service/publication_access.py
src/dungeonmind/service/__init__.py
src/dungeonmind/service/api.py
src/dungeonmind/service/bootstrap.py
src/dungeonmind/service/error_mapping.py
examples/finalized_review_publication_client/README.md
examples/finalized_review_publication_client/client.py
examples/finalized_review_publication_client/request.json
tests/unit/test_review_publication_transport_contract.py
tests/unit/test_publication_access.py
tests/unit/test_publication_error_mapping.py
tests/unit/test_finalized_review_publication_client.py
tests/integration/test_finalized_review_publication_api.py
Docs/Decisions/ADR-0012-b2f-d-finalized-review-publication-service-transport.md
Docs/Runbooks/RUNBOOK-b2f-d-finalized-review-publication-service.md
Docs/Handoffs/HANDOFF-b2f-d-finalized-review-publication-service-transport.md
Docs/Architecture/ARCHITECTURE.md
Docs/Architecture/AUTHORITY.md
Docs/Roadmaps/ROADMAP.md
README.md
```

Paths outside the allowlist: none intended.

## Explicit boundary audit

- Forbidden B.2f-c files changed: no.
- Migrations, lockfile, dependency, repository protocol, and adapter changes: no.
- Publication app CORS middleware: none.
- Caller-supplied timestamp, operation ID, expected parent, graph payload, or
  second confirmation: none.
- Review API, pending lifecycle, polling endpoint, product adoption, browser
  write surface, and mechanics binding: none.
- Current head used as publication success evidence: no.

## Contract and fixture

```text
Request:  dm_finalized_review_publication_request_v1
Response: dm_finalized_review_publication_v1
World:    world:synthetic-gatewatch
Review:   review:cff0162637b428e634e8cccaa9958dc2
Revision: rev:6e02bd224f6b5616534f10026c8b9679
Primary publication SHA-256:
          3e7a632142c41066d3866c8682290fdc8e57b8f08b3324689c2964f6b045958c
```

## Verification status at handoff

```text
Focused transport unit tests: passed (47)
Core suite: passed (605)
PostgreSQL/API integration suite: passed (123)
Live-loopback client: passed in the PostgreSQL/API integration suite
Locked dependency sync: blocked by the host sandbox mount-limit error; no
dependency or lockfile changes were made
CI run ID and job conclusions: pending
PR number: pending
Final head SHA: 71156b630a4370039dc749b548eb43828cce0e6d (working tree changes; no commit created)
```

The integration file contains proofs for fresh publication, exact replay,
same-review app convergence, different-review CAS competition, response-loss
recovery, retry-safe unknown outcome, descendant/rollback replay, access
denial, strict validation, readiness, OpenAPI, no CORS, and real loopback client
execution. Run them with the PostgreSQL service available.

## Required handback facts

```text
New endpoint:
  POST /v1/finalized-review-publications
Environment:
  DUNGEONMIND_DATABASE_URL
  DUNGEONMIND_PUBLICATION_WORLD_ID
  DUNGEONMIND_PUBLICATION_BEARER_TOKEN
  DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH (optional)
Request schema:  dm_finalized_review_publication_request_v1
Response schema: dm_finalized_review_publication_v1
Exact primary response SHA-256:
  3e7a632142c41066d3866c8682290fdc8e57b8f08b3324689c2964f6b045958c
Publication app CORS middleware: none
Bearer token in captured output: no
Fresh/replay JSON equality: proven
Two app instances converge on one record: proven
Descendant/rollback replay preserves head: proven
Loopback client imports dungeonmind: no
Core suite: 605 passed
PostgreSQL/API integration: 123 passed
CI run ID and conclusions: pending
PR number: pending
```

## Still false

Pending publication lifecycle, attempts, queues, workers, leases, schedulers,
automatic retries, GET polling, review creation/edit/finalization transport,
identity-decision append, product/browser adoption, production OAuth/OIDC,
generic multi-tenant authorization, DungeonMindBuddy code, and Threat
mechanics/resource binding remain outside this slice.
