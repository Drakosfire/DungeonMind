# HANDOFF — B.1b Curated Browser Surface Consumer Proof

**Created:** 2026-07-31
**Status:** ACTIVE — dispatch exactly one implementation capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b1b-curated-browser-surface.md`
**Repository / branch:** `Drakosfire/DungeonMind` / suggested `founding/pr-b1b-curated-browser-surface`
**Implementation base:** `320f270767461800076bfe32f77b137ab6662d5e`
**Predecessor:** merged PR `#4` — B.1a Thin read-only Mind Turn host
**One-line mission:** A deliberately minimal, non-product browser surface consumes the live curated DungeonMind Mind Turn API and visibly proves readiness, grounded answers, semantic projections, grounded abstention, sanitized failure, and exact replay without moving product-surface ownership into DungeonMind.

---

## §0 Design decision and capability decomposition

The original roadmap described B.1 as a DungeonMind API host plus a LandingPage static route. This agent is responsible only for the DungeonMind repository. A LandingPage implementation would violate the repository boundary and the rule that cross-repository changes land as separate PRs.

This slice therefore closes the **DungeonMind-owned consumer proof** with a tiny browser example under `examples/`. It is a real cross-origin HTTP consumer, but it is explicitly not LandingPage and not a production product surface.

| Candidate outcome                                                                                |                       Independently useful? | Decision                             |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------: | ------------------------------------ |
| Browser page calls the real `/readyz` and `/v1/mind-turn` endpoints and renders semantic results |                                         Yes | **Include**                          |
| Cross-origin request behavior is proven against the existing single-origin demo CORS policy      | Yes, but inseparable from the browser proof | **Include under the same invariant** |
| LandingPage route or shared product UI component                                                 |                                         Yes | **Exclude — external successor**     |
| New Mind Turn contract fields or projection kinds                                                |                                         Yes | **Exclude**                          |
| Source-opening endpoint for `open_source` suggestions                                            |                                         Yes | **Exclude**                          |
| Hermes or model-provider adapter                                                                 |                                         Yes | **Exclude**                          |
| Authentication, multi-tenant policy, or production deployment                                    |                                         Yes | **Exclude**                          |

**Selected capability:** one browser-rendered, cross-origin, read-only consumer of the existing curated B.1a host.

**Invariant:**

```text
For one seeded curated world and one server-bound demo caller, the browser renders
only the exact successful, abstaining, replayed, or sanitized-failure state
returned by DungeonMind; it neither reconstructs graph semantics nor claims a
write, source-open, authentication, or product-surface capability.
```

**Mission falsification test:**

```text
This is not one slice if implementation must change mind_turn_v1, add an API
endpoint, introduce a frontend framework/toolchain, implement source reads,
modify graph/retrieval behavior, or touch another repository.
```

---

## §1 Outcome

A developer can seed the existing synthetic curated fixture, start the existing single-worker DungeonMind demo API, start a repository-local static browser example on a second origin, and use that page to:

1. observe API readiness;
2. ask “Who safeguards the Sun Ledger?” and see the grounded answer, pinned revision, entity briefs, relationship list, and evidence summary;
3. resend the exact same request and see that the returned response is identical;
4. ask “Who is the Moon King?” and see a grounded abstention with no fabricated entity or relationship projection;
5. stop or misconfigure the API and see a truthful unavailable or sanitized error state rather than a fabricated answer.

The page is an acceptance surface for the transport and semantic response contract. It is not a new DungeonMind product surface.

---

## §2 Authority and anchors

Read these in order before changing code:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `CONTRIBUTING.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `Docs/Handoffs/HANDOFF-TEMPLATE.md`
6. Merged PR `#4` and merge commit `320f270767461800076bfe32f77b137ab6662d5e`
7. `src/dungeonmind/contracts/mind_turn.py`
8. `src/dungeonmind/service/api.py`
9. `src/dungeonmind/service/bootstrap.py`
10. `src/dungeonmind/service/demo_access.py`
11. `src/dungeonmind/service/error_mapping.py`
12. `tests/fixtures/curated_mind_turn_v1.json`
13. `tests/fixtures/requests/who-safeguards-ledger.json`
14. `tests/integration/test_mind_turn_api.py`
15. `.github/workflows/ci.yml`

### Authority precedence

```text
1. Current DungeonMind architecture, authority map, and accepted ADRs
2. Merged repository state at the implementation base
3. This checked-in handoff
4. Existing tests and fixture contracts
5. Project Sources or chat summaries
```

If current `main` has moved, rebase the handoff onto the new immutable base and verify that no merged successor has already changed the public demo API, fixture binding, or roadmap sequence.

---

## §3 Scope

### In scope

* A framework-free static browser example using HTML, CSS, and browser JavaScript only.
* A stdlib-only local static-file server that serves only the example directory.
* Consumption of the existing:

  * `GET /readyz`;
  * `POST /v1/mind-turn`;
  * `mind_turn_v1` request and response;
  * server-owned `DemoAccessBinding` enforcement;
  * single configured CORS origin.
* Primary rendering of:

  * `answer`;
  * `revision_id`;
  * `entity_brief` projections;
  * `relationship_list` projections;
  * `evidence_summary` projection;
  * grounded empty/abstention state;
  * sanitized `{error: {code, message, details}}` envelopes.
* Exact replay from the browser by resending the identical request payload, including the same `request_id`.
* Automated tests for static asset integrity, request-template parity, CORS behavior, success, abstention, and replay.
* A manual runbook proving the page in a real browser against a real PostgreSQL-backed API host.
* README and roadmap synchronization reflecting that B.1a and this DungeonMind-owned B.1b proof are landed/in flight accurately.

### Out of scope — falsification boundaries

* Any change in `src/dungeonmind/contracts/**`.
* Any change in graph scope, retrieval, evidence admission, context assembly, agent behavior, persistence, or projection construction.
* Any new or changed HTTP endpoint.
* LandingPage, DungeonMindBuddy, DungeonMindServer, or another repository.
* React, Vue, Svelte, Vite, npm, Node dependencies, Playwright, Selenium, or another frontend toolchain.
* Production authentication or authorization.
* Multi-user or multi-thread selection.
* Source-body reads or an implementation of `open_source`.
* Durable graph writes, contribution proposals, or write capabilities.
* Hermes or any network model provider.
* Production reverse proxy, TLS, deployment, backups, or multi-worker execution.
* General-purpose UI component abstractions or a design system.

---

## §4 Invariants that bind this slice

1. **DungeonMind owns knowledge behavior; the example surface owns only presentation.** It must not resolve aliases, traverse relationships, admit evidence, assemble prompts, or infer authority locally.
2. **Every read remains explicit and pinned by the response.** The page displays the returned `revision_id`; it never substitutes “latest” or infers a graph revision.
3. **Trusted demo scope remains server-owned.** The page may submit the synthetic fixture request, but `authorize_demo_request` remains the authority and exact mismatch remains forbidden.
4. **No agent or surface receives write authority.** The example sends only read-only Mind Turn requests and exposes no write affordance.
5. **Similarity is not evidence.** The page renders semantic projections and admitted evidence identifiers; it never renders retrieval scores as factual support.
6. **Failures remain truthful.** Network failure, readiness failure, request validation, capability denial, revision absence, idempotency conflict, persistence unavailability, and integrity errors must never render a stale or invented answer as success.
7. **Core stays light.** No new dependency is required to import `dungeonmind`; no frontend package manager is introduced.
8. **The API host remains single-worker for this proof.** B.1a process-local request coordination is not silently upgraded or claimed as cross-worker exactly-once execution.
9. **The example is not a product owner.** Its filenames, DOM names, and documentation must use neutral demo/consumer vocabulary, never `LandingPage` or another surface’s internal layout vocabulary.

---

## §5 Observable-path inventory

| Observable path                | Initial state                                   | Required result                                                                                  | Owning boundary                                       |
| ------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| Page load                      | Static assets available; API may be unavailable | Page renders without external network calls and checks `/readyz`                                 | Browser example                                       |
| Ready host                     | Seeded fixture and active embedding run         | Ask controls become enabled and returned revision is shown                                       | API + browser                                         |
| Grounded success               | “Who safeguards the Sun Ledger?”                | Answer includes Mere Astor; entity, relationship, and evidence projections render                | Existing API contract + browser renderer              |
| Grounded miss                  | “Who is the Moon King?”                         | Abstaining answer; zero fabricated entity/relationship cards                                     | Existing API contract + browser renderer              |
| Exact replay                   | Same complete payload and `request_id`          | Response matches the first parsed response; browser reports replay match                         | Existing persistence/idempotency + browser comparison |
| Changed payload with reused ID | Same `request_id`, changed message              | Sanitized HTTP 409 idempotency conflict; prior success is not shown as new success               | Existing API + browser error state                    |
| API unavailable                | Host stopped or unreachable                     | Clear unavailable state; no stale answer presented as current                                    | Browser network handling                              |
| Readiness failure              | Database/fixture not ready                      | Ask remains disabled; readiness payload/error shown safely                                       | Existing `/readyz` + browser                          |
| Validation/capability failure  | Invalid or mismatched request                   | Sanitized code/message shown; no raw exception/stack                                             | Existing error envelope + browser                     |
| Unsupported suggested action   | `open_source` is returned                       | Displayed only as unavailable/read-only metadata or omitted; never rendered as a working control | Browser example                                       |
| Disallowed CORS origin         | Origin differs from configured demo origin      | Browser cannot consume the API; automated preflight test proves no allow-origin grant            | FastAPI CORS boundary                                 |

---

## §6 Files in scope — exact allowlist

| Action | Path                                                           | Purpose                                                                                           |
| ------ | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Create | `Docs/Handoffs/HANDOFF-b1b-curated-browser-surface.md`         | Canonical dispatch authority                                                                      |
| Create | `examples/curated_mind_turn_surface/index.html`                | Minimal semantic result surface                                                                   |
| Create | `examples/curated_mind_turn_surface/app.js`                    | Existing API consumer and state renderer                                                          |
| Create | `examples/curated_mind_turn_surface/styles.css`                | Minimal local presentation; no framework                                                          |
| Create | `examples/curated_mind_turn_surface/demo-request.json`         | Browser-readable byte-identical copy of the canonical request fixture                             |
| Create | `scripts/serve_curated_mind_turn_surface.py`                   | Loopback static server for the example directory only                                             |
| Create | `tests/unit/test_curated_mind_turn_surface_assets.py`          | Asset, parity, path-safety, and no-external-dependency proof                                      |
| Create | `tests/integration/test_curated_mind_turn_surface_contract.py` | CORS, success, abstention, conflict, and exact replay proof against PostgreSQL/API                |
| Create | `Docs/Runbooks/RUNBOOK-b1b-curated-browser-surface.md`         | Exact local start and browser proof procedure                                                     |
| Modify | `README.md`                                                    | Current-state and demo-run instructions                                                           |
| Modify | `Docs/Roadmaps/ROADMAP.md`                                     | Mark B and B.1a landed; define this DungeonMind-only B.1b and external product adoption successor |

### Bounded discovery exception

Not applicable. If another path is required, stop and report it rather than expanding the diff.

---

## §7 Implementation contract

### 7.1 Static consumer

The page must:

* be loadable from `http://127.0.0.1:8081/` by default;
* use an editable API-base input defaulting to `http://127.0.0.1:8000`;
* load `demo-request.json` before enabling Ask;
* call `${apiBase}/readyz` before enabling normal submission;
* create a fresh opaque `request_id` for each new Ask;
* retain the complete last submitted payload for exact Replay;
* never reuse a prior request ID for a changed message unless exercising the explicit conflict proof;
* parse response projections by `kind`, not array position;
* tolerate unknown future projection kinds by ignoring them or showing them only in collapsed developer detail;
* render no raw HTML from response fields; use text nodes/text content only;
* clear or mark prior results stale when a new request begins;
* preserve a prior response only as labeled history, never as the current result after a failed request;
* make diagnostics and raw JSON optional/collapsed, not the primary product view;
* make no external network requests, CDN loads, analytics calls, or font loads.

### 7.2 Required rendered semantics

**Success view**

* answer text;
* exact `revision_id`;
* `entity_brief` entries with label, kind, optional aliases, and optional summary;
* `relationship_list.relationships` with subject ID, predicate, and object ID;
* evidence count and admitted evidence IDs from `evidence_summary`;
* a small status indicating the result is grounded when projections/evidence exist.

**Abstention view**

* the returned abstaining answer;
* a clear “No grounded objects returned” state;
* no empty placeholder entity/relationship cards;
* coverage gaps may appear in collapsed details.

**Error view**

* HTTP status when available;
* public error `code` and `message`;
* allowlisted public `details` only as returned by the server;
* a distinct network-unavailable message when no HTTP response exists;
* never the previous answer styled as current success.

**Replay view**

* exact same request body is resent;
* parsed response is compared with the prior parsed response;
* “Exact replay matched” appears only when they are equal;
* a mismatch is a visible failure and blocks acceptance.

### 7.3 Request-template authority

`tests/fixtures/requests/who-safeguards-ledger.json` remains canonical.

`examples/curated_mind_turn_surface/demo-request.json` must be byte-identical to it. The unit test must fail on drift. The browser replaces only:

* `request_id` for a new request;
* `message` from the user input.

It must not rewrite caller, tenant, role, world, campaign, thread, admissibility, or surface identity.

### 7.4 Static server

`scripts/serve_curated_mind_turn_surface.py` must:

* use only Python stdlib;
* default to host `127.0.0.1` and port `8081`;
* serve only `examples/curated_mind_turn_surface/`;
* refuse path traversal outside that root;
* perform no writes;
* initialize no DungeonMind service, database, or model;
* print the browser URL and the exact required API CORS origin;
* be safe to import without starting a server;
* return a nonzero exit code for invalid arguments or missing asset root.

### 7.5 API and CORS contract

No production endpoint or response schema changes are permitted.

The existing host must be run with:

```bash
DUNGEONMIND_CORS_ORIGIN=http://127.0.0.1:8081
```

Automated integration proof must cover:

* allowed-origin preflight for `POST /v1/mind-turn`;
* allowed-origin POST response includes the expected CORS header;
* disallowed origin is not granted `Access-Control-Allow-Origin`;
* credentials are not enabled;
* `/readyz` is consumable from the allowed origin;
* the endpoint set remains exactly `/healthz`, `/readyz`, `/v1/mind-turn`.

### 7.6 Replay and idempotency matrix

| Situation                                                     | Required behavior                                                                                              |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Same request ID + byte-equivalent body                        | Same response; no second agent execution; browser reports exact replay match                                   |
| Same request ID + changed message                             | HTTP 409 `idempotency_conflict`; original stored result remains authoritative                                  |
| New request ID + same message                                 | New valid turn using the same curated graph revision unless the operator explicitly pins another revision      |
| API restart after successful request                          | Exact replay reconstructs/loads the stored result without silently changing revision or answer                 |
| Browser retry after network failure before receiving response | User may Replay the retained exact payload; server semantics determine whether it is first execution or replay |

### 7.7 Trust boundary

**The browser may choose:**

* message;
* API base URL;
* a new opaque request ID;
* whether to replay the retained exact request.

**The browser must not choose or reinterpret:**

* authorization policy;
* world/campaign access;
* admissibility escalation;
* graph revision selection beyond an explicitly present canonical request field;
* evidence admission;
* relationship traversal;
* enabled tools;
* write capability.

---

## §8 Work plan

1. **Check in this handoff unchanged as dispatch authority.**

   * Verify base SHA and predecessor.
   * Verify no open DungeonMind PR has superseded B.1b.

2. **Add the static assets and canonical request copy.**

   * Keep the page framework-free.
   * Use semantic projection kinds from the existing response contract.
   * Add the exact fixture-parity unit test.

3. **Add the loopback static server.**

   * Restrict serving to the example root.
   * Add unit tests for root resolution, missing files, and traversal attempts.

4. **Add API consumer integration tests.**

   * Reuse the existing curated fixture seeding and `create_app` construction.
   * Prove CORS, success, abstention, exact replay, and changed-body conflict at the HTTP boundary.
   * Do not duplicate retrieval-unit assertions already owned by B.1a.

5. **Write the runbook and execute the real browser proof.**

   * Use real PostgreSQL/pgvector, Alembic migration, explicit seed, existing API host, and static server.
   * Record browser, operating system, exact commands, and observations.
   * Capture screenshots locally or attach them to the PR; do not commit generated screenshots unless the repository explicitly permits them.

6. **Synchronize README and roadmap.**

   * Correct stale statements that PostgreSQL and B.1a do not exist.
   * Mark the example as a non-product acceptance surface.
   * Name external product-surface adoption as still false and outside this repository.

---

## §9 Acceptance gates

### 9.1 Core gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run pytest -m "not integration"
```

Expected: all pass; core import still requires neither `postgres` nor `api` extras.

### 9.2 Integration gates

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run alembic upgrade head
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run python scripts/seed_curated_mind_turn.py
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run python scripts/seed_curated_mind_turn.py
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -m integration
```

Expected:

* migration succeeds;
* first seed creates the fixture;
* second seed is exact idempotent replay;
* all integration tests pass, including B.1b contract tests.

### 9.3 Focused gates

```bash
uv run pytest -q tests/unit/test_curated_mind_turn_surface_assets.py
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -q tests/integration/test_curated_mind_turn_surface_contract.py
uv run python scripts/serve_curated_mind_turn_surface.py --help
```

### 9.4 Diff gates

```bash
git diff --check
git diff --name-only 320f270767461800076bfe32f77b137ab6662d5e...HEAD
git diff --stat 320f270767461800076bfe32f77b137ab6662d5e...HEAD -- \
  Docs/Handoffs/HANDOFF-b1b-curated-browser-surface.md \
  examples/curated_mind_turn_surface/index.html \
  examples/curated_mind_turn_surface/app.js \
  examples/curated_mind_turn_surface/styles.css \
  examples/curated_mind_turn_surface/demo-request.json \
  scripts/serve_curated_mind_turn_surface.py \
  tests/unit/test_curated_mind_turn_surface_assets.py \
  tests/integration/test_curated_mind_turn_surface_contract.py \
  Docs/Runbooks/RUNBOOK-b1b-curated-browser-surface.md \
  README.md \
  Docs/Roadmaps/ROADMAP.md
```

No path outside §6 may change.

### 9.5 Required manual browser proof

Use the exact runbook. At minimum record:

1. `/readyz` becomes ready in the page.
2. “Who safeguards the Sun Ledger?” renders:

   * Mere Astor in the answer;
   * the returned `rev:*` revision;
   * entity briefs for Mere Astor and the Sun Ledger;
   * the `safeguards` relationship;
   * admitted evidence summary.
3. Replay Exact Request reports an identical response.
4. “Who is the Moon King?” returns an abstention and no entity/relationship cards.
5. Stop the API; a new Ask renders unavailable and no current answer.
6. Browser console contains no uncaught errors and no external network requests.

The changed-body request-ID conflict remains an automated HTTP-boundary gate; do not add a special product-like control solely to trigger it in the browser.

Manual proof is an acceptance gate because the mission is specifically a real browser consumer. Automated HTTP tests alone do not close B.1b.

---

## §10 Stop conditions

Stop and report rather than expanding scope if:

* the current Mind Turn request or response differs materially from `mind_turn_v1` at the implementation base;
* the curated fixture or demo binding is no longer synthetic and safe to expose in a local example;
* a real browser cannot consume the API without changing an existing endpoint or public contract;
* the page requires a source-body endpoint to be useful;
* exact replay is not stable through the existing API;
* CORS cannot be proven with the existing `cors_origin` seam;
* a frontend dependency or build tool appears necessary;
* another repository must change;
* a path outside §6 is required;
* the implementation starts adding product navigation, persistent browser history, authentication, graph writes, or general UI abstractions;
* any required base command fails and the failure cannot be shown to pre-exist on `320f270`;
* manual browser proof reveals that the response projection vocabulary is insufficient for even this curated example.

Use this report:

```text
Stop condition:
Why B.1b cannot absorb it:
Current contract or ownership conflict:
Affected observable paths:
Required path or repository outside scope:
Proposed independently useful successor:
Operator decision required:
```

---

## §11 Acceptance rubric

The reviewer accepts only when every item is true:

* [ ] The browser example consumes the real PostgreSQL-backed HTTP host, not an imported service object or mocked response.
* [ ] The browser and API run on distinct origins and CORS is proven at the HTTP boundary.
* [ ] Success renders answer, exact revision, entity, relationship, and evidence semantics from `mind_turn_v1`.
* [ ] Abstention renders no fabricated entity or relationship projection.
* [ ] Exact replay resends the identical payload and returns an identical parsed response.
* [ ] Changed-body request-ID reuse returns a sanitized conflict and does not rewrite prior truth.
* [ ] Network/readiness/API failures are truthful and never leave a stale answer presented as current success.
* [ ] The canonical request fixture and browser request template cannot drift.
* [ ] The page does not locally implement identity, retrieval, traversal, evidence admission, or prompt assembly.
* [ ] No write, source-open, Hermes, authentication, product-surface, or deployment capability is claimed.
* [ ] No new dependency or frontend toolchain is introduced.
* [ ] Core import without optional extras remains green.
* [ ] The API path set remains exactly `/healthz`, `/readyz`, and `/v1/mind-turn`.
* [ ] The complete diff is inside §6.
* [ ] README and roadmap describe the merged state truthfully.
* [ ] Manual browser evidence is included in the handback.

---

## §12 Required implementation handback

The PR body or handback must include:

1. Repository, branch, base SHA, head SHA, PR number, and status.
2. Exact changed paths and focused diff stat.
3. Every §9 command with exact result and provenance:

   * author-local;
   * independently rerun local;
   * CI;
   * manual browser observation.
4. Browser proof environment and steps.
5. Screenshots or equivalent attached evidence for success, replay, abstention, and unavailable/error states.
6. CORS evidence for allowed and disallowed origins.
7. Confirmation that the browser request template is byte-identical to the canonical request fixture.
8. Confirmation that no endpoint, contract, graph behavior, retrieval behavior, or persistence behavior changed.
9. Paths outside the allowlist: `none` or a stop report.
10. Baseline failures and waivers: `none` or exact base/head comparison.
11. Stop conditions encountered: `none` or exact report.
12. What remains false:

    * LandingPage integration;
    * production authentication;
    * source opening;
    * Hermes;
    * graph writes;
    * multi-worker exactly-once adapter execution;
    * production deployment.
13. Named successors:

    * external product-surface adoption of `mind_turn_v1`;
    * source-read/open-source capability, only when separately designed;
    * production access and deployment hardening, only on their roadmap rungs.

---

## §13 Reviewer protocol

1. Restate the mission and invariant before reading files.
2. Confirm the example is a consumer, not a second knowledge implementation.
3. Inspect every browser-derived field and ensure it comes directly from the response.
4. Verify unknown projection kinds fail soft without corrupting known projections.
5. Verify all text insertion is non-HTML and cannot execute response content.
6. Verify prior success cannot remain presented as current after failure.
7. Run the exact replay and changed-body conflict sequences against PostgreSQL.
8. Inspect CORS headers from allowed and disallowed origins.
9. Verify the static server cannot leave the example root.
10. Verify no product/LandingPage vocabulary or ownership entered DungeonMind.
11. Compare changed paths to §6.
12. Confirm every successor remains false and unclaimed.

---

## §14 Definition of done

B.1b is complete for the DungeonMind repository when a human can point a normal browser at the repository-local example, ask the curated questions through the real HTTP host, inspect the semantic projections and revision returned by DungeonMind, observe exact replay and grounded abstention, and see truthful failure behavior—without any other repository, frontend framework, contract expansion, or write path.

This closes the **replaceable surface → DungeonMind read seam**. It does not claim that LandingPage or another product surface has adopted the seam.
