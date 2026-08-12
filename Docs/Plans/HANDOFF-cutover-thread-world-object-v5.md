# HANDOFF — CUTOVER campaign-thread world-object v5

**Created:** 2026-08-12  
**Status:** READY FOR BUILD  
**Workstream:** CUTOVER  
**Repository:** `Drakosfire/DungeonMind`  
**Flow:** DND semantic contract / CUTOVER Case A  
**Direction:** DESIGN → CODE  
**Suggested PR title:** `DND: admit campaign thread world-object kind v5`  
**Suggested branch:** `dnd/cutover-thread-world-object-v5`  
**Expected ADR:** `Docs/Decisions/ADR-0017-campaign-thread-world-object-kind-v5.md`

---

## 0. Steward anchor

> **Admit the one world-object kind the exact Eldyrwild CUTOVER ledger proves DungeonMind cannot currently represent. Do not turn that narrow semantic publication into an adoption transaction, a Buddy migration, or another round of relationship cleanup.**

This PR exists because merged DungeonMindBuddy PR #568 produced a whole-world CUTOVER blocker ledger and selected one bounded DungeonMind Case A successor:

`WORLD_OBJECT_KIND` → Buddy kind `thread` → DungeonMind semantic contract gap.

The implementation must preserve that causal chain.

This is not a speculative vocabulary expansion. It is a response to one exact durable Buddy object that is currently unrepresentable under the pinned DungeonMind world-object catalog.

---

# 1. Mission

Publish a new immutable DungeonMind D&D world-object vocabulary revision that admits a persistent campaign/narrative `thread` as a first-class world-object kind.

The PR MUST:

1. publish `world-object-v5`;
2. add exactly one object kind: `dnd5e:thread`;
3. preserve every `world-object-v4` predicate exactly, including all endpoint sets;
4. publish the matching compatibility property catalog `world-property-v3`, pinned to exact world-object-v5;
5. keep `dnd5e-profile-v3` unchanged;
6. keep the union graph schema unchanged;
7. keep mechanics eligibility/pins unchanged;
8. preserve every historical vocabulary revision byte-for-byte;
9. expose only explicit v5/v3 loaders and refs — no “latest/current/default” semantics;
10. prove, with an exact CUTOVER acceptance fixture, that the one `WORLD_OBJECT_KIND` blocker selected by merged Buddy PR #568 is now representable as `dnd5e:thread`.

The PR MUST NOT:

- change DungeonMindBuddy;
- mutate Eldyrwild;
- import or adopt an existing world;
- resolve the five dual-sense relationship STOPs;
- add or widen any predicate for `thread`;
- modify assertion/provenance/adoption contracts;
- add mechanics for `thread`;
- advance product authority;
- claim CUTOVER readiness.

---

# 2. Why this is the next PR

Merged DungeonMindBuddy PR #568 is the authority for CUTOVER dispatch after #566.

Its exact merged state is:

- PR: `Drakosfire/DungeonMindBuddy#568`
- merge commit: `e5aaaf1d3d1e1e9f8c07a62383770dfd8326f259`
- canonical world: `eldyrwild`
- canonical revision: `rev:5a7c13ae45c49a65b402920499be72ed`
- canonical graph payload SHA-256:
  `2632870ef70638969503de788cfdec97acd490875deff3e2630ac91dc96fe974`
- #566 repair manifest SHA-256:
  `96cc26fc6e99448e8fba5cd6982070c1e29bb058f2b1e8a4ac291f8a0a083247`
- #568 CUTOVER fixture SHA-256:
  `6c978f89527ccd82e9bad32eac70a5386a5d714e80f7e426f574d7dbc0e43cbf`

The merged report keeps two views:

### Canonical Buddy truth

`323 semantic / 314 represented / 9 residual / 3 uses_statblock mechanics`

### Approved migration projection

`323 semantic / 318 represented / 5 residual / 3 uses_statblock mechanics`

The report remains:

`CUTOVER_NOT_READY`

and selects:

```text
CASE_A
repository = DungeonMind
basis_blocker_class = WORLD_OBJECT_KIND
blocking_stage = adoption_package_construction
```

The exact remaining kind blocker is:

```text
node:mystery:session25:light-and-sound-as-search-tools-during-night-response:field:kind
```

The durable Buddy kind at that field is:

```text
thread
```

The blocker count is exactly:

```text
WORLD_OBJECT_KIND = 1
```

This PR therefore has one semantic job: make that kind expressible in DungeonMind without collapsing it into a different meaning.

---

# 3. Source semantic decision: `thread` is a peer kind, not an adapter to `mystery`

## 3.1 Buddy already treats `thread` as its own entity kind

DungeonMindBuddy's durable vocabulary declares `thread` as a separate `EntityKind`, peer to:

- `actor`
- `place`
- `collective`
- `object`
- `phenomenon`
- encounter kinds
- session-beat kinds
- `unknown`

Buddy also has a dedicated `thread_pass`, and encounter-oriented extraction may target `thread` independently.

That is enough to reject an unreviewed assumption that `thread` is merely a spelling of some other kind.

## 3.2 `thread → dnd5e:mystery` is semantically lossy

Current DungeonMind `dnd5e:mystery` means a persistent unresolved mystery, investigative question, secret, unexplained phenomenon, or narrative uncertainty.

A campaign thread is broader.

A thread may track:

- an ongoing line of concern;
- a pursuit or consequence;
- an unresolved or developing storyline;
- a recurring connective development across sources/sessions;
- a line of play that is known and non-mysterious.

A thread does **not** inherently assert that anything is secret, unexplained, uncertain, or under investigation.

Therefore:

```text
Buddy thread
    ≠ DungeonMind mystery
```

Mapping the source kind to `dnd5e:mystery` would erase a distinction the source system already preserves.

## 3.3 `thread → dnd5e:event` is also wrong

An event is occurrence-shaped.

A thread may contain, connect, or persist across events. Its identity is continuity-shaped, not occurrence-shaped.

Therefore:

```text
Buddy thread
    ≠ DungeonMind event
```

## 3.4 Do not invent a `quest` or `objective` contract

The source evidence does not establish that a thread is necessarily:

- player-facing;
- actionable;
- a quest;
- an objective;
- open/closed;
- successful/failed;
- assigned to any actor.

This PR must not turn `thread` into a quest-state system.

---

# 4. Normative `dnd5e:thread` semantics

Publish this as a peer object kind.

Recommended catalog entry:

```json
{
  "term": "dnd5e:thread",
  "label": "Thread",
  "description": "A persistent campaign or narrative thread tracked by identity across sources or sessions. It may represent an ongoing line of concern, pursuit, consequence, unresolved development, or connective storyline. Thread identity does not imply mystery or secrecy, event occurrence, quest or objective state, epistemic standing, fictional-time standing, completion state, or mechanics."
}
```

The exact prose may be edited for catalog house style, but all of these boundaries are normative.

### Positive meaning

`dnd5e:thread` is:

- persistent;
- identity-bearing;
- campaign/narrative continuity;
- able to survive across sources/sessions.

### Negative boundaries

`dnd5e:thread` is NOT automatically:

- a `dnd5e:mystery`;
- a `dnd5e:event`;
- a `dnd5e:encounter`;
- a quest;
- an objective;
- open;
- closed;
- active;
- resolved;
- canonical;
- speculative;
- past;
- present;
- future;
- player-known;
- GM-only;
- mechanically executable.

Those semantics belong to assertions, metadata, later domain contracts, or other objects — not the kind itself.

---

# 5. Target catalog publication

## 5.1 World-object v5

Publish:

```text
vocabulary_id       = dungeonmind.dnd5e.world_object
vocabulary_revision = world-object-v5
schema_version       = dmdnd_semantic_vocabulary_v1
semantic_profile     = dungeonmind.dnd5e / dnd5e-profile-v3
```

Predecessor:

```text
world-object-v4
catalog SHA-256 =
552c59a3fa9a20e437294d1a77974c05e37b69ec95e5ea03337a7d010e4d287b
```

World-object-v5 MUST equal world-object-v4 except for:

1. `vocabulary_revision`;
2. addition of exactly one object kind: `dnd5e:thread`.

Expected kind count:

```text
v4 = 12
v5 = 13
```

Expected new-kind set:

```text
{"dnd5e:thread"}
```

No existing kind may be renamed, re-described, deleted, or reordered for semantic convenience unless catalog canonicalization already makes ordering irrelevant and the tests prove exact semantic equality.

Prefer the smallest textual diff.

---

# 6. Predicate policy: zero widening in this PR

World-object-v4 currently contains the predicate catalog needed by the proven Eldyrwild relationship work.

The #568 migration projection has five remaining relationship residuals, and all five are the already-sealed dual-sense identity/decomposition STOPs.

None of those five is a `thread` endpoint problem.

Therefore there is no CUTOVER evidence authorizing a new relationship endpoint for `dnd5e:thread`.

World-object-v5 MUST preserve all v4 predicates model-identically.

Acceptance invariant:

```python
v5.predicates == v4.predicates
```

after normal model serialization.

That means:

- same predicate count;
- same terms;
- same labels;
- same descriptions;
- same subject kinds;
- same object kinds;
- same ordering if ordering is semantically retained by the model.

`dnd5e:thread` MUST NOT appear in any predicate `subject_kinds` or `object_kinds` in this PR.

If BUILD discovers a durable current relationship whose only failure is a `thread` endpoint restriction, STOP. That is new evidence and should be adjudicated as a separate exact predicate slice, not silently widened here.

---

# 7. World-property compatibility publication

Current DungeonMind world-property-v2 pins exact world-object-v4.

A new world-object revision must not silently cause property callers to infer a new compatibility target.

Publish:

```text
world-property-v3
```

with:

- the existing property vocabulary schema unchanged;
- the same `dnd5e:role` term;
- the same role label;
- the same role description/value contract;
- exact compatibility pin to world-object-v5;
- `subject_kinds` expanded by exactly one term: `dnd5e:thread`.

Expected subject-kind delta:

```text
v2 subjects + {"dnd5e:thread"} == v3 subjects
```

This does **not** claim that the Eldyrwild thread currently has a role property.

It preserves the existing semantic contract that a world object may carry a producer-authored descriptive role under the compatible catalog.

Historical world-property-v1 and v2 remain immutable.

---

# 8. Profile, graph schema, and mechanics non-changes

## 8.1 Semantic profile

Keep:

```text
profile_id       = dungeonmind.dnd5e
profile_revision = dnd5e-profile-v3
descriptor SHA   = 2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496
```

No profile bump.

The current semantic vocabulary schema already permits additional profile-owned terms.

## 8.2 Union graph schema

Keep:

```text
dm_union_graph_v5
```

No graph schema bump.

This PR adds a semantic vocabulary term; it does not alter graph structure.

## 8.3 Mechanics

Do not repin mechanics.

Do not admit `dnd5e:thread` as mechanics-eligible.

The existing exact mechanics vocabulary/attachment contract remains unchanged.

A thread is world knowledge/continuity identity, not a StatblockRevision carrier by implication.

---

# 9. Public loader/ref surface

Follow the existing explicit revision pattern.

Add:

```python
_WORLD_OBJECT_V5_VOCABULARY_RESOURCE = "world-object-v5.json"
WORLD_OBJECT_V5_VOCABULARY_REVISION = "world-object-v5"

def load_builtin_world_object_v5_vocabulary() -> DndSemanticVocabulary: ...

def builtin_world_object_v5_vocabulary_ref() -> DndVocabularyRef: ...
```

Add the corresponding world-property-v3 APIs using the repository's existing naming style:

```python
_WORLD_PROPERTY_V3_RESOURCE = "world-property-v3.json"
WORLD_PROPERTY_V3_VOCABULARY_REVISION = "world-property-v3"

def load_builtin_world_property_v3_vocabulary() -> ...: ...

def builtin_world_property_v3_vocabulary_ref() -> ...: ...

def validate_world_property_assignment_v3(...) -> ...: ...
```

Export explicit v5/v3 functions from the package's existing application export surface.

Historical functions remain untouched.

Forbidden APIs/concepts:

```text
load_latest_...
current_world_object...
default_world_object...
latest vocabulary
auto-upgrade
implicit v4→v5
```

Exact pinning remains the architecture.

---

# 10. ADR-0017

The next available DungeonMind ADR number at the predecessor pin is ADR-0017.

Create:

```text
Docs/Decisions/ADR-0017-campaign-thread-world-object-kind-v5.md
```

The ADR should record:

## Decision

Publish `dnd5e:thread` as a peer world-object kind in immutable world-object-v5.

## Why not an adapter

Reject:

```text
thread -> mystery
thread -> event
thread -> encounter
```

because those mappings narrow or alter source identity semantics.

## Why no profile/schema bump

Catalog revision and graph/profile schema are separate version axes. The current contracts already admit additional `dnd5e:` semantic terms.

## Why no predicate widening

The exact CUTOVER evidence contains no `thread` relationship endpoint blocker. Admitting an object kind does not authorize new relationship semantics.

## Why no mechanics change

Kind identity does not imply executable/mechanical authority.

## Consequence

DungeonMind can express the one exact Buddy world-object kind blocker selected by #568. Buddy must still explicitly repin and re-run conformance before the blocker is considered cleared in CUTOVER.

---

# 11. CUTOVER acceptance fixture

Add:

```text
tests/fixtures/dungeonmind_dnd/eldyrwild_thread_kind_acceptance_v1.json
```

This fixture is not a copied Buddy world.

It is an exact source-authority witness for why this catalog revision exists.

Recommended shape:

```json
{
  "schema": "dmdnd_eldyrwild_thread_kind_acceptance_v1",
  "cutover_source": {
    "repository": "Drakosfire/DungeonMindBuddy",
    "pr": 568,
    "merge_commit": "e5aaaf1d3d1e1e9f8c07a62383770dfd8326f259",
    "world_id": "eldyrwild",
    "canonical_revision_id": "rev:5a7c13ae45c49a65b402920499be72ed",
    "canonical_graph_payload_sha256": "2632870ef70638969503de788cfdec97acd490875deff3e2630ac91dc96fe974",
    "node_kind_repair_manifest_sha256": "96cc26fc6e99448e8fba5cd6982070c1e29bb058f2b1e8a4ac291f8a0a083247",
    "cutover_reanchor_fixture_sha256": "6c978f89527ccd82e9bad32eac70a5386a5d714e80f7e426f574d7dbc0e43cbf"
  },
  "blocker": {
    "blocker_class": "WORLD_OBJECT_KIND",
    "count": 1,
    "blocking_stage": "adoption_package_construction",
    "responsible_repo": "DungeonMind",
    "durable_field_path": "node:mystery:session25:light-and-sound-as-search-tools-during-night-response:field:kind",
    "buddy_kind": "thread",
    "target_term": "dnd5e:thread"
  }
}
```

BUILD may add exact catalog refs/digests once v5/v3 bytes exist.

Do not put mutable branch names into the sealed fixture where a commit SHA is available.

Do not import DungeonMindBuddy at runtime to verify this fixture.

This is test/source evidence, not a production dependency.

---

# 12. Repository base and stale-input refusal

Expected DungeonMind predecessor:

```text
2e4fdc51f91c5c2a428500f7c2ece0d6742d04b4
```

That is the PR #29 merge commit publishing:

- world-object-v4;
- world-property-v2;
- the current adjudicated Eldyrwild relationship vocabulary.

Before implementation, BUILD MUST verify:

1. DungeonMind `main` still descends from or exactly equals that predecessor.
2. No already-published world-object-v5 exists.
3. No already-published world-property-v3 exists.
4. ADR-0017 is still the next available ADR number.
5. world-object-v4 SHA is still:
   `552c59a3fa9a20e437294d1a77974c05e37b69ec95e5ea03337a7d010e4d287b`.
6. world-property-v2 SHA is still:
   `8ad4c223e83ce48cf5cd33a33e10f5be5d48a80ad742784d7c561470b450ab73`.
7. dnd5e-profile-v3 digest is still:
   `2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496`.
8. merged Buddy #568 source authority still contains exactly one `WORLD_OBJECT_KIND` blocker for source kind `thread`.

If any of those identity/version assumptions changed, STOP and re-anchor names/digests. Do not overwrite an existing revision name or treat a semantically different newer contract as equivalent.

---

# 13. Suggested file allowlist

Expected changes should fit inside:

```text
Docs/Plans/HANDOFF-cutover-thread-world-object-v5.md
Docs/Decisions/ADR-0017-campaign-thread-world-object-kind-v5.md
Docs/Architecture/ARCHITECTURE.md
README.md

src/dungeonmind_dnd/application/__init__.py
src/dungeonmind_dnd/application/world_object_vocabulary.py
src/dungeonmind_dnd/application/world_property_vocabulary.py

src/dungeonmind_dnd/vocabularies/world-object-v5.json
src/dungeonmind_dnd/vocabularies/world-property-v3.json

tests/unit/test_dnd_world_object_v5.py
tests/unit/test_dnd_world_property_v3.py
tests/fixtures/dungeonmind_dnd/eldyrwild_thread_kind_acceptance_v1.json

pyproject.toml
```

Notes:

- `README.md`, `ARCHITECTURE.md`, and `pyproject.toml` are optional and should change only if the repository's existing publication convention requires it.
- If current tests use different established test filenames, follow the established convention while keeping the same scope.
- No `src/dungeonmind/contracts/**` change is expected.
- No `src/dungeonmind/domain/**` change is expected.
- No persistence/repository/service changes are expected.

If implementation needs a contract/schema/domain-core modification, STOP. That means this is no longer the bounded catalog publication described here.

---

# 14. Explicitly forbidden surfaces

Do not touch:

```text
DungeonMindBuddy/**
```

Do not add:

- existing-world adoption service;
- bootstrap-complete-world transaction;
- Buddy graph reader;
- Buddy migration adapter;
- source graph importer;
- graph publication;
- Postgres adoption path;
- authority selector;
- read fallback;
- write fallback;
- identity split/materialization service;
- dual-sense decomposition logic;
- relationship repair logic;
- new mechanics plugin behavior;
- current/latest vocabulary resolver.

Do not modify historical catalog files:

```text
world-object-v1.json
world-object-v2.json
world-object-v3.json
world-object-v4.json
world-property-v1.json
world-property-v2.json
```

Do not rewrite historical ADRs to make the new decision look retroactive.

---

# 15. Acceptance tests

These are normative behaviors, not suggested examples.

## T1 — exact predecessor pins

Assert the historical refs expected by this PR:

```text
world-object-v4 revision + digest
world-property-v2 revision + digest
dnd5e-profile-v3 revision + digest
```

If exact digests differ, fail.

## T2 — historical catalog immutability

Load and digest world-object-v1 through v4.

Load and digest world-property-v1 through v2.

Assert all known historical digests remain unchanged.

No fixture update is allowed to paper over historical drift.

## T3 — world-object-v5 identity

Assert:

```text
vocabulary_id = dungeonmind.dnd5e.world_object
vocabulary_revision = world-object-v5
schema_version = dmdnd_semantic_vocabulary_v1
profile = exact dnd5e-profile-v3
```

Seal the computed v5 catalog SHA in the owning test/fixture after first correct generation.

## T4 — exact kind delta

Compare v4 vs v5.

Assert:

```text
len(v4.object_kinds) == 12
len(v5.object_kinds) == 13
new terms == {"dnd5e:thread"}
removed terms == {}
```

Every pre-existing kind must model-dump identically.

## T5 — thread semantic boundaries

Assert the v5 entry exists with:

```text
term = dnd5e:thread
label = Thread
```

The description/ADR must explicitly preserve these distinctions:

```text
thread != mystery
thread != event
thread != encounter
thread != quest/objective state
thread kind does not imply epistemic state
thread kind does not imply fictional-time state
thread kind does not imply mechanics
```

Do not make this test a brittle keyword game if the repository convention favors exact catalog fixture comparison. The semantics must nevertheless be sealed somewhere reviewable.

## T6 — predicates unchanged

Model-dump v4 and v5 predicates.

Assert exact equality.

Expected predicate count remains the v4 count.

## T7 — no thread predicate endpoints

Assert:

```python
"dnd5e:thread" not in predicate.subject_kinds
"dnd5e:thread" not in predicate.object_kinds
```

for every v5 predicate.

A future evidence-driven predicate PR may change this; this one must not.

## T8 — exact CUTOVER blocker witness

Load `eldyrwild_thread_kind_acceptance_v1.json`.

Assert:

- merged Buddy #568 identity is exact;
- world/revision/payload pins are exact;
- blocker class is `WORLD_OBJECT_KIND`;
- blocker count is `1`;
- source kind is `thread`;
- exact durable field path is preserved;
- target term is `dnd5e:thread`.

Then assert v5 admits the target term and v4 does not.

This is the core CUTOVER acceptance test.

## T9 — world-property-v3 identity

Assert:

```text
revision = world-property-v3
schema unchanged
world-object pin = exact world-object-v5 ref/digest
```

Seal the resulting property-v3 digest.

## T10 — property semantics unchanged except compatibility subject

Compare v2 vs v3 `dnd5e:role`.

Assert identical:

- term;
- label;
- description;
- value contract / value kind / validation semantics.

Assert subject delta is exactly:

```text
{"dnd5e:thread"}
```

## T11 — property validator revision behavior

Assert:

- v3 accepts a valid non-empty `dnd5e:role` assignment for `dnd5e:thread`;
- v2 rejects `dnd5e:thread` because it is outside v2's exact compatibility pin.

No automatic fallback from v2 to v3.

## T12 — mechanics unchanged

Assert existing mechanics refs/digests are unchanged.

Assert no mechanics mapping/eligibility term was added for `dnd5e:thread`.

## T13 — explicit loaders only

Assert new explicit v5/v3 loaders and refs work.

Do not introduce any latest/current/default loader or alias.

If repository API-enumeration tests exist, extend them to protect this.

## T14 — no profile/schema bump

Assert v5 continues to use:

```text
dnd5e-profile-v3
dmdnd_semantic_vocabulary_v1
```

Assert property-v3 continues to use the current property schema.

## T15 — no Buddy runtime dependency

Repository/source scan the changed production modules.

No import path may point to DungeonMindBuddy.

No network/file lookup may fetch Buddy at runtime.

## T16 — CUTOVER nonclaim

The acceptance fixture / docs must make clear:

```text
WORLD_OBJECT_KIND can become representable after Buddy repins;
five dual-sense RELATIONSHIP_PREDICATE STOPs remain;
ATTRIBUTE_ASSERTION and EVIDENCE_PROVENANCE package blockers remain unless separately cleared;
DURABLE_ADOPTION_BOUNDARY remains unresolved;
CUTOVER is not READY.
```

This PR must not encode a fake whole-world “green” state.

## T17 — full owning suites

Run all established DungeonMind D&D vocabulary tests plus the repository's unit test suite required by CI.

Record actual pass counts in the PR handback. Do not predeclare a count in the implementation.

---

# 16. Verification commands

BUILD should adapt exact paths to repository convention, but the expected verification shape is:

```bash
uv sync --locked

uv run ruff check \
  src/dungeonmind_dnd/application/world_object_vocabulary.py \
  src/dungeonmind_dnd/application/world_property_vocabulary.py \
  tests/unit/test_dnd_world_object_v5.py \
  tests/unit/test_dnd_world_property_v3.py

uv run pytest -q \
  tests/unit/test_dnd_world_object_vocabulary.py \
  tests/unit/test_dnd_world_property_vocabulary.py \
  tests/unit/test_dnd_world_object_v5.py \
  tests/unit/test_dnd_world_property_v3.py

uv run pytest -q tests/unit

git diff --check
```

If the repository's actual historical tests use different names, use them and report the exact commands.

The PR handback must include:

- v5 computed catalog SHA;
- v3 computed property catalog SHA;
- exact historical digest checks;
- actual test counts;
- ruff result;
- `git diff --check`.

---

# 17. Stop conditions

STOP rather than broaden this PR if any of the following is true.

### S1 — predecessor drift

DungeonMind already contains a v5/v3 publication or main has materially changed the vocabulary contract.

Re-anchor instead of overwriting revision names.

### S2 — source authority drift

Merged #568 no longer yields exactly one `WORLD_OBJECT_KIND` blocker for source kind `thread`.

Do not publish a semantic term for a blocker that no longer exists.

### S3 — `thread` proves equivalent to an existing kind

If stronger source evidence proves Buddy `thread` is intentionally identical to `mystery`, `event`, or another existing DungeonMind kind, STOP.

Write/review the adapter decision instead.

Do not continue with a redundant peer term.

### S4 — predicate widening becomes necessary

If current exact evidence requires a relationship with `thread` as an endpoint, STOP.

Name the exact edge/predicate and dispatch a separate predicate-adjudication slice or obtain explicit steward approval to broaden.

### S5 — schema/profile change required

If `dmdnd_semantic_vocabulary_v1` or `dnd5e-profile-v3` cannot express the new peer term, STOP.

Do not silently turn a catalog publication into a semantic-profile redesign.

### S6 — mechanics change required

If any implementation path requires `thread` mechanics eligibility, STOP.

That is a separate mechanics-domain decision.

### S7 — Buddy modification required

If BUILD believes Buddy must change in order to publish the DungeonMind catalog, STOP.

This PR is DungeonMind-only.

### S8 — adoption work appears

If implementation starts adding existing-world adoption, publication receipts, CAS bootstrap, Postgres adoption, or product authority routing, STOP.

Those are later CUTOVER stages.

### S9 — dual-sense repair appears

If implementation starts creating identities/aspects for Wizard College, meat distribution, or Hempholm revelry, STOP.

Those five edges remain explicit cross-repository package-construction decisions.

---

# 18. What success means

After merge, DungeonMind will have an immutable semantic vocabulary revision capable of representing the one source object kind that the post-#568 CUTOVER ledger identifies as a DungeonMind-owned package-construction gap.

Specifically:

```text
world-object-v4
  12 kinds
  no dnd5e:thread

world-object-v5
  13 kinds
  + dnd5e:thread
  predicates unchanged
```

and:

```text
world-property-v2
  pinned to world-object-v4

world-property-v3
  pinned to world-object-v5
  role compatibility extended to dnd5e:thread
```

This does NOT itself clear the Buddy ledger.

The Buddy analyzer is pinned to exact DungeonMind contracts. Until Buddy explicitly repins to the new DungeonMind commit/v5/v3 catalogs and re-runs, CUTOVER still truthfully carries its old blocker result.

---

# 19. Required immediate successor after merge

The automatic successor is **not** the existing-world adoption transaction.

The automatic successor is one small DungeonMindBuddy conformance re-pin:

```text
Repository: Drakosfire/DungeonMindBuddy
Suggested title:
CONFORMANCE: re-pin CUTOVER to DungeonMind world-object-v5

Purpose:
- pin the exact merged DungeonMind commit;
- add the explicit source-kind mapping:
    thread -> dnd5e:thread
- pin world-object-v5 and world-property-v3 digests;
- re-run the #568 whole-world CUTOVER report;
- prove WORLD_OBJECT_KIND 1 -> 0;
- mutate no Buddy graph bytes;
- re-dispatch from the refreshed blocker ledger.
```

That successor must not assume its own next slice.

Based on the current #568 ledger, even after `thread` clears, package construction still includes at least:

- the five cross-repository dual-sense relationship STOPs;
- Buddy attribute assertion blockers;
- Buddy evidence provenance blockers.

Therefore Case B existing-world adoption remains unauthorized unless the refreshed ledger proves those package-construction blockers are no longer effective.

The refreshed ledger — not this handoff — decides what follows.

---

# 20. Likely post-repin direction, but not authorized here

Current evidence suggests CUTOVER will next need to answer two separate questions:

1. How are the remaining Buddy attribute/evidence package-construction gaps converted into exact DungeonMind adoption material?
2. What governed adoption/materialization contract represents one source concept as multiple target semantic identities for the three dual-sense cases without rewriting Buddy history?

Those are likely the bridge into the previously anticipated existing-world adoption/materialization work.

They are deliberately not part of this PR.

---

# 21. Suggested nano-commit sequence

A clean implementation can likely use four commits:

### Commit 1

```text
DOCS: handoff campaign thread world-object v5
```

Add this handoff and ADR-0017.

### Commit 2

```text
DND: publish campaign thread world-object v5
```

Add v5 resource + explicit loader/ref/export.

### Commit 3

```text
DND: repin role property compatibility to world-object v5
```

Add world-property-v3 + explicit loader/ref/validator/export.

### Commit 4

```text
TEST: seal CUTOVER thread-kind acceptance
```

Add exact fixture and all immutability/delta/nonclaim proofs.

Documentation status updates may be folded into commit 4 if tiny.

Do not create extra commits for unrelated formatting or cleanup.

---

# 22. Implementer handback

Return all of the following to stewardship.

## Git identity

```text
base SHA:
head SHA:
branch:
PR:
```

## Published catalog identity

```text
world-object-v5 SHA-256:
world-property-v3 SHA-256:
dnd5e-profile-v3 SHA-256:
```

## Exact delta proof

```text
v4 kind count:
v5 kind count:
new kinds:
removed kinds:
changed historical kind definitions:
predicate count v4:
predicate count v5:
predicate model equality:
thread appears in any predicate endpoint?:
```

Expected answer:

```text
12
13
[dnd5e:thread]
[]
[]
same
same
true
false
```

## Property proof

```text
v2 target world-object revision:
v3 target world-object revision:
role semantic fields changed?:
role subject-kind delta:
```

## CUTOVER witness

```text
Buddy #568 merge SHA:
canonical Eldyrwild revision:
canonical payload SHA:
#568 fixture SHA:
source blocker class/count:
source field path:
source kind:
target term:
```

## Nonchanges

Explicitly state:

```text
profile unchanged
union graph schema unchanged
mechanics unchanged
historical catalogs unchanged
no Buddy repo change
no graph write
no predicate widening
no dual-sense resolution
no adoption seam
no authority switch
```

## Verification

Return exact:

- ruff command/result;
- focused test commands/pass counts;
- full unit suite command/pass count;
- `git diff --check`.

## Successor recommendation

The handback must recommend only:

```text
DungeonMindBuddy / CONFORMANCE:
re-pin CUTOVER to exact merged world-object-v5/world-property-v3
and re-run the blocker ledger
```

Do not recommend Case B directly from this PR.

---

# 23. Steward review checklist

Before merge, stewardship should be able to answer YES to all of these:

- [ ] Is this DungeonMind-only?
- [ ] Is #568 the exact dispatch authority?
- [ ] Is `WORLD_OBJECT_KIND=1` still the source blocker?
- [ ] Is `dnd5e:thread` the only new object kind?
- [ ] Are all v4 predicates unchanged?
- [ ] Does `thread` appear in zero predicate endpoint sets?
- [ ] Are v1-v4 object catalogs immutable?
- [ ] Are v1-v2 property catalogs immutable?
- [ ] Is property-v3 a compatibility repin rather than a semantic redesign?
- [ ] Is profile v3 unchanged?
- [ ] Is graph schema v5 unchanged?
- [ ] Are mechanics unchanged?
- [ ] Are loaders explicit revision-only APIs?
- [ ] Is there no latest/current/default vocabulary path?
- [ ] Is there no Buddy runtime dependency?
- [ ] Is there no graph migration or adoption transaction?
- [ ] Are the five dual-sense STOPs still explicitly unresolved?
- [ ] Does the PR refuse to claim CUTOVER readiness?
- [ ] Is the immediate successor a Buddy conformance re-pin rather than Case B?

If any answer is NO, do not merge without explaining why the handoff itself must change.

---

# 24. Final boundary

This PR should be boring in the best possible way.

The CUTOVER ledger found one source kind DungeonMind cannot express.

Publish one immutable semantic peer kind.

Repin the compatible property vocabulary.

Prove historical immutability.

Stop.

Do not solve the next blocker early.
