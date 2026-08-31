# HANDOFF — K0.1: current consumer and public-surface inventory

**Created:** 2026-08-30  
**Status:** ACTIVE  
**Repository / branch:** `Drakosfire/DungeonMind` / `kernel/k0-consumer-public-surface-inventory`  
**PR base:** `steward/post-cutover-library-critique`  
**Base SHA:** `84a4479494a37d8b5bd550465d17ff29f0e359ec`  
**Code audit anchor:** DungeonMind `5ca5d688612349034f8ca490d465af166d883e6e`  
**External consumer anchor:** DungeonMindBuddy `a9d4c61d04f2a4a5f92cb6947442d8173079454c`, pinned to DungeonMind `5ca5d688612349034f8ca490d465af166d883e6e`  
**Predecessor:** `Docs/Reports/REPORT-2026-08-30-bottom-up-top-down-library-critique.md` and `Docs/Roadmaps/ROADMAP.md`  
**One-line mission:** Produce an exact, machine-checkable map of what current DungeonMind and DungeonMindBuddy actually consume, what exists only for durable historical compatibility, and what has no proven owner, so K1 demolition can remove only evidence-backed residue.

---

## §1 Outcome

K0.1 lands **no DungeonMind runtime behavior change**. It lands a reproducible point-in-time inventory, keyed to the exact DungeonMind and Buddy anchors above, that answers four demolition-safety questions:

1. What DungeonMind / `dungeonmind_dnd` modules and symbols does the real Buddy consumer import today?
2. What explicitly exported DungeonMind surface has no known external consumer at that anchor?
3. Which repository protocols and PostgreSQL tables participate in current World read/write/source/publication/initialization authority, and which exist only for founding/runtime or historical compatibility paths?
4. For each proposed demolition target, is the evidence sufficient to classify it `USED`, `UNUSED`, `HISTORICAL-COMPAT`, or `UNKNOWN`?

The PR produces both:

- a human-readable architecture report; and
- a deterministic JSON evidence ledger suitable for later K1 comparison and validation.

The output is **observational**, not a promise that every current export remains public forever. K0.1 must not accidentally turn the current museum of exports into a new compatibility contract.

Expected artifacts:

```text
scripts/k0_surface_inventory.py
Docs/Reports/REPORT-2026-08-30-k0-current-consumer-public-surface.md
Docs/Reports/K0-current-consumer-public-surface-v1.json
tests/unit/test_k0_surface_inventory.py
```

Equivalent names are acceptable only if the report, JSON ledger, generator, and tests remain obvious and colocated by purpose.

---

## §2 Authority and anchors

Read these in order before changing anything:

1. `Docs/Architecture/AUTHORITY.md`
   - current checked-in contracts/code/ADRs/architecture outrank historical reports;
   - Buddy is evidence of a real current consumer, not semantic authority;
   - historical adoption/source state remains durable authority where applicable.
2. `Docs/Architecture/ARCHITECTURE.md`
   - especially §2 agent-harness boundary, §3 invariants, §4 current public capability boundary, §5 persistence, §6 profiles, and §8 ownership map.
3. `Docs/Roadmaps/ROADMAP.md`
   - K0.1 is this slice;
   - K1 demolition is downstream and may act only on evidence produced here;
   - K2 proof plateau is a later hard gate.
4. `Docs/Reports/REPORT-2026-08-30-bottom-up-top-down-library-critique.md`
   - especially public API archaeology, World semantics hidden in generic contracts, historical compatibility on the hot path, founding agent runtime, semantic-document/embedding uncertainty, client ergonomics, and the architecture-fitness ledger.
5. `Docs/Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md`
   - agent orchestration is client-owned; existing MindTurn/agent/context machinery is not automatically protected.
6. `tests/unit/test_import_boundaries.py`
   - current package/layer exceptions are evidence to inventory, not automatically architecture to preserve.
7. Current Buddy consumer at exact commit `a9d4c61d04f2a4a5f92cb6947442d8173079454c`, beginning with but not limited to:
   - `apps/live_control_server/integrations/dungeonmind/world_graph_reads.py`
   - `apps/live_control_server/integrations/dungeonmind/world_graph_writes.py`
   - DungeonMind initialization/publication integration paths
   - current source-anchor/read integration
   - current D&D profile/mechanics imports
   - Hermes/agent code only to prove whether it imports DungeonMind harness/runtime machinery.

### Exact-anchor rule

The inventory is invalid if it silently scans a different Buddy or DungeonMind code state.

The generator/report must record:

```text
dungeonmind_code_anchor = 5ca5d688612349034f8ca490d465af166d883e6e
dungeonmind_steward_base = 84a4479494a37d8b5bd550465d17ff29f0e359ec
buddy_anchor = a9d4c61d04f2a4a5f92cb6947442d8173079454c
buddy_dungeonmind_pin = 5ca5d688612349034f8ca490d465af166d883e6e
```

If the local Buddy checkout is not at the expected anchor, fail with an explicit instruction to use a detached worktree or exact checkout. Do not silently scan whatever happens to be present.

---

## §3 Scope

### In scope

#### A. Exact external-consumer import inventory

Scan the Buddy tree at the exact anchor for all Python imports whose root is:

```text
dungeonmind
dungeonmind_dnd
```

Record at minimum:

- consumer file;
- imported module;
- imported symbol(s), where statically knowable;
- import form (`import` / `from ... import ...`);
- whether it resolves against the exact DungeonMind code anchor.

Also inspect for dynamic imports / string-based loading. Static AST absence is not enough to claim no consumer if `importlib`, framework loading, or subprocess/module-string invocation can prove use.

#### B. Explicit public/export surface inventory

Inventory current explicitly exported symbols for `dungeonmind` and `dungeonmind_dnd` package/subpackage surfaces, including `__all__` and re-exported names.

For every export, report whether the exact Buddy anchor has a known direct import/use.

Terminology must be precise:

> `NO_KNOWN_EXTERNAL_CONSUMER` means exactly that. It does **not** mean the symbol is safe to delete.

#### C. Internal import/topology evidence

Build enough internal import evidence to answer whether a proposed subsystem is:

- on a current World read path;
- on a current World write/publication path;
- on a current source/evidence path;
- on current first-world initialization;
- used only by tests/examples/demo/founding runtime;
- used only by compatibility/adoption/reconstruction;
- not statically classifiable.

Do not build a general dependency-analysis framework. Standard-library AST + explicit curated evidence is preferred.

#### D. Repository protocol inventory

Every repository protocol / bundle member currently exposed under the DungeonMind application/persistence surface must appear in the ledger.

For each, record:

- defining symbol/path;
- in-memory implementation if present;
- PostgreSQL implementation if present;
- current authority path(s) using it;
- founding/runtime-only path(s) using it;
- compatibility-only path(s) using it;
- disposition.

At minimum distinguish current graph/source/contribution/review/publication/initialization repositories from MindTurn/thread/retrieval-session/semantic-document/embedding/adoption/repair/correspondence repositories.

#### E. PostgreSQL table inventory

Every DungeonMind-owned table introduced by the current Alembic history must appear exactly once in the table ledger.

For each table record:

- creation migration / defining evidence;
- repository/adapter touching it;
- current authority path(s), if any;
- historical-compatibility obligation, if any;
- founding/runtime-only ownership, if any;
- disposition;
- whether K1 code demolition may occur while the physical table remains.

K0.1 does not connect to or mutate the live Eldyrwild database to infer this. Use checked-in migrations/adapters/contracts as authority. A disposable integration database may be used only by the normal test suite.

#### F. Import-boundary exception inventory

Record the current path-specific exceptions in `tests/unit/test_import_boundaries.py`, including the `application ↔ agents` accommodation and the D&D planning/review/mechanics/transport/resource allowlists.

For each exception classify whether it protects:

```text
CURRENT_REQUIRED
HISTORICAL_OR_FOUNDING
UNKNOWN
```

Do not simplify the import rules in this PR.

#### G. Optional dependency load probe

Capture the current import behavior of at least:

```text
import dungeonmind
import dungeonmind_dnd
```

and prove which heavy/optional roots are *not* loaded by those imports. Reuse the existing import-boundary vocabulary where practical rather than inventing a second inconsistent list.

#### H. Curated demolition-safety dispositions

Every subsystem named as a potential K1 target must receive exactly one disposition:

```text
USED
UNUSED
HISTORICAL-COMPAT
UNKNOWN
```

Definitions:

- `USED` — proven current external consumer or current surviving DungeonMind authority/runtime responsibility.
- `UNUSED` — no current external/internal surviving authority use and no demonstrated durable-history obligation. This is the only disposition that can make a target eligible for direct K1 runtime/code demolition.
- `HISTORICAL-COMPAT` — not part of desired current architecture, but required to reconstruct/read/upgrade durable history or living stored state. This blocks physical deletion until a later compatibility proof.
- `UNKNOWN` — evidence is insufficient or conflicting. This blocks demolition. Include a concrete `blocking_question`.

Important evidence rules:

- Tests alone do not make a subsystem `USED`.
- Presence in `__all__` does not make a subsystem `USED`.
- A PostgreSQL table's existence does not make its runtime owner current.
- A current Buddy import is strong `USED` evidence.
- A living migration/reconstruction obligation is strong `HISTORICAL-COMPAT` evidence.
- Lack of a static import is **not** by itself sufficient for `UNUSED`.

### Minimum named subsystem dispositions

The report/ledger must explicitly classify at least:

```text
MindTurn contracts + MindTurnService
agents/ protocol + fixture adapter
CapabilityPolicy as agent-visible tool authority
context assembly / budgeting used by MindTurn
claim / answer-validation machinery
MindThread persistence
RetrievalSession persistence
SemanticDocument persistence/runtime
EmbeddingRun persistence/runtime
semantic search / pgvector-derived runtime
demo_access / curated MindTurn demo host
World graph projection/retrieval
source/evidence repositories
contribution review/publication
reviewed first-world initialization
existing-world adoption
adoption repair
correspondence
v1-v6 graph readers / historical schema codecs
semantic-profile registry
D&D profile/planning/mechanics packages
```

The audit may split a named area into more precise subcomponents where one disposition would hide materially different obligations.

### Out of scope (falsification)

This PR must **not**:

- delete, deprecate, move, rename, or stop exporting runtime/library code;
- change World read/write/init/publication semantics;
- change any graph/source/review/profile contract;
- change PostgreSQL/Alembic schema;
- remove old graph readers, adoption, repair, or reviewed-init compatibility;
- remove MindTurn/agents/semantic runtime yet;
- redesign `SemanticProfile`;
- create Authority/Graph/World/Rules packages;
- implement `KnowledgeSpace` or another generic root abstraction;
- optimize reads/writes;
- add indexes or caches;
- repin DungeonMindBuddy;
- modify Buddy;
- read or mutate the live Eldyrwild database;
- treat "no known Buddy import" as permission to delete code.

If completing the inventory appears to require any of the above, stop and hand back the evidence instead.

---

## §4 Invariants that bind this slice

Carry forward these current architecture invariants as observational constraints:

1. Published revisions are immutable and head movement is explicit CAS.
2. Evidence participates in knowledge validity.
3. Reads remain explicit and fail closed under current scope/admissibility semantics.
4. Retrieval does not become authority.
5. Durable writes remain governed and exact-parent bound.
6. Profiles retain current ownership boundaries; generic DungeonMind must not import `dungeonmind_dnd`.
7. Clients remain replaceable; Buddy is evidence of use, not the definition of correct semantics.
8. Performance meaning may not change — this PR changes no performance implementation at all.
9. Per ADR-0022, the agent harness belongs outside DungeonMind; K0.1 must nevertheless report current code reality rather than force the evidence to match that desired boundary.

Slice-local invariants:

- **Observation, not contract:** the inventory describes the exact anchors above and does not promote every observed export into permanent public API.
- **Evidence before disposition:** no subsystem may be marked `UNUSED` solely because its name looks historical or because the critique expects it to be residue.
- **Unknown blocks demolition:** uncertainty is represented explicitly, never resolved by optimism.
- **History is different from runtime ownership:** code can be architecturally retired while its migrations/tables/codecs remain protected for durable reconstruction.
- **No behavior diff:** existing `src/`, `alembic/`, dependency manifests, and current runtime configuration must remain byte-identical to the K0 code anchor except for any test/audit tooling additions outside runtime packages.

---

## §5 Work plan

### 1. Establish exact two-repository anchors

Before scanning:

- verify DungeonMind source files being inventoried match code anchor `5ca5d688612349034f8ca490d465af166d883e6e`;
- verify Buddy checkout/worktree is exactly `a9d4c61d04f2a4a5f92cb6947442d8173079454c`;
- verify Buddy pins DungeonMind exactly to `5ca5d688612349034f8ca490d465af166d883e6e`;
- fail closed on mismatch.

Test: unit-test anchor validation with matching and mismatching fixture repos/metadata where practical.

### 2. Build the smallest deterministic scanner

Implement `scripts/k0_surface_inventory.py` or equivalent using standard-library facilities where possible.

The scanner should derive, not hand-enter:

- Buddy DungeonMind/D&D imports;
- DungeonMind/D&D explicit re-exports;
- internal module import edges needed for evidence;
- repository protocol/bundle symbols where statically knowable;
- Alembic-created table names where statically knowable;
- import-boundary exceptions / optional-load probe facts where practical.

Do not attempt perfect Python call-graph inference. Anything not safely derivable becomes curated evidence with an explicit source path.

The output must be deterministically sorted and free of wall-clock timestamps, absolute local paths, usernames, DSNs, or machine-specific values.

### 3. Define and validate the JSON ledger

Use a small explicit schema/version such as:

```text
dm_k0_surface_inventory_v1
```

Minimum top-level content:

```text
schema
anchors
external_consumer_imports
explicit_exports
internal_import_evidence
repository_ledger
table_ledger
import_boundary_exceptions
optional_dependency_probe
subsystem_dispositions
unresolved_questions
```

Each curated disposition must include evidence paths/reasons.

Validation must reject at least:

- unknown disposition vocabulary;
- duplicate subsystem/repository/table identifiers;
- missing evidence for `USED`, `UNUSED`, or `HISTORICAL-COMPAT`;
- `UNKNOWN` without a `blocking_question`;
- any Buddy-imported current symbol classified `UNUSED`;
- any Alembic-created table omitted from the table ledger;
- any repository protocol/bundle entry omitted from the repository ledger;
- unresolved imported Buddy symbol/module;
- anchor mismatch.

Do **not** add a long-lived CI rule that says all current exports must remain forever. The artifact is intentionally anchored historical evidence.

### 4. Curate the architecture-fitness dispositions

Use the generated evidence plus direct source inspection to classify the minimum subsystem list from §3.

For every `UNUSED` target, the report must include a short falsification note:

> What evidence was sought that would have made this `USED` or `HISTORICAL-COMPAT`, and what was found?

For every `HISTORICAL-COMPAT` target, state exactly what historical/living reconstruction obligation protects it.

For every `UNKNOWN`, state the exact question K1 must not guess past.

### 5. Write the human report

The report should be concise enough to act on. It must include:

1. exact anchors and reproduction command;
2. headline counts;
3. current Buddy import surface;
4. current explicit export surface summary;
5. repository/table classification;
6. subsystem demolition ledger;
7. import-boundary exception summary;
8. optional dependency/import findings;
9. unknowns;
10. **K1 eligibility list** — only targets classified `UNUSED`, with the warning that K1 still needs its own PR-level proof.

Do not repeat the entire JSON artifact in Markdown.

### 6. Run two formal review cycles

Record both review cycles in the handback/report.

**Cycle 1 — coverage / false-negative review**

Attempt to find things the scanner missed:

- dynamic imports;
- subprocess/module-string entry points;
- FastAPI/bootstrap construction;
- optional service hosts;
- repository uses hidden behind bundles/factories;
- migrations/compatibility code that a simple import graph undercounts.

**Cycle 2 — demolition-safety adversarial review**

Challenge every `UNUSED` classification.

For each one ask:

```text
Could Buddy use this indirectly?
Could current World read/write/init/publication use it indirectly?
Does a living database need it for reconstruction or upgrade?
Does a compatibility reader/receipt require it?
Is it loaded dynamically?
```

Any unresolved challenge downgrades the target to `UNKNOWN` or `HISTORICAL-COMPAT`; do not defend the original classification by preference.

Count review cycles in the handback. Fewer cycles is not a goal.

### 7. Atomic documentation handback

Update the K0.1 roadmap line only after acceptance evidence exists:

- point to the landed report/artifact;
- record K0.1 disposition (`DONE` or equivalent current roadmap vocabulary);
- name K0.2 as next unless evidence discovered a blocker requiring a corrective slice first.

Do not advance K1 before K0.2/K0.3 if the roadmap still requires the complete K0 golden witness first.

---

## §6 Acceptance gates

### Audit generation

Representative command; exact CLI may differ slightly but must preserve the same proof:

```bash
uv run python scripts/k0_surface_inventory.py \
  --dungeonmind-root . \
  --dungeonmind-code-anchor 5ca5d688612349034f8ca490d465af166d883e6e \
  --buddy-root ../DungeonMindBuddy \
  --buddy-anchor a9d4c61d04f2a4a5f92cb6947442d8173079454c \
  --expected-buddy-dungeonmind-pin 5ca5d688612349034f8ca490d465af166d883e6e \
  --output Docs/Reports/K0-current-consumer-public-surface-v1.json
```

Expected:

- exact anchors match;
- every imported Buddy DungeonMind/D&D symbol resolves;
- every explicit export is inventoried;
- every repository protocol/bundle member in the audited repository surface is represented;
- every Alembic-created table is represented;
- every named subsystem has one valid disposition;
- deterministic rerun produces byte-identical JSON.

Prove deterministic output:

```bash
cp Docs/Reports/K0-current-consumer-public-surface-v1.json /tmp/k0-surface.json
uv run python scripts/k0_surface_inventory.py ... \
  --output Docs/Reports/K0-current-consumer-public-surface-v1.json
cmp /tmp/k0-surface.json Docs/Reports/K0-current-consumer-public-surface-v1.json
```

### Focused tests

```bash
uv run pytest tests/unit/test_k0_surface_inventory.py \
  tests/unit/test_import_boundaries.py
```

Expected: green, including negative validation cases.

### Existing core quality gates

```bash
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
```

Expected: green.

### Integration / current CI

Run the repository's existing integration job or equivalent disposable PostgreSQL cohort:

```bash
uv sync --locked --extra postgres --extra api
uv run alembic upgrade head
uv run pytest -m integration
```

Expected: green. K0.1 must not require a live Eldyrwild database.

### No-runtime-change proof

The implementation branch may add audit tooling/tests/docs, but current runtime source/schema/dependency manifests must remain unchanged relative to the exact code anchor:

```bash
git diff --exit-code \
  5ca5d688612349034f8ca490d465af166d883e6e -- \
  src alembic pyproject.toml uv.lock
```

Expected: **no diff**.

If an audit test absolutely requires a runtime-package helper change, stop and request a new slice; do not smuggle behavior/support code into K0.1.

### External consumer integrity

K0.1 modifies no Buddy files and does not repin Buddy.

Expected external anchors remain:

```text
DungeonMindBuddy: a9d4c61d04f2a4a5f92cb6947442d8173079454c
DungeonMind pin:  5ca5d688612349034f8ca490d465af166d883e6e
```

---

## §7 Stop conditions

Stop and report rather than proceeding if any of these occur:

- Buddy is not available at the exact required anchor/pin and the inventory therefore cannot claim exact external-consumer evidence.
- A Buddy import/dynamic load cannot be resolved against the exact DungeonMind pin.
- A proposed `UNUSED` target has plausible current or historical use that cannot be disproven.
- Table/repository coverage cannot be made complete without guessing.
- The scanner would require a general-purpose call-graph/dependency framework rather than a small audit tool.
- Completing the audit requires changing `src/`, migrations, dependency manifests, runtime configuration, or Buddy.
- Existing unit/integration/import-boundary tests fail at the baseline before K0.1 behavior is introduced; record the baseline failure rather than normalizing it away.
- The exact code anchor differs from current DungeonMind `main` in a way that invalidates the audit assumptions.
- Any evidence contradicts the critique's expected demolition candidates. The evidence wins; update the report, not the facts.

`UNKNOWN` is an acceptable final disposition when evidence genuinely does not settle a target. It is **not** permission for K1 to proceed against that target.

---

## §8 Handback requirements

### Repositories and revisions

Record:

- repo;
- branch;
- PR number/URL;
- PR base branch;
- base SHA;
- final head SHA;
- DungeonMind code audit anchor;
- Buddy consumer anchor;
- Buddy DungeonMind pin;
- merge SHA/status when applicable.

### Headline inventory counts

Record at minimum:

```text
Buddy files importing dungeonmind*
Distinct imported dungeonmind modules
Distinct imported dungeonmind symbols
Explicit exported symbols inventoried
Repository protocol/bundle entries inventoried
PostgreSQL tables inventoried
Subsystem dispositions: USED / UNUSED / HISTORICAL-COMPAT / UNKNOWN
Import-boundary exceptions inventoried
Dynamic-import findings
```

### Demolition eligibility

List every K1 candidate classified `UNUSED` and its falsification evidence.

Separately list all targets blocked by:

- `HISTORICAL-COMPAT`;
- `UNKNOWN`;
- current `USED` evidence.

Do not summarize these categories together as "unused-ish."

### Decisions

For every non-obvious classification record:

```text
question
evidence
disposition
rejected alternative
consequence for K1
reversal / reclassification condition
```

### Verification

Record exact commands and results, including:

- deterministic generator rerun;
- focused audit tests;
- Ruff;
- Pyright;
- non-integration tests;
- integration cohort;
- no-runtime-change diff;
- exact Buddy anchor/pin validation.

### Review telemetry

Record:

- formal review cycle count;
- Cycle 1 findings and fixes;
- Cycle 2 findings and any disposition downgrades;
- remaining unknowns.

### What remains false

The handback must explicitly state that K0.1 does **not** prove:

- that any `UNUSED` target has already been safely deleted;
- that MindTurn/agents/semantic runtime are physically removable without K1 tests;
- that historical tables/codecs may be dropped;
- that the public API has been consolidated;
- that DungeonMind is domain-neutral;
- that RulesKnowledge is supported;
- that performance has improved;
- that K2 proof plateau has passed;
- that Buddy may be repinned.

### Named next slices

Expected successor order from the current roadmap:

1. `K0.2 — Golden semantic witness`
2. `K0.3 — Performance baseline expansion`
3. `K1.1 — Runtime/public excision`, only after K0 is complete and only against targets K0.1 actually makes eligible.

If K0.1 discovers a blocker severe enough to require a corrective slice before K0.2, name that narrowly instead of silently expanding this PR.
