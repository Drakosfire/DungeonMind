# HANDOFF — B.2b Semantic Profile Boundary

**Created:** 2026-08-01
**Status:** ACTIVE — dispatch exactly one DungeonMind implementation capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b2b-semantic-profile-boundary.md`
**Repository / suggested branch:** `Drakosfire/DungeonMind` / `founding/pr-b2b-semantic-profile-boundary`
**Implementation base:** `9374b987ead22bd12945ec7827a91d8f24e4cf70`
**Predecessor:** merged PR `#6` — B.2a Assertion-scoped alias and summary read projection
**One-line mission:** Draw the permanent boundary between the DungeonMind kernel and game-system meaning by adding one explicitly versioned graph schema whose object kinds and relationship predicates are qualified, opaque terms admitted by an exact, digest-pinned semantic profile — proven against a non-D&D synthetic profile — without placing any D&D mechanics or taxonomy in the kernel.

---

## §0 Capability decomposition decision

PRs A through B.2a have proven the complete governed read seam:

```text
immutable graph revision (v1 coarse, v2 assertion-scoped)
→ scoped retrieval and evidence admission
→ read-only Mind Turn
→ HTTP contract
→ real browser consumer
```

Both stored schemas carry open, unqualified `kind` and `predicate` strings.
The kernel treats them as opaque, and nothing records which vocabulary they
belong to. The next approaching consumer (DungeonMindBuddy Threat/statblock
work) brings a D&D-flavored taxonomy. The cheapest way to serve it — D&D
enums in kernel contracts — would make the first consumer the universal
ontology and couple every future game system to a boundary violation that
cannot be undone without rewriting published revisions.

This slice proves one narrower permanent behavior instead:

```text
graph payload pins an exact semantic profile (id + revision + digest)
kernel resolves the profile from generic operator config
kernel admits or rejects qualified namespace:local terms
kernel never interprets the terms and never imports the profile package
D&D semantics live in a data-only sibling package
```

The checked-in roadmap's next numbered external rung, PR C, belongs to
`RulesIngestion`. This handoff is the next **DungeonMind-owned** capability.
PR C may proceed independently in its owning repository; this PR must not
import, edit, or emulate it.

### Selected capability

**B.2b — semantic profile boundary and `dm_union_graph_v3`.**

### Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Put D&D enums in core now | Reject | Makes first consumer the universal ontology |
| Keep open unqualified strings forever | Reject for V3 | Ownership remains ambiguous |
| Add profile fields to V2 | Reject | Published schemas are immutable |
| Add profile fields to graph-revision envelope v1 | Reject | Would silently change a durable contract |
| Store descriptor filesystem path in graph | Reject | Deployment path is not durable identity |
| Embed the whole descriptor in every graph | Reject for now | Duplicates profile history and weakens package ownership |
| Load executable plugins by import path | Reject | Too broad and unsafe |
| Create a separate repository now | Defer | Breaks atomicity before operational need |
| Build universal ontology interpretation now | Defer | No second-system evidence |

### Governing invariant

```text
DungeonMind is a governed semantic kernel, not the owner of D&D meaning.
For dm_union_graph_v3, a graph payload carries one exact semantic profile
reference — profile_id + profile_revision + descriptor_sha256. Every node
kind and relationship predicate is a qualified namespace:local term whose
namespace the pinned descriptor admits. Descriptor location is local
configuration; identity is the pinned ref. V1 and V2 remain immutable and
unqualified. The kernel resolves profiles through a registry port and never
imports a profile package.
```

### Mission falsification test

```text
This is no longer one PR if it requires D&D mechanics contracts in the
kernel, a generic ontology interpreter, executable plugin loading, a change
to any published contract or stored v1/v2 revision, a database migration,
a new HTTP endpoint, a sibling-repository change, or a graph payload that
stores a filesystem path.
```

---

## §1 Mission

Add one explicitly versioned stored graph schema, `dm_union_graph_v3`, in
which:

* the graph payload pins one exact semantic profile by identity and digest;
* object kinds and relationship predicates are qualified, opaque semantic
  terms admitted by that profile's descriptor;
* profile resolution flows through a generic registry port fed by local
  operator configuration;
* D&D 5e profile data ships in a data-only sibling package,
  `dungeonmind_dnd`, in the same repository and wheel, with a strictly
  one-way dependency;
* a synthetic non-D&D profile (`test.narrative`) proves the boundary, so
  the canary demonstrates decoupling rather than D&D product support.

This is independently useful because it makes semantic ownership explicit
and durable before the first game-system consumer arrives, without opening
a write path, interpreting any term, or claiming multi-system support.

---

## §2 Product and architectural outcome

After this PR:

```text
dm_union_graph_v3 revision
→ exact semantic-profile ref in the graph payload
→ qualified opaque semantic terms (namespace:local)
→ generic registry port + local registry config
→ DungeonMindDnD sibling data package (one-way)
→ non-D&D canary fixture proving the boundary end to end
```

A reader can parse one exact v3 revision and:

* resolve the pinned profile descriptor from configured registry data;
* verify descriptor identity and digest against the stored ref;
* admit kinds/predicates whose namespaces the descriptor admits;
* reject unknown profiles, tampered descriptors, and unadmitted namespaces
  as persistence-integrity failures;
* project v3 through the same scoped read path as v2 (aliases and summary
  remain assertion-scoped; relationships remain coarse);
* replay player Mind Turns exactly at the pinned revision.

What does **not** change: v1/v2 payloads and behavior, every public durable
contract, the HTTP surface, the response projection vocabulary, migrations,
and agent adapters. GM/player/canon/session policy remains kernel policy
for now and is not claimed as universal TTRPG ontology.

---

## §3 Authority base and required reading

Read these in order before editing:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `Docs/Handoffs/HANDOFF-found-dungeonmind-repository.md` — especially §14–15
4. `CONTRIBUTING.md`
5. `Docs/Roadmaps/ROADMAP.md`
6. `Docs/Decisions/ADR-0001-database-selection.md`
7. `Docs/Decisions/ADR-0002-persistence-lifecycle-ownership.md`
8. `Docs/Decisions/ADR-0003-pgvector-derived-index.md`
9. merged PR `#6` — B.2a assertion-scoped alias/summary read projection
10. `Docs/Handoffs/HANDOFF-b2a-assertion-scoped-alias-summary.md`
11. `src/dungeonmind/application/graph_snapshot.py`
12. `src/dungeonmind/application/graph_scope.py`
13. `src/dungeonmind/application/mind_turn.py`
14. `src/dungeonmind/infrastructure/fixtures/curated_mind_turn.py`
15. `src/dungeonmind/service/bootstrap.py`
16. `tests/unit/test_import_boundaries.py`
17. `tests/unit/test_assertion_scoped_graph.py`
18. `tests/integration/test_assertion_scoped_mind_turn.py`

### Authority precedence

```text
1. Current checked-in DungeonMind code, contracts, ADRs, and architecture
2. Merged repository state at 9374b987ead22bd12945ec7827a91d8f24e4cf70
3. This checked-in handoff
4. Existing tests and synthetic fixtures
5. Project Sources and chat summaries
```

If `main` has moved, re-anchor to the new merge commit and confirm no merged
or open DungeonMind PR already changes graph-schema parsing, graph scoping,
profile resolution, or Mind Turn projection semantics.

DungeonMindBuddy Threat/statblock documents are **consumer requirements**,
not authority to place D&D mechanics in the kernel.

---

## §4 Existing-boundary audit and required extraction

Audit before adding anything:

* `kind` and `predicate` are free-form strings in v1/v2 stored payloads and
  fixture vocabulary. That vocabulary is fixture-local; it is **not** a
  canonical taxonomy and must not be promoted into kernel enums.
* No kernel module may gain a D&D-specific type, enum, predicate list, or
  mechanics rule. Any existing assumption that a kind or predicate is
  meaningful to the kernel is a defect to report, not a pattern to extend.
* Response projection kinds (`entity_brief`, `entity_field_provenance`)
  remain kernel-owned; they project admitted field values and never
  interpret qualified terms.
* Extraction required: semantic-term ownership moves out of the kernel into
  (a) a versioned, data-only profile descriptor contract and (b) a sibling
  `dungeonmind_dnd` package holding the D&D 5e descriptor as package data.

---

## §5 Ownership boundary

| Concern | Owner |
| --- | --- |
| Graph identity, revisions, evidence, retrieval, admission, scoped projection | **DungeonMind kernel** |
| Semantic profile *identity model* (ref, descriptor shape, registry config contract, registry port) | **DungeonMind kernel** |
| D&D 5e profile *content* (descriptor file, its namespaces, its revisions) | **DungeonMindDnD** (`src/dungeonmind_dnd/`) |
| Which profiles a deployment loads, and where descriptors live on disk | **Operator configuration** (local registry config) |
| GM/player/canon/session audience policy | **DungeonMind kernel** (not claimed as universal TTRPG ontology) |
| Future D&D taxonomy/mechanics capability | **DungeonMindDnD** (future lane, not this slice) |

Hard rules:

* No code under `src/dungeonmind` imports `dungeonmind_dnd`.
* `dungeonmind_dnd` is data-only: no imports of `dungeonmind.application`,
  `dungeonmind.infrastructure`, or `dungeonmind.service`; no registration
  side effects at import.
* Local registry paths are never semantic authority and never appear in
  graph payloads, public responses, or error details.
* Profile descriptors are versioned checked-in artifacts, not chat or
  config authority.

---

## §6 Durable contracts

New additive contracts in `src/dungeonmind/contracts/semantic_profile.py`:

* **`dm_semantic_profile_ref_v1`** (`SemanticProfileRef`) — pinned identity:
  `profile_id` + `profile_revision` + `descriptor_sha256` (exactly 64
  lowercase hex). Rejects `latest`, whitespace, path separators, URIs, and
  module paths.
* **`dm_semantic_profile_v1`** (`SemanticProfileDescriptor`) — data-only
  profile: `profile_id` + `profile_revision` + non-empty unique lowercase
  `term_namespaces` (no `:`). No file paths, module names, URLs, hooks, or
  executable behavior.
* **`dm_semantic_profile_registry_config_v1`**
  (`SemanticProfileRegistryConfig` / `SemanticProfileRegistryEntry`) —
  operator config mapping `(profile_id, profile_revision)` to a relative
  `descriptor_path`. Paths are config-only locators, resolved relative to
  the config file; absolute paths and URIs are rejected.

Unchanged contracts: `mind_turn_v1`, `dm_graph_revision_v1`,
`dm_evidence_ref_v1`, and every other published durable contract. The
profile ref lives in the **graph payload**, not in the graph-revision
envelope.

New typed failures (`src/dungeonmind/domain/errors.py`), all subclasses of
`PersistenceIntegrityError`:

* `SemanticProfileNotFoundError` (`semantic_profile_not_found`)
* `SemanticProfileIntegrityError` (`semantic_profile_integrity_error`)
* `SemanticTermValidationError` (`semantic_term_validation_error`)

---

## §7 `dm_union_graph_v3`

One new stored graph schema identifier beside v1/v2.

### 7.1 Payload shape

A v3 payload reuses the exact v2 node, relationship, and evidence shapes
(assertion-scoped aliases and one optional summary; coarse relationships)
and adds one required field at the payload root:

```json
{
  "world_id": "world:...",
  "semantic_profile": {
    "schema_version": "dm_semantic_profile_ref_v1",
    "profile_id": "test.narrative",
    "profile_revision": "narrative-profile-v1",
    "descriptor_sha256": "95edd343644e7a8dad7416d0002e6788c3782108f558f9b326550b4f2205ee78"
  },
  "nodes": [
    {
      "object_id": "obj:clock-buried-sun",
      "kind": "narrative:clock",
      "label": "The Buried Sun Clock",
      "evidence_ref_ids": ["ev:clock-core-player"],
      "alias_assertions": [],
      "summary_assertion": null
    }
  ],
  "relationships": [
    {
      "relationship_id": "rel:clock-advances-outcome",
      "subject_object_id": "obj:clock-buried-sun",
      "predicate": "narrative:advances_toward",
      "object_object_id": "obj:outcome-dawn-debt",
      "evidence_ref_ids": ["ev:clock-advances-player"]
    }
  ],
  "evidence_refs": ["... dm_evidence_ref_v1 records ..."]
}
```

### 7.2 Term rules

* Every node `kind` and relationship `predicate` is a qualified term:
  `namespace:local`, lowercase, exactly one colon, both sides matching
  `[a-z0-9]+([._-][a-z0-9]+)*`.
* The term's namespace must appear in the pinned descriptor's
  `term_namespaces`; otherwise parsing fails with
  `semantic_term_validation_error`.
* Terms are opaque: the kernel validates shape and admission only. No
  interpretation, expansion, or cross-namespace reasoning exists.

### 7.3 Reader behavior

* `UnionGraphV3SnapshotReader` parses only `dm_union_graph_v3`; it requires
  `semantic_profile`, validates the ref, resolves the descriptor through
  the injected `SemanticProfileRegistry`, and verifies identity and digest
  before admitting terms.
* `VersionedUnionGraphSnapshotReader` dispatches v1/v2/v3 by exact
  `graph_schema` and rejects all unsupported schemas. It accepts an
  optional profile registry; the default registry is empty, so v3 reads
  fail closed with `semantic_profile_not_found` when no registry is
  configured. There is no silent default to `dungeonmind.dnd5e`.
* V1 and V2 payloads reject a `semantic_profile` field; v1/v2 revisions
  remain byte-for-byte readable with unchanged behavior, and their parsed
  snapshots carry null profile fields.
* Scoped projection treats v3 exactly like v2 (object shell plus
  independently admitted aliases and summary) and carries the profile ref
  and descriptor through the scoped snapshot for internal use.

---

## §8 Registry and failure model

* `SemanticProfileRegistry` is an application port:
  `get(profile_id, profile_revision) -> SemanticProfileDescriptor | None`.
* `StaticSemanticProfileRegistry` — in-memory; rejects duplicate identities;
  returns deep copies.
* `FilesystemSemanticProfileRegistry` — loads a
  `dm_semantic_profile_registry_config_v1` file, resolves each relative
  `descriptor_path` against the config file location (parent segments
  allowed), validates each descriptor, and rejects duplicate identities and
  identity mismatches. Malformed configs or descriptors fail closed at load
  time.
* The demo host builds its registry from
  `DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH`; absent the variable, the
  registry is empty and v3 fails closed. The configured reader is shared by
  the service, fixture preflight, and readiness.
* Failure model:

| Condition | Failure |
| --- | --- |
| Profile identity absent from registry | `semantic_profile_not_found` |
| Descriptor unreadable / invalid JSON / failed validation | `semantic_profile_integrity_error` |
| Descriptor identity mismatch with registry entry or stored ref | `semantic_profile_integrity_error` |
| Descriptor digest mismatch with stored ref | `semantic_profile_integrity_error` |
| Duplicate profile identity in config or static registry | `semantic_profile_integrity_error` |
| Missing `semantic_profile` on v3 payload | persistence integrity failure |
| `semantic_profile` present on v1/v2 payload | persistence integrity failure |
| Unqualified or unadmitted kind/predicate | `semantic_term_validation_error` |

* No failure message, detail payload, API error, or log includes local
  filesystem paths.

---

## §9 DungeonMindDnD initial package

* `src/dungeonmind_dnd/` ships in the same repository and wheel as
  `src/dungeonmind` (one distribution, two one-way packages; the descriptor
  JSON is force-included as package data).
* The package docstring states the rule: importing it is side-effect free;
  it registers nothing; the kernel never imports it.
* Initial content is exactly one descriptor,
  `dungeonmind_dnd/profiles/dnd5e-v1.json`:

```json
{
  "schema_version": "dm_semantic_profile_v1",
  "profile_id": "dungeonmind.dnd5e",
  "profile_revision": "dnd5e-profile-v1",
  "term_namespaces": ["dnd5e"]
}
```

  Digest: `582851c0fc41897fff5a57a4fd6dd7fb7078b865315a30bc21552c82e7596967`.
* This package owns D&D 5e profile semantics only. It contains no taxonomy,
  no mechanics, and no contracts. Concrete D&D semantics are a named future
  lane.
* Any later repository or package extraction must preserve profile
  identities and descriptor bytes so every stored graph reference remains
  exactly resolvable.

---

## §10 Fixtures and complete proof

### 10.1 Canary descriptor

`tests/fixtures/semantic_profiles/test-narrative-v1.json`:

```json
{
  "schema_version": "dm_semantic_profile_v1",
  "profile_id": "test.narrative",
  "profile_revision": "narrative-profile-v1",
  "term_namespaces": ["narrative"]
}
```

Digest: `95edd343644e7a8dad7416d0002e6788c3782108f558f9b326550b4f2205ee78`.

### 10.2 Curated v3 fixture

`tests/fixtures/curated_semantic_profile_v1.json` uses the existing curated
fixture envelope and a unique synthetic world:

```text
fixture_version: curated_semantic_profile_v1
world_id: world:semantic-profile-demo
campaign_id: camp:semantic-profile
thread_id: thr:semantic-profile-demo
surface_id: test:semantic-profile
graph_schema: dm_union_graph_v3
profile: test.narrative / narrative-profile-v1 (digest-pinned)
object: obj:clock-buried-sun, kind narrative:clock, label The Buried Sun Clock
player alias: Dawn Clock
player summary: a public countdown toward settling the dawn debt
object: obj:outcome-dawn-debt, kind narrative:outcome, label Dawn Debt Settled
relationship: rel:clock-advances-outcome, predicate narrative:advances_toward
```

All prose is synthetic and player-visible. Leak sentinels are explicit:
forbidden terms `dnd5e`, `creature`, `statblock`, `dungeonmind.dnd5e`;
forbidden path fragments `semantic_profiles`, `test-narrative-v1.json`,
`descriptor_path`.

The canary is the proof subject on purpose: the kernel demonstrating v3
against a non-D&D profile proves decoupling. It does not prove — and must
not be read as — multi-game product support.

### 10.3 Required proof points

* v3 parse resolves the pinned profile and admits qualified terms.
* Scoped projection preserves profile fields; v3 follows v2 field admission.
* Unadmitted namespace, unknown profile, tampered descriptor, identity
  mismatch, duplicate identity, missing profile field, and v1/v2 profile
  field injection all fail closed.
* Descriptor relocation with an updated config path preserves identity;
  changed bytes change the digest and fail verification.
* No registry configured → v3 read fails closed; v1/v2 remain usable.
* Import boundaries: nothing under `src/dungeonmind` imports
  `dungeonmind_dnd`; `dungeonmind_dnd` stays data-only.
* PostgreSQL-backed Mind Turn at one exact v3 revision: publish, player
  turn, exact replay, and fresh retrieval-session reconstruction; missing
  profile blocks the turn; tampered profile blocks without path leak.
* Complete serialized player responses contain no forbidden terms and no
  path fragments.
* Fixture digests in the fixture files match the descriptors on disk.
* The fixture seeds idempotently and preflights through the versioned
  reader with the configured registry.

---

## §11 Files in scope — exact allowlist

| Action | Path | Purpose |
| --- | --- | --- |
| Create | `Docs/Handoffs/HANDOFF-b2b-semantic-profile-boundary.md` | Canonical implementation authority |
| Create | `Docs/Decisions/ADR-0004-semantic-profile-boundary.md` | Boundary decision record |
| Create | `src/dungeonmind/contracts/semantic_profile.py` | Ref, descriptor, and registry-config contracts |
| Create | `src/dungeonmind/application/semantic_profiles.py` | Registry port, digest, qualified-term parsing/admission |
| Create | `src/dungeonmind/infrastructure/semantic_profiles.py` | Static and filesystem registry adapters |
| Create | `src/dungeonmind_dnd/__init__.py` | Data-only sibling package marker |
| Create | `src/dungeonmind_dnd/profiles/dnd5e-v1.json` | D&D 5e profile descriptor (package data) |
| Create | `tests/fixtures/semantic_profiles/test-narrative-v1.json` | Non-D&D canary descriptor |
| Create | `tests/fixtures/curated_semantic_profile_v1.json` | Synthetic v3 proof fixture |
| Create | `tests/unit/test_semantic_profile_contracts.py` | Contract and digest proof |
| Create | `tests/unit/test_semantic_profile_registry.py` | Registry adapters, relocation, tamper proof |
| Create | `tests/unit/test_semantic_profile_graph.py` | v3 parse/scope/failure and v1/v2 regression proof |
| Create | `tests/integration/test_semantic_profile_mind_turn.py` | PostgreSQL-backed v3 Mind Turn and replay proof |
| Create | `examples/semantic_profiles/registry.json` | Local composition example config |
| Create | `examples/semantic_profiles/README.md` | Locator-vs-identity operator note |
| Modify | `src/dungeonmind/application/graph_snapshot.py` | v3 schema records, v3 reader, versioned dispatch |
| Modify | `src/dungeonmind/application/graph_scope.py` | v3 scoped projection parity with v2 |
| Modify | `src/dungeonmind/domain/errors.py` | Typed semantic profile failures |
| Modify | `src/dungeonmind/infrastructure/fixtures/curated_mind_turn.py` | Registry-aware fixture preflight/loading |
| Modify | `src/dungeonmind/service/bootstrap.py` | Configured registry wiring from env var |
| Modify | `tests/unit/test_import_boundaries.py` | One-way dependency and data-only enforcement |
| Modify | `pyproject.toml` | Ship both packages plus descriptor package data |
| Modify | `Docs/Architecture/ARCHITECTURE.md` | v3 schema, profile layer, ownership rows |
| Modify | `Docs/Architecture/AUTHORITY.md` | ADR-0004 and profile authority boundaries |
| Modify | `Docs/Roadmaps/ROADMAP.md` | B.2b current slice and future lanes |
| Modify | `README.md` | Truthful capability, repository map, non-goals |
| Modify | `CONTRIBUTING.md` | Boundary hard rules |

### Bounded discovery exception

None. If another path is required, stop and report before editing it.

### Explicitly forbidden paths

* existing files under `src/dungeonmind/contracts/**` (published contracts
  are immutable; only the one new additive module above may be created)
* `migrations/**`
* `src/dungeonmind/infrastructure/postgres/**`
* `src/dungeonmind/agents/**`
* `src/dungeonmind/service/api.py`
* `.github/workflows/**`
* existing B.1b browser assets
* any sibling repository

---

## §12 Explicitly out of scope

* D&D mechanics, statblocks, threat calculation, or any game rule.
* Any D&D enum, kind list, predicate list, or taxonomy in the kernel.
* A generic ontology/taxonomy interpreter or cross-profile mapping.
* Executable plugins, hooks, or import-path loading of behavior.
* Changes to `mind_turn_v1`, `dm_graph_revision_v1`, `dm_evidence_ref_v1`,
  or any other published contract.
* Rewriting, migrating, or reinterpreting existing v1/v2 revisions.
* New response projection kinds or layout vocabulary; current response
  projection kinds remain kernel-owned.
* Assertion authoring, contributions, graph writes, or publication changes.
* Database migrations or normalized semantic-term tables.
* Source-body reads or `open_source` execution.
* Hermes or another network/model adapter.
* Multi-game or multi-system product support claims.
* A separate repository or distribution for `dungeonmind_dnd` (deferred).
* Product-surface changes; RulesIngestion, DungeonMindBuddy,
  DungeonMindServer, LandingPage, or deployment-repository changes.
* Generalizing GM/player/canon/session audience policy into profile data.

---

## §13 Atomic documentation sync

This PR is not mergeable unless the same branch updates, in the same
reviewable diff:

1. `Docs/Decisions/ADR-0004-semantic-profile-boundary.md` — the decisions
   and rejected alternatives recorded exactly once.
2. `Docs/Architecture/ARCHITECTURE.md` — semantic-profile layer, ownership
   rows for DungeonMind and DungeonMindDnD, the one-way dependency rule, the
   v3 summary beside v1/v2 in §6.1, qualified-term behavior, locator-versus-
   identity, the future interpretation insertion point, and the truthful
   "does not exist yet" list.
3. `Docs/Architecture/AUTHORITY.md` — ADR-0004 in the authority set;
   DungeonMindDnD authoritative only for D&D profile semantics; descriptors
   as checked-in artifacts; registry paths never authority.
4. `Docs/Roadmaps/ROADMAP.md` — B.2a landed; B.2b the current slice; named
   future lanes without dates; PR C/D/E/F ownership preserved.
5. `README.md` — B.2b capability, repository map, kernel-versus-profile
   paragraph, one-distribution/two-packages note, and non-goals.
6. `CONTRIBUTING.md` — the boundary hard rules.

No documentation may claim interpretation, mechanics, or multi-system
support.

---

## §14 Verification commands

### 14.1 Core gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run pytest -m "not integration"
```

Expected: all pass. Importing the kernel still requires no optional API,
PostgreSQL, model, profile-package, or sibling-repository dependency.

### 14.2 Focused unit gates

```bash
uv run pytest -q tests/unit/test_semantic_profile_contracts.py
uv run pytest -q tests/unit/test_semantic_profile_registry.py
uv run pytest -q tests/unit/test_semantic_profile_graph.py
uv run pytest -q tests/unit/test_import_boundaries.py
```

### 14.3 PostgreSQL integration gate

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
uv run pytest -q tests/integration/test_semantic_profile_mind_turn.py
uv run pytest -m integration
```

### 14.4 Regression gates

```bash
uv run pytest -q tests/unit/test_graph_snapshot_reader.py
uv run pytest -q tests/unit/test_graph_scope_provenance.py
uv run pytest -q tests/unit/test_assertion_scoped_graph.py
uv run pytest -q tests/unit/test_mind_turn_service.py
uv run pytest -q tests/unit/test_curated_fixture.py
uv run pytest -q tests/unit/test_seed_preflight.py
DUNGEONMIND_DATABASE_URL=$DUNGEONMIND_DATABASE_URL \
  uv run pytest -q tests/integration/test_mind_turn_api.py
DUNGEONMIND_DATABASE_URL=$DUNGEONMIND_DATABASE_URL \
  uv run pytest -q tests/integration/test_assertion_scoped_mind_turn.py
DUNGEONMIND_DATABASE_URL=$DUNGEONMIND_DATABASE_URL \
  uv run pytest -q tests/integration/test_curated_mind_turn_surface_contract.py
```

### 14.5 Diff gates

```bash
git diff --check
git diff --name-only 9374b987ead22bd12945ec7827a91d8f24e4cf70...HEAD
```

Every changed path must appear in §11. No migration file, published contract
file, PostgreSQL adapter, agent adapter, API endpoint, workflow, browser
asset, or sibling-repository path may change.

---

## §15 Acceptance rubric

The reviewer accepts only when every item is true:

* [ ] `dm_union_graph_v1` and `dm_union_graph_v2` payloads, behavior, and
  stored revisions are unchanged, and both reject a `semantic_profile`
  field.
* [ ] `dm_union_graph_v3` is a distinct exact schema: v2-shaped nodes plus
  one required, digest-verified `semantic_profile` ref in the payload.
* [ ] The profile ref is pinned identity (`profile_id` +
  `profile_revision` + `descriptor_sha256`), never a path, URI, module, or
  `latest`.
* [ ] Every v3 kind and predicate is a qualified `namespace:local` term
  admitted by the pinned descriptor; all other terms fail closed.
* [ ] Descriptor location is config-only; no graph payload, public
  response, error detail, or log contains a filesystem path.
* [ ] The default registry is empty: with no configuration, v3 fails closed
  and v1/v2 remain usable; there is no silent default to
  `dungeonmind.dnd5e`.
* [ ] No code under `src/dungeonmind` imports `dungeonmind_dnd`, and
  `dungeonmind_dnd` stays data-only; both rules are enforced by tests.
* [ ] The D&D 5e descriptor ships as package data in the same wheel with
  the recorded identity and digest.
* [ ] The proof fixture is synthetic, unique, idempotent, and pins the
  non-D&D `test.narrative` profile.
* [ ] Forbidden-term and path-fragment sentinels appear nowhere in the
  complete serialized player response.
* [ ] Player Mind Turns at one exact v3 revision replay identically, and a
  fresh process reconstructs the retrieval session.
* [ ] Missing and tampered profiles block turns without leaking paths.
* [ ] Relocating a descriptor file preserves identity; altering bytes
  changes the digest and fails verification.
* [ ] No published contract, migration, PostgreSQL adapter, agent adapter,
  endpoint, workflow, browser asset, or sibling repository changed.
* [ ] All focused, core, integration, and regression gates pass.
* [ ] Documentation states the narrow capability and the remaining false
  states truthfully, including "no interpretation layer exists".

---

## §16 Stop conditions

Stop and report rather than expanding scope if:

1. Current `main` differs materially from base `9374b98` in graph parsing,
   scoping, or Mind Turn projection behavior.
2. Supporting v3 requires changing a published contract, a stored v1/v2
   revision, or a database schema.
3. The profile ref cannot live in the graph payload without touching the
   `dm_graph_revision_v1` envelope.
4. Qualified-term admission cannot be proven without interpreting terms.
5. Any kernel module needs to import `dungeonmind_dnd`, or
   `dungeonmind_dnd` needs executable behavior.
6. A filesystem path or registry location would reach a graph payload,
   public response, or error detail.
7. The proof requires D&D content, real game rules, or non-synthetic prose.
8. A generic ontology interpreter, plugin loader, or cross-profile mapping
   becomes necessary.
9. GM/player/canon/session policy must move into profile data to land this.
10. The fixture cannot be seeded idempotently through existing
    repositories.
11. A migration, PostgreSQL adapter change, API endpoint, agent change,
    workflow change, or sibling-repository edit appears necessary.
12. A path outside §11 is required.
13. Any existing A–B.2a gate regresses.
14. Any founding-charter §15 condition applies.

Use this exact stop report:

```text
Stop condition:
Discovered fact:
Affected invariant:
Why B.2b cannot absorb it:
Evidence and failing path:
Safe work completed:
Work not attempted:
Options:
Recommended resolution:
Operator decision required:
```

---

## §17 What remains false after merge

* D&D taxonomy, statblocks, threat math, or any concrete game semantics.
* A generic ontology or profile interpretation layer.
* Cross-profile mapping, aliasing, or translation.
* Executable profile behavior, hooks, or plugins.
* Multi-game or multi-system product support.
* A separate repository or distribution for `dungeonmind_dnd`.
* Generalized audience policy (GM/player/canon/session remains kernel
  policy, not claimed as universal TTRPG ontology).
* Assertion authoring and graph writes; assertion-scoped relationships.
* Source opening; Hermes; external product-surface adoption.
* Field-level semantic-document materialization.

---

## §18 Required PR handback

The PR body or handback must include:

1. Repository, branch, base SHA, head SHA, PR number, and status.
2. Exact changed paths and diff stat against
   `9374b987ead22bd12945ec7827a91d8f24e4cf70`.
3. A concise decision record: why a new schema (v3) instead of editing v2;
   why the ref lives in the payload rather than the revision envelope; why
   identity is digest-pinned rather than path-based; why the descriptor is
   data-only; why the canary is non-D&D.
4. Profile identity table: both profiles, revisions, namespaces, and
   descriptor digests.
5. The v3 fixture matrix and identifiers.
6. Player-turn summaries at the pinned revision, replay evidence, and
   agent-invocation counts.
7. Full sentinel list (forbidden terms and path fragments) with the
   serialized-response search result.
8. Every §14 command with exact result and provenance.
9. Confirmation that v1/v2 stored payloads, model dumps, and projection
   payloads did not change.
10. Confirmation that Alembic heads and migrations are unchanged.
11. Paths outside allowlist: `none` or a stop report.
12. Baseline failures/waivers: `none` or exact base/head evidence.
13. Stop conditions encountered: `none` or exact report.
14. What remains false (§17 verbatim).
15. Named successors:

    * DungeonMindDnD concrete semantics — the first real D&D
      taxonomy/mechanics capability, only when demanded by a real consumer;
    * a profile interpretation layer — only after a concrete second-system
      pressure proves what abstraction is needed;
    * audience-policy generalization — GM/player/canon assumptions
      revisited separately if a supported game requires it;
    * external RulesIngestion PR C in its owning repository.

---

## §19 Reviewer protocol

1. Reconstruct the mission before reading code: exact profile pin, qualified
   opaque terms, generic config-driven registry, data-only sibling package,
   non-D&D proof, no interpretation.
2. Confirm the base is merged PR #6 at `9374b98` or an explicitly
   re-anchored successor.
3. Diff v1/v2 parser and scoper outputs before and after; treat any change
   as a blocker unless proven non-observable and necessary.
4. Inspect the ref and descriptor contracts for locator rejection
   (`latest`, paths, URIs, modules) and digest shape.
5. Trace v3 parse in this order: schema dispatch → profile field required →
   ref validation → registry resolution → identity check → digest
   verification → kind admission → predicate admission → v2-shaped node and
   evidence rules → scoped projection parity.
6. Verify the fail-closed default: no configured registry means v3 fails
   and v1/v2 still read.
7. Search the complete serialized player response, agent context, coverage,
   diagnostics, logs, and error details for every forbidden term and every
   path fragment.
8. Verify relocation preserves identity and tampering fails verification.
9. Confirm import-boundary tests cover both directions of the one-way rule.
10. Confirm the wheel includes both packages and the descriptor package
    data.
11. Run exact replay and fresh-reconstruction cases against one pinned v3
    revision.
12. Verify no published contract, migration, PostgreSQL adapter, agent,
    endpoint, workflow, browser asset, or sibling repository changed.
13. Compare every changed path to §11.
14. Reject any claim that this PR delivers D&D semantics, interpretation,
    multi-system support, authoring, or production readiness.

---

## §20 Definition of done

B.2b is complete when DungeonMind can read one `dm_union_graph_v3` revision
whose payload pins an exact semantic profile — resolving and verifying the
descriptor from generic operator configuration, admitting only qualified
terms the profile owns, and projecting player-scoped results through the
existing read path — while v1/v2 remain byte-for-byte unchanged, no kernel
code imports `dungeonmind_dnd`, no filesystem path escapes configuration,
the non-D&D canary proves the boundary end to end, and no interpretation,
mechanics, write path, migration, or sibling-repository dependency has been
introduced.
