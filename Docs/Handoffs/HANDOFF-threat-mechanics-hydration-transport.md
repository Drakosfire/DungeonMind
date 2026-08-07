# HANDOFF — Serve exact-revision Threat mechanics hydration

Created: 2026-08-05  
Status: ACTIVE — dispatch exactly one implementation capability.  
Flow / agent: STATBLOCK  
Design agent: DungeonBuddy / GPT-5.6 Thinking  
Code agent: STATBLOCK  
Repository: Drakosfire/DungeonMind  
Branch: statblock/threat-mechanics-hydration-transport  
PR title: STATBLOCK: serve exact-revision Threat mechanics hydration

This handoff is the implementation authority. The PR description is only a
transport pointer; it cannot replace this handoff, the code diff, nano-commit
story, exact fixture hashes, or verification evidence.

## §1 Mission and merge-ready invariant

Deliver exactly one independently useful capability: an authorized external GM
service can hydrate one exact D&D Threat mechanics resource from one exact
published World Graph revision so DungeonMindBuddy can consume verified
statblock bytes without copying mechanics into graph truth or inferring the
current head.

For one bearer-authorized world, one strict request containing an exact graph
revision ID, exact graph object ID, and complete pinned mechanics-resource ref
must cause exactly one exact-revision repository read, server-owned GM
admissibility, B.3a graph/binding verification, and at most one resolver call.
Success returns the existing byte-equivalent digest-verified hydration with
`Cache-Control: no-store`. Authorization, revision, graph, object, Threat,
resource, provider, and digest mismatches fail closed before any later
authority boundary. There is no current-head lookup, retry, fallback,
persistence, graph mutation, credential leak, provider-locator leak, or
mechanics copy into the graph.

## §2 Authority and boundaries

The required predecessor is merged B.3a:

- `DndMechanicsResourceRef`
- `DndMechanicsResourceEnvelope`
- `DndThreatMechanicsBinding`
- `DndThreatMechanicsHydration`
- `DndMechanicsResourceResolver`
- `derive_threat_mechanics_binding`
- `hydrate_threat_mechanics`

B.3a schemas, identity grammar, content addressing, hashes, fixtures, and
hydration semantics are immutable in this slice. Transport owns only bearer
access, exact-revision loading, route/error mapping, and response headers.

The caller supplies:

```text
world_id + graph_revision_id + object_id + complete DndMechanicsResourceRef
```

The server supplies `Admissibility.GM`. The route never accepts caller
admissibility, visibility, binding, relationship IDs, graph payload digests,
semantic profile, Threat vocabulary, mechanics payload, current-head/latest
selectors, locators, or credentials in the body.

The exact repository operation is:

```text
get_revision(world_id, graph_revision_id)
```

It is called exactly once. `get_head`, history scans, latest/current inference,
publish, append, save, retries, fallback resolvers, cache lookup, discovery,
and persistence are forbidden.

## §3 Public route and observable paths

The separate FastAPI host exposes exactly:

```text
GET  /healthz
GET  /readyz
POST /v1/dnd/threat-mechanics-hydrations
```

The POST route:

1. verifies the bearer before parsing the body or touching dependencies;
2. validates the strict request;
3. binds the validated world to the configured bearer world;
4. performs one exact repository read;
5. calls B.3a derive and hydrate unchanged;
6. returns `DndThreatMechanicsHydration` normally with `200` and `no-store`.

Unauthorized or malformed-body ordering is observable: an invalid bearer with
malformed JSON returns `401`, `WWW-Authenticate: Bearer`, and zero body-parser,
repository, reader, or resolver calls. A valid bearer with malformed JSON
returns sanitized `422`. A valid bearer for the wrong world returns `403`
before repository access.

Stable route outcomes:

| Condition | HTTP | Code |
| --- | ---: | --- |
| Missing, malformed, or unknown bearer | 401 | `capability_denied` |
| Valid bearer, wrong world | 403 | `capability_denied` |
| Invalid request JSON/schema | 422 | `request_validation_error` |
| Exact revision absent | 404 | `graph_revision_not_found` |
| Graph repository unavailable | 503 | `graph_repository_unavailable` |
| Revision/graph/profile/object/Threat/binding mismatch | 409 | `threat_mechanics_binding_invalid` |
| Resource absent | 404 | `mechanics_resource_not_found` |
| Resolver exception | 503 | `mechanics_resource_unavailable` |
| Resource ref/envelope/digest mismatch | 502 | `mechanics_resource_integrity_failure` |
| Unexpected internal defect | 500 | `internal_error` |

All errors use the existing `{ "error": { "code", "message", "details" } }`
shape. No raw exception, rejected input, graph prose, evidence locator,
mechanics bytes, credential, provider URL, local path, database detail, or
token may appear in body, repr, traceback, or captured logs.

`/healthz` is liveness only. `/readyz` uses an infrastructure-only readiness
callback and never reads a head, revision, graph payload, or resource.
No CORS middleware or browser surface is added.

## §4 Exact request contract

Schema:

```text
dmdnd_threat_mechanics_hydration_request_v1
```

```python
class DndThreatMechanicsHydrationRequest(DungeonMindModel):
    schema_version: Literal[
        "dmdnd_threat_mechanics_hydration_request_v1"
    ] = "dmdnd_threat_mechanics_hydration_request_v1"
    world_id: str
    graph_revision_id: str
    object_id: str
    resource_ref: DndMechanicsResourceRef
```

The contract is strict (`extra="forbid"`, hidden input errors), includes nested
schema-version defaults in normal `model_dump(mode="json")`, and uses no
exclusion flags for canonical serialization.

Canonical request:

```json
{
  "schema_version": "dmdnd_threat_mechanics_hydration_request_v1",
  "world_id": "world:synthetic-gatewatch",
  "graph_revision_id": "rev:6e02bd224f6b5616534f10026c8b9679",
  "object_id": "obj:48e170969a2bb3980e437f7430b7b1c1",
  "resource_ref": {
    "schema_version": "dmdnd_mechanics_resource_ref_v1",
    "ruleset_id": "dnd5e",
    "provider_id": "fixture.dungeonmind.statblocks",
    "resource_id": "statblock:tripod-null-calf",
    "resource_revision": "tripod-null-calf-v1",
    "resource_schema": "fixture_dnd5e_statblock_v1",
    "media_type": "application/json",
    "payload_sha256": "11e6e581606ffdd1091cf6d515c1fd4288772451a74ec14a979660acdeffd932"
  }
}
```

Canonical request SHA-256:

```text
a78a1648fae75937b5b775d6ef0d385ab620eace249a6b618334ab1868ae134e
```

## §5 Immutable predecessor fixture gates

The following values must remain unchanged:

```text
world_id:                 world:synthetic-gatewatch
published revision:       rev:6e02bd224f6b5616534f10026c8b9679
parent revision:          rev:f2d5164c176289c5f3df7e68b4f0e46d
operation:                reviewop:11111111111111111111111111111111
graph payload SHA-256:    75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5
Threat object:            obj:48e170969a2bb3980e437f7430b7b1c1
Threat relationship:      rel:7136b2aa4616bd0455f8fde084b5a1c0
resource payload SHA-256: 11e6e581606ffdd1091cf6d515c1fd4288772451a74ec14a979660acdeffd932
binding ID:               mechbind:872167afbc6e6a6b242c6d93036767ab
complete binding SHA:     82a6cc1b5df140013ff24cc6dc63721d5c421ee7d6e0c185b22d48d15879dddb
complete hydration SHA:   166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16
complete request SHA:     a78a1648fae75937b5b775d6ef0d385ab620eace249a6b618334ab1868ae134e
```

A fixture hash change is a stop condition, not a regeneration task.

## §6 Files in scope

Only these paths are authorized:

```text
Docs/Handoffs/HANDOFF-threat-mechanics-hydration-transport.md
src/dungeonmind_dnd/contracts/mechanics_transport.py
src/dungeonmind_dnd/contracts/__init__.py
src/dungeonmind_dnd/application/threat_mechanics_transport.py
src/dungeonmind_dnd/application/__init__.py
src/dungeonmind_dnd/integration/__init__.py
src/dungeonmind_dnd/integration/threat_mechanics_api.py
examples/dnd_threat_mechanics_request.json
examples/dnd_threat_mechanics_client.py
tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-mechanics-request-v1.json
tests/unit/test_dnd_threat_mechanics_transport_contract.py
tests/unit/test_dnd_threat_mechanics_transport_service.py
tests/unit/test_dnd_threat_mechanics_api.py
tests/unit/test_dnd_threat_mechanics_client.py
tests/integration/test_dnd_threat_mechanics_api.py
tests/unit/test_import_boundaries.py
```

One bounded discovery exception is permitted under `tests/integration/` for
one existing shared PostgreSQL seed helper only, and only when needed to seed
the existing exact B.2f published revision. No production path, migration,
generic fixture refactor, or unrelated cleanup is authorized.

## §7 Explicit non-goals

Do not change B.3a files or fixtures, kernel production code, repository
protocols, PostgreSQL adapters, migrations, lockfiles, existing service hosts,
roadmap, README, architecture, ADRs, Buddy code, provider adapters, provider
discovery, locators, credentials, retries, fallback, cache, fan-out, binding
registry, binding persistence, current-head mode, batch hydration, player
access, CORS, browser access, mechanics writes, graph mutation, combat state,
Timeline semantics, Hermes, Plan/Play rendering, observability stores,
deployment/IaC, or product adoption.

The named successor is a separate DungeonMindBuddy PR:

```text
STATBLOCK: shadow hydrate Tripod Null-Calf from DungeonMind
```

## §8 Required evidence

The implementation must prove:

- request model strictness and canonical SHA;
- authorization before body parsing and dependency access;
- one exact `get_revision` and no `get_head`;
- forged revision ID, parent, operation, payload digest/body, schema, world,
  profile, missing object, wrong kind, and non-Threat mutations fail before
  resolver access;
- resolver call count is zero before eligibility and one at most afterward;
- resource miss, resolver exception, wrong ref, wrong envelope, and wrong
  digest map to their stable codes without returned mechanics bytes;
- successful payload and dependency inputs are isolated;
- exact historical hydration survives a descendant/head advance;
- health/readiness/OpenAPI/CORS surface is narrow;
- root imports remain lightweight and kernel never imports `dungeonmind_dnd`;
- the standard-library client proves real loopback HTTP twice and exact replay;
- changed paths remain within this allowlist and no migration/lockfile changes
  occur.

Required command set:

```text
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import sys, dungeonmind; assert 'dungeonmind_dnd' not in sys.modules"
uv run --no-dev python -c "import sys, dungeonmind_dnd; assert 'fastapi' not in sys.modules; assert 'psycopg' not in sys.modules"
uv run pytest -q tests/unit/test_dnd_threat_mechanics_transport_contract.py
uv run pytest -q tests/unit/test_dnd_threat_mechanics_transport_service.py
uv run pytest -q tests/unit/test_dnd_threat_mechanics_api.py
uv run pytest -q tests/unit/test_dnd_threat_mechanics.py tests/unit/test_import_boundaries.py
uv run pytest -q -m "not integration"
uv sync --locked --extra postgres --extra api
uv run alembic heads
uv run alembic upgrade head
DUNGEONMIND_DATABASE_URL=<test-url> uv run pytest -q tests/integration/test_dnd_threat_mechanics_api.py
DUNGEONMIND_DATABASE_URL=<test-url> uv run pytest -q -m integration
uv build
git diff --check
```

The live proof must capture the loopback URL, redacted client output, response
headers, canonical response SHA, repository/read/head/reader/resolver counts,
and process exit codes. It must use one exact historical revision, advance the
head to a descendant, and repeat the old request successfully.

## §9 Required handback and disposition

The review handback must include the exact PR or branch/head SHA, the base SHA
or reanchor report, nano-commit list, changed paths and focused diff stat,
request and predecessor hashes, every command result with provenance,
adversarial call counts, HTTP status/code/header/OpenAPI/CORS results,
sanitization sentinels, baseline failures and waivers, stop conditions,
and confirmation that no out-of-scope capability was added.

Disposition:

```text
READY_FOR_BUDDY_THREAT_MECHANICS_SHADOW_CLIENT
```

The named Buddy shadow successor remains unimplemented and unclaimed.
