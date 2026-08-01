# HANDOFF — B.2a Assertion-Scoped Alias and Summary Read Projection

**Created:** 2026-07-31
**Status:** ACTIVE — dispatch exactly one DungeonMind implementation capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md`
**Repository / suggested branch:** `Drakosfire/DungeonMind` / `founding/pr-b2a-assertion-scoped-alias-summary`
**Implementation base:** `f94105f9bf547add2ca815a70f5fc9a8752d9531`
**Predecessor:** merged PR `#5` — B.1b Curated browser surface consumer proof
**One-line mission:** Add one explicitly versioned graph-read schema in which an object's primary identity remains coarse and grounded, while aliases and summary are independently admitted or omitted by their own evidence provenance; prove player/GM behavior through the real Mind Turn path without creating a generic world-object or assertion framework.

---

## §0 Design checkpoint

PRs A through B.1b have proven the complete replaceable read seam:

```text
immutable graph revision
→ scoped retrieval and evidence admission
→ read-only Mind Turn
→ HTTP contract
→ real browser consumer
```

The current `dm_union_graph_v1` reader remains deliberately conservative: every evidence reference attached to an object must be valid and in scope or the entire object is hidden. That prevents leakage, but it also means one GM-only alias or summary can hide an otherwise player-visible object.

This slice replaces neither that schema nor that safety rule. It adds a second graph schema that proves one narrower permanent behavior:

```text
object existence + primary label evidence remains coarse
alias assertion evidence is evaluated per alias
summary assertion evidence is evaluated independently
relationships remain coarse
```

The checked-in roadmap's next numbered external rung, PR C, belongs to `RulesIngestion`. This handoff is the next **DungeonMind-owned** capability. PR C may proceed independently in its owning repository; this PR must not import, edit, or emulate it.

### Selected capability

**B.2a — assertion-scoped aliases and summary for read projection only.**

### Rejected alternatives

| Alternative                                                               | Decision | Reason                                                                                                                          |
| ------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Silently add assertion fields to `dm_union_graph_v1`                      | Reject   | Published graph schemas are immutable/versioned; existing revisions must retain exact semantics.                                |
| Build a generic `WorldObject`, property bag, or universal assertion model | Reject   | Too broad; aliases and summary are the smallest concrete fields exposed by B.1a's coarse-object limitation.                     |
| Put `visibility` or `campaign_id` directly on alias/summary assertions    | Reject   | Creates a second authority that can disagree with source provenance. Scope is derived from admitted evidence.                   |
| Add field-level semantic-document materialization                         | Defer    | Candidate documents remain derived discovery records; this slice proves graph admission and projection, not ingestion redesign. |
| Add source opening                                                        | Defer    | Source body/excerpt storage and locator semantics require a separate contract.                                                  |
| Implement this in DungeonMindBuddy or RulesIngestion                      | Reject   | Repository ownership is DungeonMind only.                                                                                       |

### Governing invariant

```text
For dm_union_graph_v2, a caller may receive an object only when its core
identity evidence is admitted. Each alias and the summary are then retained
only when every evidence reference attached to that field is independently
valid and in scope. Omitted fields must not participate in identity resolution,
agent context, semantic projections, evidence, anchors, coverage, or diagnostics.
```

### Mission falsification test

```text
This is no longer one PR if it requires a generic assertion framework,
normalized assertion tables, graph authoring or publication changes,
field-level embedding ingestion, a new HTTP endpoint, a sibling-repository
change, or any rewrite of an existing dm_union_graph_v1 revision.
```

---

## §1 Observable product outcome

A player and a GM can read the same exact graph object at the same exact graph revision while receiving different safe field projections:

* both may receive the grounded primary label;
* the player receives only aliases grounded in player-admissible evidence;
* the player does not receive a GM-only alias or summary;
* the GM receives player- and GM-admissible aliases plus the GM summary;
* the object is not hidden merely because one optional field is GM-only;
* hidden values cannot resolve a mention or appear anywhere else in the response envelope;
* exact replay remains deterministic and revision-pinned.

This is independently useful because it removes a known over-hiding behavior without opening a write path or attempting to model every rich object field.

---

## §2 Authority and anchors

Read these in order before editing:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `Docs/Handoffs/HANDOFF-found-dungeonmind-repository.md` — especially §14–15
4. `CONTRIBUTING.md`
5. `Docs/Roadmaps/ROADMAP.md`
6. merged PR `#4` — B.1a Mind Turn host
7. merged PR `#5` — B.1b browser consumer proof
8. `src/dungeonmind/application/graph_snapshot.py`
9. `src/dungeonmind/application/graph_scope.py`
10. `src/dungeonmind/application/mind_turn.py`
11. `src/dungeonmind/application/context_assembly.py`
12. `src/dungeonmind/contracts/evidence.py`
13. `src/dungeonmind/contracts/retrieval.py`
14. `src/dungeonmind/infrastructure/fixtures/curated_mind_turn.py`
15. `src/dungeonmind/service/bootstrap.py`
16. `tests/unit/test_graph_snapshot_reader.py`
17. `tests/unit/test_graph_scope_provenance.py`
18. `tests/unit/test_mind_turn_service.py`
19. `tests/integration/test_mind_turn_api.py`

### Authority precedence

```text
1. Current checked-in DungeonMind code, contracts, ADRs, and architecture
2. Merged repository state at f94105f9bf547add2ca815a70f5fc9a8752d9531
3. This checked-in handoff
4. Existing tests and synthetic fixtures
5. Project Sources and chat summaries
```

If `main` has moved, re-anchor to the new merge commit and confirm no merged or open DungeonMind PR already changes graph-schema parsing, graph scoping, or Mind Turn projection semantics.

---

## §3 Scope

### In scope

* A new stored graph schema identifier: `dm_union_graph_v2`.
* Preservation of `dm_union_graph_v1` and its coarse-object behavior without migration or reinterpretation.
* Schema-local records for:

  * alias assertions;
  * one optional summary assertion.
* Independent evidence classification for each alias and summary.
* A version-dispatching graph reader used by the default Mind Turn service, fixture validation, and demo-host readiness.
* Scoped rebuilding of label and alias indexes after field admission.
* Existing `entity_brief` projections populated only with admitted aliases and summary.
* One additive semantic projection kind, `entity_field_provenance`, containing only admitted alias/summary assertion mappings.
* A synthetic fixture proving player and GM behavior.
* Unit and PostgreSQL-backed Mind Turn integration tests.
* Roadmap, architecture, and README synchronization.

### Out of scope

* Changes to `mind_turn_v1`, `dm_graph_revision_v1`, `dm_evidence_ref_v1`, or any other public durable contract.
* A universal assertion contract under `src/dungeonmind/contracts/`.
* Generic properties, state, mechanics bindings, lifecycle fields, chronology, or arbitrary metadata.
* Assertion-scoped relationships; relationships remain coarse in this slice.
* Label alternatives or multiple summaries.
* Assertion authoring, contribution generation, identity create/connect, graph publication, or graph mutation.
* Database migrations or normalized assertion tables.
* Rewriting or upgrading existing graph revisions.
* Source-body reads or `open_source` execution.
* Hermes or another network/model adapter.
* Field-level semantic-document generation or embedding changes.
* Product-surface changes.
* RulesIngestion, DungeonMindBuddy, DungeonMindServer, LandingPage, or deployment-repository changes.

---

## §4 Stored graph schema contract

### 4.1 Existing schema remains exact

`dm_union_graph_v1` retains its present shape and behavior:

```json
{
  "object_id": "obj:...",
  "kind": "...",
  "label": "...",
  "aliases": ["..."],
  "summary": "...",
  "evidence_ref_ids": ["ev:..."]
}
```

For v1, aliases and summary continue to share the object's coarse evidence set. Do not infer field provenance and do not rewrite v1 payloads into v2.

### 4.2 New `dm_union_graph_v2` node shape

A v2 node has this exact conceptual shape:

```json
{
  "object_id": "obj:item-sun-ledger",
  "kind": "artifact",
  "label": "The Sun Ledger",
  "evidence_ref_ids": ["ev:ledger-core-player"],
  "alias_assertions": [
    {
      "assertion_id": "asrt:ledger-alias-dawn",
      "alias": "Dawn Ledger",
      "evidence_ref_ids": ["ev:ledger-alias-player"]
    },
    {
      "assertion_id": "asrt:ledger-alias-debtbook",
      "alias": "Debtbook of the First Light",
      "evidence_ref_ids": ["ev:ledger-alias-gm"]
    }
  ],
  "summary_assertion": {
    "assertion_id": "asrt:ledger-summary-secret",
    "summary": "a brass-bound account that records the names owed to the buried sun",
    "evidence_ref_ids": ["ev:ledger-summary-gm"]
  }
}
```

The v2 node must not accept legacy `aliases` or `summary` keys. Pydantic's existing extra-forbid policy must reject mixed v1/v2 shapes.

### 4.3 Field semantics

* `object_id`, `kind`, and `label` remain the coarse identity shell.
* Node-level `evidence_ref_ids` support object existence and the primary label.
* Node-level core evidence is required and non-empty in v2.
* `alias_assertions` is zero or more independently grounded aliases.
* `summary_assertion` is absent or exactly one independently grounded summary.
* Every assertion has:

  * one opaque stable `assertion_id`;
  * one non-empty field value;
  * one or more unique evidence reference IDs.
* Assertion IDs are unique across all alias and summary assertions in one graph snapshot.
* Normalized duplicate alias values on the same object fail closed.
* Alias values may collide across different objects; existing ambiguity behavior applies after scoping.
* Assertions carry no direct visibility, campaign, confidence, authority, or lifecycle field.
* All referenced evidence IDs must exist in the graph snapshot.

### 4.4 Relationships

The v2 relationship shape remains the current relationship record:

```json
{
  "relationship_id": "rel:...",
  "subject_object_id": "obj:...",
  "predicate": "...",
  "object_object_id": "obj:...",
  "evidence_ref_ids": ["ev:..."]
}
```

Relationships remain coarse: both endpoint objects must survive core scoping and every relationship evidence reference must be admitted.

---

## §5 Reader and view behavior

### 5.1 Reader classes

Preserve `UnionGraphV1SnapshotReader` for exact compatibility.

Add:

* `UnionGraphV2SnapshotReader` — parses only `dm_union_graph_v2`;
* `VersionedUnionGraphSnapshotReader` — dispatches by exact `graph_schema` and rejects all unsupported schemas.

The versioned reader becomes the default reader for:

* `MindTurnService` when no reader is injected;
* curated fixture preflight;
* demo-host bootstrap and readiness parsing.

Do not make v1's class silently accept v2.

### 5.2 Internal object views

The existing downstream object shape must remain compatible:

* `aliases: list[str]` contains the current admitted aliases;
* `summary: str | None` contains the current admitted summary;
* `evidence_ref_ids` contains the evidence admitted for the currently retained object fields.

Schema-local assertion metadata may be carried on `GraphObjectView` only as internal/excluded fields so existing v1 `model_dump()` output and assembled context do not gain empty compatibility fields.

Required internal metadata:

* core identity evidence IDs;
* admitted alias assertion records;
* admitted summary assertion record.

Do not add a public `WorldObjectAssertion` or equivalent contract.

### 5.3 Schema-neutral traversal

Exact object lookup, mention resolution, relationship listing, and one-hop expansion operate on `ParsedGraphSnapshot` and must not instantiate a v1-only reader internally.

---

## §6 Scope and visibility behavior

### 6.1 V1 behavior

Keep the current v1 coarse projection exactly:

```text
all object evidence admitted → retain entire object
any object evidence hidden/broken/missing → hide entire object
```

Existing v1 tests are regression authority.

### 6.2 V2 core object behavior

For each v2 object:

```text
classify every core evidence_ref_id
all valid and in scope → retain object shell and primary label
otherwise → hide entire object
```

A hidden core object contributes no label, alias, summary, evidence, anchor, relationship endpoint, candidate resolution, or projection.

### 6.3 V2 alias behavior

For each alias assertion independently:

```text
all attached evidence valid and in scope → retain alias
otherwise → omit alias only
```

An omitted alias must not:

* enter `alias_index`;
* resolve a mention;
* appear in agent context;
* appear in `entity_brief`;
* appear in `entity_field_provenance`;
* add evidence or source anchors;
* expose its assertion ID, evidence IDs, source IDs, or value through public coverage or diagnostics.

### 6.4 V2 summary behavior

The summary follows the same all-evidence rule. An omitted summary leaves the object visible without a summary and leaks no indication that hidden summary text exists.

### 6.5 Evidence classification

Reuse the existing evidence → source artifact → source revision validation and the existing world/campaign/admissibility ordering.

* Player admissibility accepts only player-visible sources.
* GM admissibility may admit both player- and GM-visible sources.
* Out-of-scope assertion evidence silently omits the assertion.
* Scope-unknown assertion provenance omits the assertion and records only internal exclusion state.
* In-scope broken assertion provenance omits the assertion and may retain internal rejection detail.
* No assertion exclusion is copied wholesale into public `Coverage`.

Add an internal `assertion_exclusions` map to the scoped projection, keyed by assertion ID, for tests and diagnostics inside DungeonMind only.

### 6.6 Retained evidence

After scoping, retained graph evidence is the union of:

* retained object core evidence;
* retained alias assertion evidence;
* retained summary assertion evidence;
* retained relationship evidence.

No omitted assertion evidence remains in the scoped snapshot.

---

## §7 Semantic projections

### 7.1 Existing `entity_brief`

Keep the existing projection kind and surface-compatible fields:

```json
{
  "object_id": "obj:item-sun-ledger",
  "label": "The Sun Ledger",
  "kind": "artifact",
  "aliases": ["Dawn Ledger"],
  "summary": "... only when admitted ..."
}
```

For v1, payload behavior is unchanged.

For v2, aliases and summary are the scoped values only.

### 7.2 New `entity_field_provenance`

For each retained v2 object that has at least one admitted alias assertion or an admitted summary assertion, add one semantic projection:

```json
{
  "object_id": "obj:item-sun-ledger",
  "alias_assertions": [
    {
      "assertion_id": "asrt:ledger-alias-dawn",
      "alias": "Dawn Ledger",
      "evidence_ref_ids": ["ev:ledger-alias-player"]
    }
  ],
  "summary_assertion": {
    "assertion_id": "asrt:ledger-summary-secret",
    "summary": "a brass-bound account that records the names owed to the buried sun",
    "evidence_ref_ids": ["ev:ledger-summary-gm"]
  }
}
```

Rules:

* include only admitted assertions and admitted evidence IDs;
* omit `summary_assertion` entirely when it is not admitted;
* never emit an empty provenance projection;
* use a stable projection ID derived from request ID + object ID + projection kind;
* do not change `mind_turn_v1` or add layout vocabulary.

The B.1b browser may ignore this additive semantic projection. Its unknown-projection behavior is already fail-soft.

---

## §8 Synthetic proof fixture

Create `tests/fixtures/curated_assertion_scope_v1.json` using the existing curated fixture envelope and a unique synthetic world.

Required identifiers and values:

```text
fixture_version: curated_assertion_scope_v1
world_id: world:assertion-scope-demo
campaign_id: camp:assertion-scope
thread_id: thr:assertion-scope-demo
surface_id: test:assertion-scope
object_id: obj:item-sun-ledger
label: The Sun Ledger
player alias: Dawn Ledger
GM alias: Debtbook of the First Light
GM summary: a brass-bound account that records the names owed to the buried sun
```

Use two source artifacts:

* one player-visible artifact grounding the object core and player alias;
* one GM-visible artifact grounding the GM alias and GM summary.

Use separate player and GM semantic documents:

* the player document contains only the primary label and player alias;
* the GM document may contain the GM alias and summary;
* both map to the same graph object and exact graph revision;
* neither document contains text forbidden by its visibility.

Use unique embedding run, semantic document, source, revision, evidence, and assertion IDs. All prose must remain synthetic.

The fixture loader may gain an explicit `expected_fixture_version` parameter and must use the versioned graph reader. Its default call remains exactly compatible with `curated_mind_turn_v1`.

---

## §9 Required behavior matrix

| Case                                           | Player result                                      | GM result                                                             |
| ---------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------- |
| v1 object with mixed player/GM evidence        | Entire object hidden, unchanged from B.1a          | Object retained when all evidence is GM-admissible                    |
| v2 core player evidence                        | Object and primary label retained                  | Object and primary label retained                                     |
| v2 player alias                                | Alias retained and resolvable                      | Alias retained and resolvable                                         |
| v2 GM alias                                    | Omitted and not resolvable                         | Retained and resolvable                                               |
| v2 GM summary                                  | Omitted; object remains visible                    | Retained and available to agent/projection                            |
| v2 core GM-only evidence                       | Entire object hidden                               | Object retained                                                       |
| v2 assertion with mixed player+GM evidence     | Assertion omitted                                  | Assertion retained if all evidence valid                              |
| v2 assertion with missing or broken provenance | Assertion omitted; object retained; no public leak | Same fail-closed rule, with only authorized internal rejection detail |
| v2 relationship                                | Existing coarse relationship policy                | Existing coarse relationship policy                                   |
| unsupported schema                             | Persistence integrity failure                      | Persistence integrity failure                                         |

---

## §10 Idempotency, revision, and replay

* Existing v1 graph revisions remain immutable and readable.
* No migration or automatic v1→v2 conversion exists.
* A v2 graph revision ID remains content-addressed from its exact schema name and payload.
* The new fixture seeds idempotently: exact replay reuses the same graph head, source records, embedding run, documents, and thread.
* A conflicting fixture payload fails before replacing or rolling back an existing head.
* Exact player Mind Turn replay returns the identical response and does not invoke the agent twice.
* Exact GM Mind Turn replay returns the identical response and does not invoke the agent twice.
* Reusing a request ID with changed admissibility, message, or other authorized request fields remains an idempotency conflict.
* Field scoping is deterministic for one pinned revision and source state.

---

## §11 Files in scope — exact allowlist

| Action | Path                                                           | Purpose                                                                                 |
| ------ | -------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Create | `Docs/Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md`  | Canonical implementation authority                                                      |
| Modify | `Docs/Architecture/ARCHITECTURE.md`                            | Record v1 coarse compatibility and narrow v2 field admission                            |
| Modify | `Docs/Roadmaps/ROADMAP.md`                                     | Mark B.1b landed and name B.2a as the current DungeonMind-owned slice                   |
| Modify | `README.md`                                                    | Truthful current capability and non-goals                                               |
| Modify | `src/dungeonmind/application/graph_snapshot.py`                | v2 schema records, versioned reader, internal assertion views, schema-neutral traversal |
| Modify | `src/dungeonmind/application/graph_scope.py`                   | v1/v2 projection dispatch and assertion-level field admission                           |
| Modify | `src/dungeonmind/application/mind_turn.py`                     | default versioned reader and additive field-provenance projection                       |
| Modify | `src/dungeonmind/infrastructure/fixtures/curated_mind_turn.py` | versioned fixture validation and explicit fixture-version loading                       |
| Modify | `src/dungeonmind/service/bootstrap.py`                         | versioned reader in demo host/readiness                                                 |
| Create | `tests/fixtures/curated_assertion_scope_v1.json`               | Synthetic player/GM proof fixture                                                       |
| Create | `tests/unit/test_assertion_scoped_graph.py`                    | Parser, scoper, resolution, projection, leak, and v1 regression proof                   |
| Create | `tests/integration/test_assertion_scoped_mind_turn.py`         | PostgreSQL-backed seed, player/GM Mind Turn, and replay proof                           |

### Bounded discovery exception

None. If another path is required, stop and report before editing it.

### Explicitly forbidden paths

* `src/dungeonmind/contracts/**`
* `migrations/**`
* `src/dungeonmind/infrastructure/postgres/**`
* `src/dungeonmind/agents/**`
* `src/dungeonmind/service/api.py`
* `.github/workflows/**`
* existing B.1b browser assets
* any sibling repository

---

## §12 Work plan

1. **Check in this handoff as the first branch commit.**

   * Verify the base SHA and merged PR #5.
   * Verify no newer graph-schema or scoping PR supersedes it.

2. **Introduce the v2 parser without changing v1.**

   * Add exact schema-local alias/summary records.
   * Validate required evidence, dangling evidence, assertion uniqueness, and normalized alias uniqueness.
   * Add the version-dispatching reader.
   * Refactor traversal helpers only as required to be schema-neutral.

3. **Implement v2 field admission.**

   * Keep v1 coarse projection intact.
   * Retain core object shell only when core evidence is admitted.
   * Filter each alias and summary independently.
   * Rebuild scoped indexes from retained fields only.
   * Remove omitted assertion evidence from the scoped snapshot.

4. **Expose semantic field provenance.**

   * Preserve `entity_brief` for all schemas.
   * Add `entity_field_provenance` only for admitted v2 assertions.
   * Ensure omitted values and IDs are absent from every public response section.

5. **Make runtime graph parsing version-aware.**

   * Default Mind Turn reader.
   * Fixture preflight.
   * Demo bootstrap/readiness.
   * Preserve injected-reader seams and v1 behavior.

6. **Add the synthetic fixture and tests.**

   * Unit parser/scoper/leak tests.
   * PostgreSQL-backed player/GM service turns.
   * Exact replay and changed-scope conflict.
   * Existing v1 suite remains green.

7. **Synchronize architecture, roadmap, and README.**

   * Do not claim generic assertion support.
   * Name relationships/properties/state/mechanics as still coarse or deferred.

---

## §13 Acceptance gates

### 13.1 Core gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run pytest -m "not integration"
```

Expected: all pass. Importing core still requires no optional API, PostgreSQL, model, or sibling-repository dependency.

### 13.2 Focused unit gate

```bash
uv run pytest -q tests/unit/test_assertion_scoped_graph.py
```

The focused unit suite must prove at minimum:

* valid v2 parsing;
* mixed v1/v2 node shape rejection;
* missing core evidence rejection;
* dangling assertion evidence rejection;
* duplicate assertion ID rejection;
* duplicate normalized alias rejection on one object;
* player versus GM alias/summary admission;
* hidden alias cannot resolve;
* hidden text and IDs absent from scoped snapshot and projections;
* v1 coarse behavior remains exact.

### 13.3 PostgreSQL integration gate

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
uv run pytest -q tests/integration/test_assertion_scoped_mind_turn.py
uv run pytest -m integration
```

The focused integration test must prove:

**Player turn**

* exact v2 revision returned;
* object retained;
* `Dawn Ledger` retained;
* `Debtbook of the First Light` absent;
* secret summary text absent;
* no GM assertion/evidence/source identifiers anywhere in serialized response;
* `entity_field_provenance` maps only the player alias;
* answer does not use the secret summary.

**GM turn**

* same exact graph revision;
* player and GM aliases retained;
* secret summary retained;
* provenance projection maps all admitted assertions;
* GM evidence and anchors are admitted;
* answer may use the admitted summary.

**Replay**

* exact player and GM requests replay identically;
* agent invocation count does not increase on replay;
* changed admissibility under a reused request ID fails with idempotency conflict.

### 13.4 B.1 regression gates

```bash
uv run pytest -q tests/unit/test_graph_snapshot_reader.py
uv run pytest -q tests/unit/test_graph_scope_provenance.py
uv run pytest -q tests/unit/test_mind_turn_service.py
uv run pytest -q tests/unit/test_curated_mind_turn_surface_assets.py
DUNGEONMIND_DATABASE_URL=$DUNGEONMIND_DATABASE_URL \
  uv run pytest -q tests/integration/test_mind_turn_api.py
DUNGEONMIND_DATABASE_URL=$DUNGEONMIND_DATABASE_URL \
  uv run pytest -q tests/integration/test_curated_mind_turn_surface_contract.py
```

No manual browser rerun is required because the browser files and HTTP contract are unchanged.

### 13.5 Diff gates

```bash
git diff --check
git diff --name-only f94105f9bf547add2ca815a70f5fc9a8752d9531...HEAD
git diff --stat f94105f9bf547add2ca815a70f5fc9a8752d9531...HEAD -- \
  Docs/Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md \
  Docs/Architecture/ARCHITECTURE.md \
  Docs/Roadmaps/ROADMAP.md \
  README.md \
  src/dungeonmind/application/graph_snapshot.py \
  src/dungeonmind/application/graph_scope.py \
  src/dungeonmind/application/mind_turn.py \
  src/dungeonmind/infrastructure/fixtures/curated_mind_turn.py \
  src/dungeonmind/service/bootstrap.py \
  tests/fixtures/curated_assertion_scope_v1.json \
  tests/unit/test_assertion_scoped_graph.py \
  tests/integration/test_assertion_scoped_mind_turn.py
```

No migration file, public contract file, PostgreSQL adapter, agent adapter, API endpoint, workflow, browser asset, or sibling-repository path may change.

---

## §14 Leak audit

For the player response, serialize the entire `MindTurnResponse` and assert that none of these appear anywhere:

* GM alias text;
* GM summary text;
* GM assertion IDs;
* GM evidence IDs;
* GM source artifact IDs;
* GM source revision IDs;
* GM locators or URIs.

Run the same search against:

* assembled agent context;
* resolved referents;
* claims;
* evidence;
* source anchors;
* source reads;
* semantic projections;
* suggested actions;
* context changes;
* coverage;
* diagnostics.

Do not satisfy this audit by renaming fixture strings after the fact. The prohibited values must remain explicit test sentinels.

---

## §15 Stop conditions

Stop and report rather than expanding scope if:

1. Current `main` differs materially from base `f94105f` in graph parsing, scoping, or Mind Turn projection behavior.
2. Supporting v2 requires changing a public contract or database schema.
3. Existing v1 revisions cannot remain byte-for-byte and behaviorally compatible.
4. Internal assertion metadata cannot be excluded from existing v1 object dumps and agent context.
5. A hidden alias enters an alias/label index before or after scoping.
6. Any hidden field value or provenance identifier reaches a player response, context, coverage, or diagnostic.
7. The implementation needs direct assertion visibility/campaign fields instead of deriving scope from evidence.
8. A generic assertion/property/world-object abstraction becomes necessary.
9. The proof requires player semantic documents to contain GM-only text.
10. The fixture cannot be seeded idempotently through existing repositories.
11. A migration, PostgreSQL adapter change, API endpoint, agent change, workflow change, or sibling-repository edit appears necessary.
12. A path outside §11 is required.
13. Any existing B.1a/B.1b gate regresses.
14. The work begins implementing assertion authoring or graph writes.
15. Any founding-charter §15 condition applies.

Use this exact stop report:

```text
Stop condition:
Discovered fact:
Affected invariant:
Why B.2a cannot absorb it:
Evidence and failing path:
Safe work completed:
Work not attempted:
Options:
Recommended resolution:
Operator decision required:
```

---

## §16 Acceptance rubric

The reviewer accepts only when every item is true:

* [ ] `dm_union_graph_v1` behavior and stored revisions are unchanged.
* [ ] `dm_union_graph_v2` is a distinct exact schema, not a permissive extension.
* [ ] V2 core object evidence remains coarse and required.
* [ ] Each alias and the summary are scoped independently from their evidence.
* [ ] Assertions have no direct visibility, campaign, confidence, or authority fields.
* [ ] Hidden aliases do not participate in identity resolution.
* [ ] Hidden fields and provenance identifiers are absent from the complete player envelope and agent context.
* [ ] Omitted assertion evidence is absent from the scoped snapshot.
* [ ] Relationships remain coarse and unchanged.
* [ ] Existing `entity_brief` remains surface-compatible.
* [ ] `entity_field_provenance` contains only admitted assertions and evidence IDs.
* [ ] The default service/bootstrap path can read v1 and v2.
* [ ] Existing v1 fixture loading and seeding remain compatible.
* [ ] The new fixture is synthetic, unique, and idempotent.
* [ ] Player and GM turns operate against the same exact v2 graph revision.
* [ ] Exact replay remains deterministic and skips duplicate agent execution.
* [ ] No public contract, migration, PostgreSQL adapter, agent, endpoint, workflow, browser asset, or sibling repository changed.
* [ ] All focused, core, integration, and regression gates pass.
* [ ] Documentation states the narrow capability and the remaining false states truthfully.

---

## §17 Required implementation handback

The PR body or handback must include:

1. Repository, branch, base SHA, head SHA, PR number, and status.
2. Exact changed paths and diff stat.
3. A concise schema decision record:

   * why v2 was added;
   * why v1 was not edited;
   * why assertions derive scope from evidence;
   * why no generic assertion contract was introduced.
4. The exact v2 fixture matrix and identifiers.
5. Player and GM response summaries at the same revision.
6. Full leak-audit sentinel list and result.
7. Every §13 command with exact result and provenance.
8. Exact replay/agent invocation evidence.
9. Confirmation that existing v1 model dumps and projection payloads did not change.
10. Confirmation that Alembic heads and migrations are unchanged.
11. Paths outside allowlist: `none` or a stop report.
12. Baseline failures/waivers: `none` or exact base/head evidence.
13. Stop conditions encountered: `none` or exact report.
14. What remains false:

    * generic field/property assertion model;
    * assertion-scoped relationships;
    * state/lifecycle/mechanics provenance;
    * assertion authoring and graph writes;
    * field-level semantic-document materialization;
    * source opening;
    * Hermes;
    * external product-surface adoption.
15. Named successors:

    * a concrete next field/relationship provenance slice only when demanded by a real consumer;
    * admitted source opening after body/excerpt semantics are designed;
    * external RulesIngestion PR C in its owning repository.

---

## §18 Reviewer protocol

1. Reconstruct the mission before reading code: visible object shell, independently scoped aliases and summary, no generic model.
2. Confirm the base is merged PR #5 at `f94105f` or an explicitly re-anchored successor.
3. Compare v1 parser/scoper outputs before and after; treat any change as a blocker unless proven non-observable and necessary.
4. Inspect v2 validation for mixed shapes, required evidence, dangling refs, duplicate assertion IDs, and duplicate aliases.
5. Trace player scope in this order:

   * core evidence;
   * alias evidence;
   * summary evidence;
   * scoped indexes;
   * mention resolution;
   * retained evidence;
   * context;
   * projections;
   * full response.
6. Search the complete player response and context for every GM sentinel.
7. Verify GM receives both player- and GM-admissible fields at the same revision.
8. Confirm relationship behavior remains coarse.
9. Confirm the projection vocabulary is semantic, not layout-specific.
10. Confirm internal assertion fields do not alter v1 model dumps.
11. Run exact replay and changed-admissibility conflict cases.
12. Verify no migration or public contract changed.
13. Compare every changed path to §11.
14. Reject any claim that this PR delivers generic world objects, authoring, source opening, or production readiness.

---

## §19 Definition of done

B.2a is complete when DungeonMind can read one `dm_union_graph_v2` revision and safely project the same grounded object differently for player and GM admissibility: the player keeps the visible object shell and player alias while receiving none of the GM alias, summary, or provenance; the GM receives all admitted fields; both remain pinned to the same immutable revision; v1 behavior remains exact; and no write path, generic assertion framework, migration, or sibling-repository dependency has been introduced.
