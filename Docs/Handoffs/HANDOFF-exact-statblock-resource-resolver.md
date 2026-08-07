# HANDOFF — Resolve exact DungeonMind statblock mechanics resources

Created: 2026-08-06  
Status: ACTIVE DESIGN — dispatch is blocked until predecessor PR #20 merges.  
Canonical handoff path: `Docs/Handoffs/HANDOFF-exact-statblock-resource-resolver.md`  
Conversation name: DungeonMind Exact Statblock Resource Resolver  
Flow / agent: STATBLOCK  
Handoff direction: DESIGN → CODE  
Design agent: DungeonBuddy / GPT-5.6 Thinking  
Code agent: STATBLOCK  
Repository: Drakosfire/DungeonMind  
Branch: statblock/dungeonmind-statblock-resource-resolver  
PR title: STATBLOCK: resolve exact statblock mechanics resources

Dispatch gate: Do not branch or change code until DungeonMind PR #20,
`STATBLOCK: serve exact-revision Threat mechanics hydration`, is merged. The
implementation PR must record the resulting immutable `origin/main` merge SHA
in its body before its first code commit. The reviewed PR #20 head
`32b949502b1d2a5492a2974e98362c3797eba369` and transient merge-result SHA are
predecessor evidence, not valid implementation bases.

This checked-in handoff is the complete implementation authority. The worker
must not compress, replace, or broaden it. The PR description is transport
metadata only; the handoff, cumulative diff, nano commits, and independently
rerun evidence are authoritative.

## Shared vocabulary

| Term | Definition |
| --- | --- |
| Mechanics resource ref | The existing B.3a `DndMechanicsResourceRef`: opaque provider/resource identity plus exact payload digest. It contains no URL, credential, graph prose, or mechanics bytes. |
| Provider exact-revision response | The existing DungeonMind statblock-v1 response carrying `statblock_id`, `revision_id`, `contract`, `contract_version`, `canonical_definition`, and `definition_digest`. |
| Observed envelope | The untrusted mapping constructed from fields actually returned by the provider. It is deliberately not repaired or pre-certified by the resolver; B.3a remains the authority that reloads and verifies it. |
| Unsupported ref | A valid generic B.3a ref that does not belong to this exact provider adapter or does not use the provider’s exact `sb_*` / `rev_*` identifier grammar. It produces a miss with zero HTTP calls. |
| Transport failure | Timeout, connection failure, redirect, oversized body, non-JSON body, or non-success provider status other than exact miss. It raises one sanitized resolver exception; PR #20 maps it to `mechanics_resource_unavailable`. |
| Provider disagreement | A 200 response whose observed identity, schema, digest, or canonical mechanics bytes disagree with the requested ref. The resolver preserves the disagreement in its raw mapping so B.3a classifies it as integrity failure. |
| No repair | No lowercasing, ID substitution, digest recomputation, fallback field, response-to-request overwrite, or “helpful” normalization may make an invalid provider response pass. |

## Agent flow and nano-commit contract

Use flow identifier STATBLOCK and keep the implementation in this order:

```text
feat(statblock): add exact statblock resource resolver contract

feat(statblock): resolve one exact provider revision without fallback

test(statblock): prove provider disagreement and transport boundaries

test(statblock): compose resolver through exact Threat hydration

docs(statblock): complete resolver handback
```

A commit may be split further when a review fix has one discrete purpose. Do not
combine unrelated cleanup, graph work, Buddy integration, bootstrap/deployment,
or documentation synchronization into these commits.

## Review and document-sync contract

The reviewer must identify the exact PR/branch/head SHA, exact PR #20 merge
base, and cumulative diff. Review the implementation against this handoff
rather than the PR description. Require as many discrete review cycles as
necessary.

Every finding must name:

- the failed invariant clause;
- the affected path and owning boundary;
- the exploit or incorrect observable outcome;
- the exact code or evidence needed to close it.

Architecture, roadmap, tracker, and status synchronization remain a separate
post-merge document operation. This PR checks in only its own implementation
handoff and handback.

## §1 Mission and merge-ready invariant

An authorized DungeonMind mechanics host can resolve one exact accepted
DungeonMind statblock revision so the existing B.3a/PR #20 hydration seam can
serve real content-addressed mechanics rather than fixture-only resources.

Merge-ready invariant: One supported `DndMechanicsResourceRef` causes at most
one bounded, authenticated, non-redirecting GET for its exact provider
resource and revision; the resolver returns only an unmodified observed
resource identity plus the provider’s canonical mechanics object, while
misses, transport failures, response disagreements, secrets, retries,
locators, current-head inference, and fallback remain closed under the
existing B.3a and PR #20 authority boundaries.

### Why this is the next slice

DungeonMind PR #20 creates the exact graph-revision hydration transport but
intentionally injects a caller-owned `DndMechanicsResourceResolver`; it does
not ship a real provider adapter. DungeonMindBuddy already owns an exact
statblock-v1 read client and exact Threat query/projection path, but its graph
and binding vocabulary is not the B.3a D&D profile:

| Buddy today | DungeonMind B.3a / PR #20 |
| --- | --- |
| `threat:*` object IDs | `obj:*` object IDs |
| `uses_statblock` binding edge | `dnd5e` profile + `threatens` eligibility |
| `sb_*` / `rev_*` statblock locator | `DndMechanicsResourceRef` |
| `sha256:<hex>` definition digest | 64-lowercase-hex `payload_sha256` |

A direct Buddy shadow client now would require a second mapping registry or
silent identity translation. That would violate the architecture rather than
prove it. This slice closes the smaller missing provider seam first. The graph
identity/profile bridge remains the named successor.

### Pre-dispatch critique

| Question | Answer |
| --- | --- |
| Can one invariant govern every claimed observable path? | Yes. Every path is one exact resolver call or a closed result before/later authority. There is no persistence, UI, graph write, or retry state. |
| What adversarial sequence is most likely to falsify it? | Valid requested ref → provider returns 200 with a different statblock/revision or digest → adapter overwrites observed fields with requested fields or recomputes a matching digest → B.3a accepts wrong mechanics. |
| Would §7 detect that failure? | Yes. Loopback responses mutate identity, contract version, digest, and canonical bytes independently; the tests require the raw disagreement to survive into B.3a and produce `mechanics_resource_integrity_failure`, with one provider call and no successful hydration. |
| Which owning boundary is easiest to under-test? | Exception sanitization. `httpx` exceptions retain request objects and authentication headers, so tests must inspect exception text, repr, details, cause, context, and captured logs. |
| What fact would force this slice to stop or split? | If parsing the provider’s checked-in `canonical_definition` and hashing it with DungeonMind canonical JSON does not reproduce the stripped provider `definition_digest`, or if correct error classification requires changing B.3a/PR #20 public semantics. |

## §2 Context, authority, and boundaries

| Field | Required content |
| --- | --- |
| Parent authority | `ARCHITECTURE-campaign-supergraph.md`: mechanics stay outside graph truth; exact consumers pin exact identity; surfaces do not invent storage or graph authority. |
| Workstream authority | DungeonMind B.3 roadmap lane: external mechanics resource identity remains distinct from graph identity and hydration. |
| Repository rules | Core import remains light; optional HTTP dependencies do not load from `import dungeonmind` or `import dungeonmind_dnd`; no lockfile or migration change. |
| Base revision | The immutable merge SHA produced when PR #20 merges. Record it before implementation. |
| Predecessor contract | PR #20 exact hydration request/transport plus B.3a `DndMechanicsResourceRef`, `DndMechanicsResourceEnvelope`, `DndMechanicsResourceResolver`, and `DndThreatMechanicsHydration`. |
| Provider grounding source | DungeonMindBuddy commit `d50d0c3a45761376185d36fb39ae3a098a5b8cfc`, exact response fixture `tests/fixtures/statblocks/v1/exact-revision-response.json`, existing statblock-v1 client/config/canonicalization. |
| Exact input consumed | One validated B.3a `DndMechanicsResourceRef`. |
| Exact provider operation | `GET /api/internal/dungeonbuddy/v1/statblocks/{resource_id}/revisions/{resource_revision}` with `X-DungeonBuddy-Internal-Key`. |
| Named successor | `STATBLOCK: adapt published Buddy Threat identity into DungeonMind D&D profile`. |
| Later consumer | `STATBLOCK: shadow verify Buddy Threat hydration through DungeonMind`, blocked on the identity/profile bridge. |
| What remains false | No Buddy request is emitted; no Buddy graph revision is transformed; no user-visible result changes; no executable production host is bootstrapped; no resolver is selected by discovery. |

### Explicit non-goals

UI, Hermes, Plan/Play/Build changes, graph writes, provider discovery,
retries, caching, binding persistence, current-head mode, batch reads,
deployment, IaC, metrics store, resource registry, generic ruleset support.

### Required reading order

Read these inputs in order before implementation:

1. Checked-in PR #20 handoff and merged PR #20 implementation.
2. `src/dungeonmind_dnd/contracts/mechanics_resources.py`.
3. `src/dungeonmind_dnd/application/threat_mechanics.py` and PR #20 transport.
4. DungeonMindBuddy exact provider fixture at commit `d50d0c3...`.
5. DungeonMindBuddy statblock client/config/canonicalization at that same commit.
6. Existing DungeonMind import-boundary and B.3a/PR #20 tests.

Stop before code if the merged PR #20 contract differs from the reviewed
head, the exact provider fixture has changed materially, or any required
behavior would need a second public endpoint or a graph-identity mapping.

## §3 Observable-path and adversarial-sequence inventory

| Path | Current behavior | Required behavior | Same invariant? | Owning boundary |
| --- | --- | --- | --- | --- |
| Supported exact ref, valid provider response | PR #20 requires an injected fixture/custom resolver. | One exact authenticated GET returns one raw B.3a envelope mapping whose mechanics are parsed from provider `canonical_definition`; B.3a verifies identity and digest. | Yes | Concrete resolver + B.3a reload |
| Unsupported provider/schema/ID grammar | No concrete adapter. | Return `None`; zero HTTP calls; no fallback adapter or path inference. | Yes | Resolver admission |
| Provider exact miss (404 or 410) | No concrete adapter. | Return `None` after exactly one GET. | Yes | Resolver status mapping |
| Provider 200 with wrong resource identity | No concrete adapter. | Preserve observed wrong identity; B.3a rejects as integrity failure. Never overwrite with requested identity. | Yes | Response mapping + B.3a |
| Provider 200 with wrong contract/version | No concrete adapter. | Derive observed resource schema from observed contract/version; mismatch remains visible to B.3a. | Yes | Response mapping + B.3a |
| Provider 200 with wrong digest/canonical bytes | No concrete adapter. | Preserve observed digest and parsed canonical bytes; B.3a rejects digest disagreement. Never recompute a digest into the ref. | Yes | Response mapping + B.3a |
| Timeout/connection failure | No concrete adapter. | One sanitized resolver exception; no retry; no raw URL, header, token, body, request object, cause, or context. | Yes | HTTP resolver |
| Redirect | No concrete adapter. | Refuse the redirect and raise one sanitized failure. Never follow it. | Yes | HTTP resolver |
| Oversized response | No concrete adapter. | Stop reading beyond one MiB and raise one sanitized failure. | Yes | Bounded-body reader |
| Non-JSON/non-object provider body | No concrete adapter. | Sanitized resolver failure; body is never echoed. | Yes | Response decoder |
| Repeat exact resolution | No concrete adapter. | Each call independently performs at most one GET; no cache or implicit replay state. | Yes | Resolver |
| PR #20 composition | Fixture resolver only. | Existing exact hydration route succeeds with the concrete resolver and remains no-store, exact-revision, and one-call. | Yes | PR #20 app/service integration |
| Operator configuration | No resolver configuration. | Strict existing-statblock env names or explicitly injected config; secret redacted; invalid config fails before HTTP. | Yes | Config loader |

### Ordered adversarial sequences

| Sequence | Required safe outcome | Owning proof |
| --- | --- | --- |
| Request exact A → provider returns exact B with 200 | Observed B is not repaired to A; PR #20 returns integrity failure; one provider call. | E7 |
| Request digest A → provider returns payload B but claims digest A | B.3a recomputes payload digest and rejects; no successful hydration. | E8 |
| Request A → provider returns payload A but digest B | B.3a rejects; resolver does not substitute request digest. | E8 |
| Provider returns contract 1.0.1 under otherwise matching IDs | Observed schema differs from requested schema; integrity failure. | E7 |
| Provider responds 302 to credential-bearing request | Redirect is not followed; token is absent from all public/diagnostic values. | E5 |
| First transport attempt times out | Exactly one attempt; sanitized unavailable result; no retry or fallback. | E5 |
| Response declares/streams >1 MiB | Reader aborts; no partial envelope; sanitized unavailable failure. | E6 |
| Unsupported generic ref contains colon/path-like provider resource identity | Adapter performs zero HTTP and returns miss; no URL construction from unsupported identifiers. | E3 |
| Same exact request sent twice through PR #20 | Two independent provider GETs, two byte-equivalent hydration bodies, zero cache/head reads. | E10 |
| Import package without api extra | Root packages import; `httpx` is absent from loaded modules. | E11 |

## §4 Files in scope (exact allowlist)

| Action | Path | Purpose |
| --- | --- | --- |
| Create | `Docs/Handoffs/HANDOFF-exact-statblock-resource-resolver.md` | Implementation authority and handback. |
| Create | `src/dungeonmind_dnd/integration/statblock_resource_resolver.py` | Strict config, exact provider adapter, bounded HTTP, raw observed-envelope mapping, and sanitized private error. |
| Modify | `src/dungeonmind_dnd/integration/__init__.py` | Documentation-only or type-only export only when it does not eagerly import `httpx`; prefer leaving runtime imports lazy. |
| Create | `tests/fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json` | Byte-faithful captured provider response copied from DungeonMindBuddy commit `d50d0c3...`; no vocabulary rewrite. |
| Create | `tests/unit/test_dnd_statblock_resource_resolver.py` | Config, admission, exact mapping, status, no-retry, sanitization, redirect, and bounded-body proofs. |
| Create | `tests/integration/test_dnd_statblock_resource_resolver.py` | Real loopback HTTP composition through B.3a/PR #20 using the captured provider response. |
| Modify | `tests/unit/test_import_boundaries.py` | Permit only the concrete integration module’s optional `httpx` dependency and prove root imports remain light. |

### Bounded discovery exception

Directory: `tests/`  
Maximum additional paths: 1  
Allowed path kinds: existing shared HTTP-loopback test helper only

Decision rule: include only when an already-present helper removes duplicated
server lifecycle code without changing its behavior; record the exact path and
reason in the PR before changing it. No production path, fixture framework,
`pyproject`, lockfile, CI workflow, or unrelated test cleanup qualifies.

Any other path is a stop condition. Do not silently export the resolver from a
root package, alter PR #20/B.3a code, or add bootstrap/deployment files.

## §5 Files and capabilities explicitly out of scope

| Path, layer, or capability | Why excluded |
| --- | --- |
| `src/dungeonmind_dnd/contracts/mechanics_resources.py` | B.3a resource identity and resolver protocol are predecessor authority. A required change means stop/split. |
| `src/dungeonmind_dnd/application/threat_mechanics.py` | B.3a binding/hydration semantics must remain unchanged. |
| PR #20 request/service/API files | This adapter must compose through the merged seam without changing its route or error contract. |
| `src/dungeonmind/**` kernel | Provider-specific HTTP belongs in the D&D integration package, never generic kernel authority. |
| `pyproject.toml`, `uv.lock` | `httpx` already belongs to the existing optional api dependency group. New dependency or lock drift is a stop. |
| PostgreSQL adapters/migrations | Resource resolution is external read-only I/O; it has no durable state. |
| Provider registry/discovery | One exact adapter is the capability. Generic fan-out is a separate contract. |
| Retry, fallback, circuit breaker, cache | They introduce state and ambiguity not governed by this invariant. |
| Host bootstrap/env-to-app factory | Production composition/deployment is a separate independently useful capability. |
| DungeonMindBuddy code | No consumer or cross-repository change in this PR. |
| Buddy graph/profile identity mapping | The immediate named successor; required before an honest shadow client. |
| User-visible statblock UI or Hermes output | Buddy already owns those surfaces; this PR cannot create a parallel presentation path. |
| Graph writes, binding registry, binding persistence | Mechanics remain external and non-durable in this lane. |
| Validation-receipt recertification | The resolver extracts the provider’s canonical mechanics payload; B.3a verifies exact payload identity. It does not recreate statblock acceptance policy. |

### Demolition declaration

Replaced path: none — no concrete DungeonMind D&D statblock resource resolver
exists.  
Deleted in this PR: no  
Retained reason: existing B.3a protocol and PR #20 injected-resolver seam
remain authority.  
Named remaining consumer: PR #20 app/service composition.  
Required deletion owner: future adoption PR only if a duplicate concrete
resolver is later discovered.

## §6 Implementation contract and conditional matrices

### 6.1 Input, output, and trust boundary

Input:

```text
DndMechanicsResourceRef
+ injected or strictly loaded provider config
+ optional injected httpx.Client for tests/composition
```

Output:

```text
None for unsupported/exact-miss
OR raw Mapping shaped as dmdnd_mechanics_resource_envelope_v1
OR sanitized DndStatblockResourceResolverError for transport/provider availability
```

Invariant: the resolver observes one exact provider resource; B.3a decides
whether that observation equals the requested content-addressed resource.

Failure behavior:

| Situation | Behavior |
| --- | --- |
| unsupported ref | `None`, zero HTTP |
| provider 404 / 410 | `None`, one HTTP |
| redirect / timeout / network | sanitized private resolver error, one HTTP |
| 401 / 403 / 408 / 409 / 422 / 429 / 5xx / unexpected status | sanitized private resolver error, one HTTP |
| oversized / non-JSON response | sanitized private resolver error, one HTTP |
| 200 identity/schema/digest drift | raw observed mapping; B.3a integrity failure |

Replay / idempotency:

- same input → a new independent exact GET; no local state or cache;
- changed input → a new independent admission decision and at most one exact GET;
- retry after failure → caller may invoke again; the resolver itself never retries.

Trust: the request ref is validated by the B.3a contract but still must match
this adapter’s provider/schema/media/ID grammar before URL construction.
Provider response is untrusted and is never repaired.

### 6.2 Concrete provider constants

```text
ruleset_id:       dnd5e
provider_id:      dungeonmind.statblocks
resource_schema:  dungeonmind.dungeonbuddy-statblocks.1.0.0
media_type:       application/json
resource_id:      ^sb_[a-z0-9]+$
resource_revision:^rev_[a-z0-9]+$
provider route:   /api/internal/dungeonbuddy/v1/statblocks/{resource_id}/revisions/{resource_revision}
auth header:      X-DungeonBuddy-Internal-Key
redirect policy:  follow_redirects=False
max body:         1,048,576 bytes
```

The resource schema is a deterministic lossless composition of the provider’s
observed contract and contract version:

```text
{contract}.{contract_version}
```

For the grounded v1 fixture this is exactly:

```text
dungeonmind.dungeonbuddy-statblocks.1.0.0
```

Do not lowercase, normalize, or repair observed contract/version values. A
provider response with different values must produce a different observed
schema and therefore fail B.3a equality.

### 6.3 Exact predecessor-to-consumer mapping

Grounding source: DungeonMindBuddy commit
`d50d0c3a45761376185d36fb39ae3a098a5b8cfc`, path
`tests/fixtures/statblocks/v1/exact-revision-response.json`.

Grounded fixture anchors:

```text
contract:          dungeonmind.dungeonbuddy-statblocks
contract_version:  1.0.0
statblock_id:      sb_000001
revision_id:       rev_000002
definition_digest: sha256:935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51
mechanics source:  canonical_definition (JSON string)
```

| Provider field/outcome | Real shape | B.3a observed field/behavior | Transformation | Required proof |
| --- | --- | --- | --- | --- |
| `statblock_id` | `sb_*` string | `resource_ref.resource_id` | Direct; no fallback to request | E4/E7 |
| `revision_id` | `rev_*` string | `resource_ref.resource_revision` | Direct; no fallback to request | E4/E7 |
| `contract` + `contract_version` | exact strings | `resource_ref.resource_schema` | `f"{contract}.{contract_version}"`; no normalization | E4/E7 |
| `definition_digest` | `sha256:<64 lower hex>` | `resource_ref.payload_sha256` | Strip only an exact leading `sha256:`; otherwise preserve invalid observed value | E4/E8 |
| `canonical_definition` | JSON string containing canonical mechanics object | `mechanics_payload` | Parse once with strict JSON; do not use `definition` as fallback | E4/E8 |
| `definition` | object | no consumer field | Ignored; not fallback authority | E4 source guard |
| `validation_receipt` | object | no consumer field | Ignored; no recertification claim | Diff review |
| 404, 410 | exact response status | resolver miss | Return `None` | E3 |
| redirect | 3xx | resolver unavailable | Refuse; no follow | E5 |
| other non-200 | status + possibly sensitive body | resolver unavailable | Stable private category/status only; never include body | E5 |

The exact expected ref for the captured fixture is:

```json
{
  "schema_version": "dmdnd_mechanics_resource_ref_v1",
  "ruleset_id": "dnd5e",
  "provider_id": "dungeonmind.statblocks",
  "resource_id": "sb_000001",
  "resource_revision": "rev_000002",
  "resource_schema": "dungeonmind.dungeonbuddy-statblocks.1.0.0",
  "media_type": "application/json",
  "payload_sha256": "935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51"
}
```

### 6.4 Observed-envelope rule

For a valid JSON-object 200 response, the resolver builds a raw mapping from
observed fields. It must not instantiate and thereby pre-certify
`DndMechanicsResourceEnvelope` before returning. The existing B.3a seam owns
reload and integrity classification.

Conceptual shape only:

```json
{
  "schema_version": "dmdnd_mechanics_resource_envelope_v1",
  "resource_ref": {
    "schema_version": "dmdnd_mechanics_resource_ref_v1",
    "ruleset_id": "dnd5e",
    "provider_id": "dungeonmind.statblocks",
    "resource_id": "observed statblock_id",
    "resource_revision": "observed revision_id",
    "resource_schema": "observed contract + \".\" + observed contract_version",
    "media_type": "application/json",
    "payload_sha256": "observed definition_digest after exact prefix strip"
  },
  "mechanics_payload": "parsed observed canonical_definition"
}
```

Rules:

- Never substitute requested ID, revision, schema, or digest into the observed response.
- Never calculate a new digest and place it in `resource_ref`.
- Never use `definition` when `canonical_definition` is missing or invalid.
- Never coerce a non-object canonical payload to an object.
- A valid JSON top-level response that lacks required fields may remain an invalid raw envelope for B.3a to reject; do not fabricate defaults.
- A non-JSON or non-object top-level HTTP response is a provider transport/contract failure and must not be echoed.

### 6.5 Configuration contract

Use a frozen, redacted config owned by the integration module. It may be
constructed explicitly and may provide an environment loader using the
existing statblock deployment names:

```text
DUNGEONMIND_STATBLOCKS_BASE_URL
DUNGEONMIND_STATBLOCKS_INTERNAL_API_KEY
DUNGEONMIND_STATBLOCKS_TIMEOUT_SECONDS
```

| Field | Rule |
| --- | --- |
| base URL | Required `http` or `https`, host required, no embedded username/password, no path, params, query, or fragment, normalized without trailing slash. |
| internal key | Required nonblank; never retained in repr beyond a redacted marker. |
| timeout | Finite positive number, maximum 120 seconds; default must match the grounded existing deployment contract unless an explicit injected config chooses another value. |
| max body | Fixed one MiB constant; not caller/environment configurable in this slice. |
| enabled flag | Do not add one. Construction is the explicit capability decision; absent/invalid config fails before HTTP. |

No config value may appear in public exception text, repr, details, traceback
chain, or captured logs. The base URL may remain in a redacted config repr only
because credentials are prohibited from it; provider paths and query details
must not appear in resolver exceptions.

### 6.6 HTTP and error contract

The private error may expose only stable non-secret fields such as:

```text
category: resolver_misconfigured | resolver_unavailable | resolver_response_invalid
status_code: optional integer
```

It must use a fixed public message. Raw provider bodies, URLs, request reprs,
header maps, exception strings, and tokens are forbidden.

Because `httpx` exceptions retain request objects, mapped errors must be raised
outside except blocks and with no chained cause/context. Evidence must assert:

```text
secret not in str(error)
secret not in repr(error)
secret not in serialized details
error.__cause__ is None
error.__context__ is None
secret not in captured logs
```

### 6.7 Identity and fallback matrix

| Situation | Required rule | Ambiguity behavior | Fallback permitted? |
| --- | --- | --- | --- |
| Exact supported ref | Match all fixed provider/schema/media fields and exact ID regexes before URL construction. | Not ambiguous. | No |
| Wrong provider ID | Return miss, zero HTTP. | No provider fan-out. | No |
| Wrong resource schema | Return miss, zero HTTP. | No version downgrade/upgrade. | No |
| Generic opaque resource ID not matching `sb_*` | Return miss, zero HTTP. | Do not reinterpret or URL-encode into provider path. | No |
| Generic opaque revision not matching `rev_*` | Return miss, zero HTTP. | Do not infer latest. | No |
| Provider returns different exact ID/revision | Preserve observed values; B.3a mismatch. | Never choose request or response as winner in adapter. | No |
| Provider returns different contract/version | Preserve observed composite schema; B.3a mismatch. | No version compatibility assumption. | No |
| Provider exact miss | Return `None`. | No list/search/name lookup. | No |
| Provider unavailable | Raise sanitized error. | No retry, alternate URL, stale cache, or fixture. | No |

### 6.8 Persistence and replay matrix

Not applicable as a durable-state matrix. The resolver writes no file,
database, cache, ledger, event, graph revision, binding, or request/result
record.

| Operation | Durable representation | Round-trip guarantee | Replay behavior | Compatibility | Rollback |
| --- | --- | --- | --- | --- | --- |
| Resolve | None | Returned mapping is isolated from mutable provider/client buffers. | Repeated call performs a new exact GET. | Exact v1 provider only. | Nothing to roll back. |

### 6.9 Dependency and import boundary

`httpx` already exists under DungeonMind’s optional `api` dependency. This PR
must not alter dependency metadata.

- `import dungeonmind` must not import `dungeonmind_dnd` or `httpx`.
- `import dungeonmind_dnd` must not import `httpx`.
- Importing `dungeonmind_dnd.integration.statblock_resource_resolver` requires
  the optional `api` environment and may import `httpx`.
- Core no-extra Pyright must remain green. Use the same narrow optional-import
  treatment accepted by PR #20 rather than excluding a package tree.
- Integration CI with `--extra api` must explicitly type-check the new module.

## §7 Evidence required to merge

| ID | Guarantee / invariant clause | Owning boundary | Evidence class | Command/scenario | Expected evidence | Stop condition |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Captured fixture is byte-faithful and uses real provider vocabulary. | Fixture/mapping test | Contract | Focused resolver unit test | Copied fixture’s parsed content equals source anchors; no renamed fields; handback records source commit/path and copied-file SHA. | Fixture was rewritten or fields invented. |
| E2 | Config is strict and secret-redacted. | Config loader/model | Adversarial | Focused unit test | URL/path/credential/query/NaN/zero/over-max rejected; repr and errors hide token. | Any secret or raw invalid value appears. |
| E3 | Unsupported refs and 404/410 are exact misses without fallback. | Resolver admission/status | Contract | Focused unit test | Unsupported ref: zero HTTP; 404/410: exactly one GET then `None`; no alternate call. | Any URL built for unsupported IDs or any fallback/list call. |
| E4 | Valid exact response maps observed provider fields and canonical mechanics exactly. | Response adapter | Contract | Captured-fixture test | Expected ref above; mechanics equal parsed `canonical_definition`; DungeonMind canonical SHA equals `935dc0...`; `definition` is not used. | Digest mismatch or adapter substitutes request/default fields. |
| E5 | Timeout/network/redirect/non-miss statuses are one-shot and sanitized. | HTTP resolver | Failure injection | Mock/loopback tests | One attempt; redirect not followed; fixed error; no secret/body/URL/cause/context/log leak. | Retry/follow/leak/chained request object. |
| E6 | Response body is bounded. | Stream reader | Adversarial | Mock declared and streamed oversize responses | Abort at/before 1 MiB + one chunk; no envelope; sanitized failure. | Full oversized body retained/read or partial success. |
| E7 | Wrong ID/revision/contract/version is not repaired. | Adapter + B.3a | Adversarial integration | Mutated 200 loopback responses through PR #20 service | `mechanics_resource_integrity_failure`; one provider call; no hydration bytes returned. | Successful hydration or unavailable classification caused by prevalidation/repair. |
| E8 | Wrong digest or canonical bytes is rejected by B.3a. | B.3a reload/hydration | Adversarial integration | Independently mutate digest, canonical bytes, non-object canonical JSON | Integrity failure; no request digest substituted; no mechanics bytes in error. | Adapter recomputes/repairs digest or uses `definition` fallback. |
| E9 | Exact valid provider resource hydrates through unchanged PR #20. | PR #20 route/service | Integration | Real loopback provider + exact graph fixture + concrete resolver | 200; `Cache-Control: no-store`; requested graph identity unchanged; mechanics SHA `935dc0...`; one graph revision read, one provider GET, zero head reads. | PR #20/B.3a code needed modification or call counts differ. |
| E10 | Repeated exact calls remain isolated and uncached. | PR #20 + resolver | Replay | POST same request twice | Byte-equivalent response JSON; two provider GETs; no shared mutation/cache. | One provider call, stale/mutated payload, or hidden cache. |
| E11 | Optional dependency boundary remains narrow. | Package imports/static boundary | Regression | Import and boundary commands | Root imports succeed without `httpx`; only concrete module may import it. | Root import loads/fails on `httpx` or kernel imports provider code. |
| E12 | No persistence, discovery, retry, UI, or graph mapping was added. | Cumulative diff | Scope inspection | Changed-path/source guards | Exact allowlist; no forbidden verbs/routes/stores/registries; no Buddy code. | Any extra capability or path. |

### Required command set

The code agent must run and record exact output for every applicable command:

```bash
# Base capture after PR #20 merges.
git rev-parse origin/main
git merge-base origin/main HEAD

# Core environment: no optional HTTP dependency required for root imports.
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import sys, dungeonmind; assert 'dungeonmind_dnd' not in sys.modules; assert 'httpx' not in sys.modules"
uv run --no-dev python -c "import sys, dungeonmind_dnd; assert 'httpx' not in sys.modules"

# Focused contracts and unchanged predecessor behavior.
uv run pytest -q tests/unit/test_dnd_statblock_resource_resolver.py
uv run pytest -q tests/unit/test_dnd_threat_mechanics.py tests/unit/test_dnd_threat_mechanics_transport_service.py tests/unit/test_dnd_threat_mechanics_api.py tests/unit/test_import_boundaries.py
uv run pytest -q -m "not integration"

# Optional API environment and real loopback composition.
uv sync --locked --extra api --extra postgres
uv run pyright src/dungeonmind_dnd/integration/statblock_resource_resolver.py
uv run pytest -q tests/integration/test_dnd_statblock_resource_resolver.py
DUNGEONMIND_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest -q -m integration

# Package and scope gates.
uv build
git diff --check
git diff --name-only "$PR20_MERGE_SHA"...HEAD
git diff --stat "$PR20_MERGE_SHA"...HEAD -- \
  Docs/Handoffs/HANDOFF-exact-statblock-resource-resolver.md \
  src/dungeonmind_dnd/integration/statblock_resource_resolver.py \
  src/dungeonmind_dnd/integration/__init__.py \
  tests/fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json \
  tests/unit/test_dnd_statblock_resource_resolver.py \
  tests/integration/test_dnd_statblock_resource_resolver.py \
  tests/unit/test_import_boundaries.py
```

The implementation may use `httpx.MockTransport` for focused unit failures,
but E9 and E10 require a real loopback socket. The loopback server must record
exact method, path, headers, call count, and whether a redirect target was
contacted.

### Minimal live/dogfood proof

Not applicable — this PR intentionally adds no production bootstrap,
deployment, Buddy consumer, or user surface. The real loopback HTTP composition
through the merged PR #20 app is the highest owning boundary available without
inventing a new operator surface.

A demand for live Buddy dogfood is a stop/split signal: the identity/profile
bridge and production composition must exist first.

### Baseline failure protocol

For any required command already failing on the exact PR #20 merge base:

1. run the identical command on base and head;
2. include both exact results;
3. classify whether head adds any failure;
4. do not label the gate green;
5. name the explicit operator waiver required when the failing command remains an acceptance gate.

No waiver may cover a failed focused resolver, B.3a, PR #20,
import-boundary, or loopback integration proof.

## §8 Required review handback

The handback must include:

- Exact PR URL or branch/head SHA and exact PR #20 merge-base SHA.
- §1 mission and merge-ready invariant copied exactly.
- Nano-commit list with one discrete implementation/proof story each.
- Actual changed paths and focused diff stat against the PR #20 merge SHA.
- Captured provider fixture source commit/path and copied-file SHA-256.
- Exact provider constants, request path, auth header name, timeout, and body limit.
- The exact expected B.3a ref for the captured fixture.
- E1–E12 produced result and provenance for every row.
- Exact call counts for unsupported, miss, valid, disagreement, repeat, timeout, redirect, and oversized cases.
- Exact HTTP status/error code/no-store results through PR #20.
- Secret/body/URL sanitization sentinel results, including cause/context/logs.
- Every required command and exact output.
- Baseline base/head failures and explicit operator waivers; none when none.
- Paths outside §4 or bounded exception; none or stop report.
- Stop conditions encountered and disposition; none when none.
- Explicit confirmation that no PR #20/B.3a production file changed.
- Explicit confirmation that no retry, cache, discovery, persistence, bootstrap, graph bridge, Buddy code, or UI was added.
- Named successor still false: `STATBLOCK: adapt published Buddy Threat identity into DungeonMind D&D profile`.
- Later shadow consumer still false: `STATBLOCK: shadow verify Buddy Threat hydration through DungeonMind`.
- Confirmation that this handoff was implemented without compressed or omitted constraints.

Disposition on complete evidence:

```text
READY_FOR_BUDDY_THREAT_IDENTITY_PROFILE_BRIDGE
```

## §9 Acceptance rubric

The reviewer accepts only when every item is true:

- Exactly one concrete provider-resolver capability was delivered — E3/E4/E9.
- One supported ref produces at most one exact authenticated GET — E3/E5/E9.
- Unsupported refs cannot become URLs or trigger fallback — E3.
- Provider exact misses are distinct from provider unavailability — E3/E5.
- Observed provider identity/schema/digest values are never overwritten with request values — E4/E7/E8.
- Provider `canonical_definition`, not `definition`, is the mechanics source — E4/E8.
- Parsed canonical mechanics reproduce the grounded provider digest under DungeonMind canonical hashing — E4.
- Wrong identity/version/digest/bytes fail through unchanged B.3a/PR #20 — E7/E8.
- Valid mechanics hydrate through unchanged PR #20 with no-store and exact graph pinning — E9.
- Repeated requests are isolated and uncached — E10.
- Redirect, timeout, HTTP, body-limit, and decoder failures are one-shot and sanitized — E5/E6.
- Authentication material is absent from error text, repr, details, cause, context, and logs — E2/E5.
- Root imports remain light and optional `httpx` ownership is narrow — E11.
- No new dependency, migration, route, durable format, registry, provider discovery, retry state, cache, graph mapping, or product surface exists — E12.
- The exact captured predecessor fixture and real vocabulary are used — E1/E4.
- No path outside §4 or its one bounded test-helper exception changed — E12.
- Every acceptance gate has exact produced evidence and provenance, with truthful base/head failures and explicit waivers.
- The named graph identity/profile bridge and later Buddy shadow consumer remain unimplemented and unclaimed.

## Stop conditions

Stop and report rather than expanding if implementation discovers:

- PR #20 is not merged or its merged contracts differ materially from reviewed head `32b949...`;
- the provider fixture differs materially from the grounded response shape;
- parsed `canonical_definition` does not hash under DungeonMind canonical JSON to the stripped `definition_digest`;
- correct provider disagreement classification requires changing B.3a or PR #20 public error semantics;
- a URL, credential, provider locator, contract repair, or current-head selector must enter `DndMechanicsResourceRef`;
- provider resolution requires list/search/discovery, retries, fallback, redirects, or stale cache;
- a production bootstrap/deployment change is required to prove the resolver;
- a Buddy `threat:*` ↔ DungeonMind `obj:*` mapping is required inside this adapter;
- a new public schema, durable identifier, persistence record, or provider registry appears;
- any production path outside §4 is required;
- `pyproject.toml`, `uv.lock`, migrations, CI workflows, or kernel code must change;
- a secret-bearing request or response can survive in exception cause/context or logs;
- a required owning-boundary proof cannot be produced.

Use this stop report shape:

```text
Stop condition:
Why the current mission cannot absorb it:
Invariant clause affected:
Required evidence now missing:
New public/durable contract discovered:
Affected observable paths or ownership layers:
Proposed successor slice:
Tracker or authority update needed:
```

## §10 Implementation handback

### Merge base and PR

- Resolver PR: https://github.com/Drakosfire/DungeonMind/pull/21
- Branch: `statblock/dungeonmind-statblock-resource-resolver`
- PR #20 merged predecessor SHA: `c9849e2123589679beba2c063e197342962dd67a`
- `git rev-parse origin/main`: `c9849e2123589679beba2c063e197342962dd67a`
- `git merge-base origin/main HEAD` before this handback commit: `c9849e2123589679beba2c063e197342962dd67a`
- Implementation head before this review-cycle handback update:
  `0829d4c7e319406ad90aff6b8f45101cf876790c`

The branch was created from the merged `origin/main` SHA before any resolver
code commit. The predecessor B.3a and PR #20 production files are unchanged.

### Mission and merge-ready invariant

An authorized DungeonMind mechanics host can resolve one exact accepted
DungeonMind statblock revision so the existing B.3a/PR #20 hydration seam can
serve real content-addressed mechanics rather than fixture-only resources.

Merge-ready invariant: One supported `DndMechanicsResourceRef` causes at most
one bounded, authenticated, non-redirecting GET for its exact provider
resource and revision; the resolver returns only an unmodified observed
resource identity plus the provider’s canonical mechanics object, while
misses, transport failures, response disagreements, secrets, retries,
locators, current-head inference, and fallback remain closed under the
existing B.3a and PR #20 authority boundaries.

### Nano commits

1. `51c8cec docs(statblock): add exact resource resolver handoff`
2. `12fd09c feat(statblock): add exact statblock resource resolver contract`
3. `be54a88 feat(statblock): resolve one exact provider revision without fallback`
4. `72a3e76 test(statblock): prove provider disagreement and transport boundaries`
5. `c78b89c test(statblock): compose resolver through exact Threat hydration`
6. `11668d3 test(statblock): prove resolver log sanitization`
7. This handback commit: `docs(statblock): complete resolver handback`
8. `0829d4c fix(statblock): remove public transport injection`
9. This review-cycle handback update: `docs(statblock): refresh resolver evidence`

### Changed paths and focused cumulative diff

Against `c9849e2123589679beba2c063e197342962dd67a`, the current cumulative
diff is 6 paths, 2,309 insertions, and no deletions. This review-cycle handback
appends the required evidence to the same handoff path:

```text
Docs/Handoffs/HANDOFF-exact-statblock-resource-resolver.md
src/dungeonmind_dnd/integration/statblock_resource_resolver.py
tests/fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json
tests/integration/test_dnd_statblock_resource_resolver.py
tests/unit/test_dnd_statblock_resource_resolver.py
tests/unit/test_import_boundaries.py
```

No path outside §4 changed. No `pyproject.toml`, `uv.lock`, migration, CI,
kernel, B.3a, or PR #20 production file changed.

### Provider grounding and exact constants

Source: `Drakosfire/DungeonMindBuddy`, commit
`d50d0c3a45761376185d36fb39ae3a098a5b8cfc`, path
`tests/fixtures/statblocks/v1/exact-revision-response.json`.

Copied fixture SHA-256:

```text
9e777f98e25e8a1a4e38f01b08528bfd2a4c99e9bf3d00853cfb0a88b8221c6c
```

The copied file and source file hashes are byte-identical. Parsed
`canonical_definition` under DungeonMind canonical JSON produces:

```text
935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51
```

```text
provider_id:       dungeonmind.statblocks
resource_schema:   dungeonmind.dungeonbuddy-statblocks.1.0.0
media_type:        application/json
resource_id:       ^sb_[a-z0-9]+$
resource_revision: ^rev_[a-z0-9]+$
route:             /api/internal/dungeonbuddy/v1/statblocks/{resource_id}/revisions/{resource_revision}
auth header:       X-DungeonBuddy-Internal-Key
default timeout:   90.0 seconds
maximum timeout:   120.0 seconds
maximum body:      1,048,576 bytes
redirects:         refused; follow_redirects=False
```

Exact B.3a ref:

```json
{
  "schema_version": "dmdnd_mechanics_resource_ref_v1",
  "ruleset_id": "dnd5e",
  "provider_id": "dungeonmind.statblocks",
  "resource_id": "sb_000001",
  "resource_revision": "rev_000002",
  "resource_schema": "dungeonmind.dungeonbuddy-statblocks.1.0.0",
  "media_type": "application/json",
  "payload_sha256": "935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51"
}
```

### E1–E12 evidence

- **E1:** The captured response maps the real Buddy fields without vocabulary
  rewriting. The raw copied-file hash and parsed payload digest are recorded
  above; `definition` is absent from the observed envelope.
- **E2:** URL credentials, path, query, fragment, unsupported scheme, blank
  key, NaN, zero, and over-limit timeout configurations fail before HTTP.
  Config repr and resolver errors redact the internal key.
- **E3:** Four unsupported refs make zero HTTP calls. 404 and 410 each make
  exactly one GET and return `None`; no list, search, or fallback exists.
- **E4:** The valid fixture makes one GET with the exact method, path, and
  `X-DungeonBuddy-Internal-Key`; observed identity and parsed canonical
  mechanics match the exact ref and digest.
- **E5:** 302, 401, 403, 408, 409, 422, 429, 500, and 503 each make one
  request and produce `resolver_unavailable`. Connect and read timeout
  failures are also one-shot. Redirect target calls remain zero. Error text,
  repr, details, cause, and context contain no secret. The public resolver
  constructor owns the constrained client with `trust_env=False`; a real
  hostile proxy loopback receives zero calls while the provider receives one
  exact GET.
- **E6:** Declared oversized bodies fail before reading content. Streamed
  bodies stop after the first chunk beyond one MiB; no partial envelope is
  returned.
- **E7:** Loopback mutations of `statblock_id`, `revision_id`, and
  `contract_version` produce PR #20 HTTP 502
  `mechanics_resource_integrity_failure`, one provider call, and no mechanics
  bytes in the error.
- **E8:** Independent digest, canonical-byte, and non-object canonical JSON
  mutations produce the same B.3a integrity failure. The request digest is
  never substituted and changed mechanics do not appear in the error.
- **E9:** The exact provider response hydrates through the unchanged PR #20
  host with HTTP 200 and `Cache-Control: no-store`; one exact graph revision
  read, one provider GET, and zero head reads. Returned mechanics hash to
  `935dc0...`.
- **E10:** Two identical POSTs produce isolated byte-equivalent mechanics and
  two provider GETs; the graph repository performs two exact revision reads
  and zero head reads.
- **E11:** Core no-extra import checks pass without `httpx` loaded. Only the
  concrete integration module is allowed to own the optional `httpx` import;
  import-boundary tests pass. The public constructor has no transport
  injection; focused unit tests use only the module-private `MockTransport`
  seam.
- **E12:** The cumulative diff is the six-path allowlist above. No persistence,
  discovery, retry, cache, UI, graph mapping, Buddy code, bootstrap, route,
  registry, or durable format was added.

### Verification provenance

```text
uv sync --locked
  passed; removed optional api/postgres packages.
uv run ruff check .
  passed.
uv run pyright
  passed: 0 errors, 0 warnings, 0 informations.
uv run --no-dev python -c "import sys, dungeonmind; assert 'dungeonmind_dnd' not in sys.modules; assert 'httpx' not in sys.modules"
  passed.
uv run --no-dev python -c "import sys, dungeonmind_dnd; assert 'httpx' not in sys.modules"
  passed.
uv run pytest -q tests/unit/test_dnd_threat_mechanics.py tests/unit/test_dnd_threat_mechanics_transport_service.py tests/unit/test_dnd_threat_mechanics_api.py tests/unit/test_import_boundaries.py
  passed.
uv run pytest -q -m "not integration"
  passed in the core no-extra environment.
uv sync --locked --extra api --extra postgres
  passed.
uv run pyright src/dungeonmind_dnd/integration/statblock_resource_resolver.py
  passed: 0 errors, 0 warnings, 0 informations.
uv run pytest -q tests/unit/test_dnd_statblock_resource_resolver.py
  passed: 40 tests.
uv run pytest -q tests/integration/test_dnd_statblock_resource_resolver.py
  passed: 13 tests.
uv run pytest -q -m integration
  passed; database-backed tests skipped because DUNGEONMIND_DATABASE_URL was unset.
uv run pytest -q -m "not integration"
  passed in the API-enabled environment.
uv run ruff check .
  passed.
uv build
  passed; source distribution and wheel built.
git diff --check
  passed.
```

The focused resolver command in the no-extra environment is intentionally
skipped because its test module requires the optional `api` extra; the
complete no-extra suite passed, and the focused resolver command passed after
`uv sync --locked --extra api --extra postgres`. This is an environment
qualification, not a resolver or predecessor waiver. The real loopback proof
passed without a database.

### Scope, stop conditions, and successors

No stop condition was encountered. No bounded discovery exception was used.
No PR #20/B.3a production file changed. No retry, cache, discovery,
persistence, bootstrap, graph bridge, Buddy code, or UI was added.

The named successor remains false and unclaimed:

```text
STATBLOCK: adapt published Buddy Threat identity into DungeonMind D&D profile
```

The later shadow consumer remains false and unclaimed:

```text
STATBLOCK: shadow verify Buddy Threat hydration through DungeonMind
```

The handoff constraints were retained in this checked-in document; no
constraint was intentionally omitted or broadened.

Disposition:

```text
READY_FOR_BUDDY_THREAT_IDENTITY_PROFILE_BRIDGE
```
