---
# Optional transport pointer for the GitHub PR body.
# The checked-in HANDOFF, nano-commit diff, and verification output are authoritative.
pr_body_template: |
  ## Handoff pointer
  - Conversation: DungeonMind fictional-time characterization
  - Flow / agent: TIMELINE
  - Direction: DESIGN → CODE
  - Handoff: Docs/Handoffs/HANDOFF-ft0-fictional-time-characterization.md
  - PR / branch: timeline/ft0-fictional-time-characterization

  ## Verification pointer
  - Base/head: TODO after PR #14 merges and implementation begins
  - Changed paths: §4 allowlist only
  - Verification: §7 evidence ledger

  The checked-in handoff, cumulative code diff, nano commits, and independently
  rerun verification are the review contract. The PR description is transport
  metadata only. Document sync is a separate operation.
---

# HANDOFF — FT0 Corpus-grounded Fictional-time Characterization

**Created:** 2026-08-03  
**Status:** ACTIVE — implementation dispatch is permitted only after the base gate in §2 is satisfied.  
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-ft0-fictional-time-characterization.md`  
**Conversation name:** `DungeonMind fictional-time characterization`  
**Flow / agent:** `TIMELINE`  
**Handoff direction:** `DESIGN → CODE`  
**Design agent:** ChatGPT project design session  
**Code agent:** fresh TIMELINE code agent with no prior implementation context  
**Repository:** `Drakosfire/DungeonMind`  
**Suggested branch:** `timeline/ft0-fictional-time-characterization`  
**PR title:** `TIMELINE: characterize fictional-time ordering and state boundaries`  
**Implementation base:** `71156b630a4370039dc749b548eb43828cce0e6d` — the exact `main` merge SHA of DungeonMind PR #14 (`B.2f-c`). Do not branch from PR #14's ephemeral test merge commit.  
**Predecessor:** DungeonMind PR #14 — durable finalized-review publication identity and recovery.  
**External research stop record:** DungeonMindBuddy PR #505 — TL01 closed as not ready; reopen requires a smaller capability with an identified consumer.  
**Named successor:** `FT1` — a candidate versioned temporal-claim contract and revision-pinned read seam, only if FT0 produces a clear positive result and a named consuming surface.

> **Dispatch gate:** This is a bounded executable characterization, not a production Timeline feature. Dispatch is prohibited until PR #14 is merged, the exact base SHA is written into the implementation handback, and the worker confirms that no concurrent PR owns fictional-time contracts, temporal query semantics, or `GraphContributionAssertion.temporal_scope` changes.
>
> This checked-in handoff is the complete authority. Do not expand it into prose extraction, a provider experiment, a generic temporal ontology, graph publication, an API, or a product surface. If the characterization cannot remain inside the strict allowlist and code-size budget, stop and return a split proposal.

## Shared vocabulary

| Term | Definition |
|---|---|
| **Fictional occurrence time** | Time inside the represented world or campaign. It is distinct from source creation time, source revision time, ingestion time, publication time, or session provenance. |
| **Anchor** | A named fictional event or boundary used only for temporal reasoning. An anchor does not imply a calendar date. |
| **Strict-before claim** | A governed test claim that anchor A occurred before anchor B. It forms a strict partial order: irreflexive, transitive, and acyclic. |
| **State boundary** | A named event at which one Boolean state changes from a declared value immediately before the boundary to a declared value immediately after it. “Immediately” means logical boundary side, not a measured duration. |
| **Absolute anchor** | An explicit fictional calendar/date/time value attached to an anchor. Source metadata is never an absolute anchor. FT0 contains no absolute anchors. |
| **Entailed** | The answer follows from an explicit claim or deterministic closure over explicit claims. |
| **Contradicted** | The opposite ordering is entailed by the strict partial order. |
| **Unresolved** | The fixture does not license an answer. Unresolved is a successful, truthful outcome. |
| **Proof path** | The exact ordered claim IDs used to derive one answer. |
| **Closed evidence ledger** | Every proof claim references existing evidence IDs, and every fixture evidence record is used by at least one claim. |
| **Characterization** | Test-only executable semantics used to decide whether a future production contract is worth designing. It is not a public, durable, or supported runtime capability. |

## Agent flow and nano-commit contract

Use `TIMELINE` for this slice.

Keep the implementation in nano commits. The expected commit story is:

1. `test: seal FT0 corpus-derived fixture`
2. `test: characterize fictional-time ordering and state boundaries`
3. `test: prove abstention, leakage guards, and replay determinism`
4. `docs: complete FT0 implementation handback` only after code review, if repository practice requires status handback in the same file

Do not combine unrelated cleanup, dependency updates, production refactors, or documentation synchronization into these commits.

## Review and document-sync contract

The reviewer must identify the exact base SHA, branch, and head SHA; review the cumulative diff; and rerun the §7 evidence. The PR body is not authority.

Do not update `README.md`, architecture, authority, roadmap, or ADRs in the implementation PR. FT0 makes no architectural decision. If FT0 succeeds, a separate design/document operation may propose FT1 and any corresponding ADR.

## §0 Capability decomposition and stopping rule

The earlier DungeonMindBuddy TL01 effort attempted prompt calibration over prose and closed as not ready after producing no promotable prompt and no production consumer. FT0 deliberately changes the question.

```text
TL01 asked:
  can a provider reliably extract temporal structure from arbitrary prose?

FT0 asks:
  given a tiny set of already-governed temporal claims,
  can the future kernel answer useful temporal questions deterministically,
  preserve unresolved time, and retain exact evidence?
```

The sequence is intentionally split:

```text
FT0  test-only characterization over two corpus-derived cases
FT1  candidate contract + revision-pinned query seam, only if product pull exists
FT2  governed contribution/materialization integration, only after FT1
FT3  extraction calibration, only after a real consumer requires it
```

FT0 must not implement any FT1, FT2, or FT3 behavior.

### Cost ceiling

FT0 is invalid if it requires campaign-scale infrastructure.

- Maximum changed paths: exactly the §4 allowlist.
- Maximum executable test file size: 450 nonblank lines.
- Maximum fixture size: 250 nonblank lines.
- Provider calls: zero.
- Network or sibling-repository reads during tests: zero.
- New dependencies: zero.
- New report documents: zero.
- New fixture cohorts: zero.
- New production modules: zero.

Crossing any ceiling is a stop condition, not permission to amend the slice silently.

## §1 Mission and merge-ready invariant

A kernel maintainer can execute one sealed, test-only fictional-time characterization over two corpus-grounded cases so that four useful queries resolve deterministically, missing fictional time remains explicitly unresolved, and source/session metadata never becomes fictional occurrence time.

**Merge-ready invariant:**

```text
one pinned source manifest
+ one sealed local characterization fixture
+ one test-local evaluator
→ validate unique anchors, claims, state boundaries, queries, and closed evidence
→ compute only strict-before transitive closure and exact boundary-side state values
→ return deterministic answer + proof claim IDs + evidence IDs
→ preserve unresolved absolute time and incomparable anchors
→ produce byte-equivalent results under fixture replay and harmless list reordering
→ make zero changes to production code, durable/public contracts, graph schemas,
  publication, persistence, transport, providers, or product surfaces
```

### Primary acceptance questions

The characterization must answer exactly these four gold questions:

| Query | Gold answer | Required basis |
|---|---|---|
| Was the grotesque tree felled before the root-beetle attack? | `entailed / true` | strict-before closure through the evening revelry boundary |
| What absolute fictional date or time was the tree felled? | `unresolved` | no explicit absolute anchor exists; Session 4 is provenance only |
| Had Lysandra returned home during the current campaign arc immediately before the Mireward gate arrival? | `entailed / false` | dossier-backed prior state on the before side of the gate boundary |
| Had Lysandra returned home during the current campaign arc immediately after the Mireward gate arrival? | `entailed / true` | observed Session 22 gate arrival closes the prior state |

### Pre-dispatch critique

| Question | Answer |
|---|---|
| Can one invariant govern every claimed observable path? | Yes. Every path is fixture validation or pure query evaluation with no side effects. |
| What adversarial sequence is most likely to falsify it? | Reorder fixture arrays, expose `session: 4` / `session: 22`, remove all absolute anchors, then ask the absolute-time query. A faulty evaluator may derive occurrence time from provenance or fixture order. |
| Would the §7 evidence detect that failure? | Yes. Dedicated leakage and shuffle tests require identical ordering/state answers and an unresolved absolute answer. |
| Which owning boundary is easiest to under-test? | Proof construction: an evaluator may return the right Boolean while inventing evidence or relying on expected gold. Tests must verify exact claim/evidence paths and keep gold outside evaluator input. |
| What fact would force this slice to stop or split? | Any need to change `src/dungeonmind`, graph payload schemas, materialization, persistence, migrations, APIs, or profile vocabulary. |

## §2 Context, authority, and boundaries

### Repository-state gate

Before editing:

1. Verify DungeonMind PR #14 is merged.
2. Record its exact merge SHA as the implementation base.
3. Confirm `origin/main` contains ADR-0011 and the durable publication implementation.
4. Search open PRs and current code for another owner of fictional-time semantics or `temporal_scope` changes.
5. Stop if the current `GraphContributionAssertion`, graph schema, or review materializer differs materially from the predecessor facts below.

Pre-dispatch reconnaissance may be performed while PR #14 is open, but no implementation branch should be cut from its ephemeral test merge commit.

### Authority table

| Field | Required content |
|---|---|
| Parent architecture | `Docs/Architecture/ARCHITECTURE.md`; `Docs/Architecture/AUTHORITY.md` after PR #14 merges |
| Parent decisions | ADR-0004 semantic profile boundary; ADR-0007 finalized review; ADR-0009 review materialization; ADR-0010 CAS publication; ADR-0011 durable publication after merge |
| Repository rules | `CONTRIBUTING.md`; kernel must not import `dungeonmind_dnd`; optional dependencies remain optional |
| Base revision | Exact PR #14 merge SHA, recorded by implementer |
| Existing temporal carrier | `GraphContributionAssertion.temporal_scope: dict[str, Any] | None`; currently opaque |
| Existing graph materialization | `review_materialization.py` materializes accepted label, alias, summary, relationship, and evidence effects; it does not establish temporal query semantics or a graph temporal record |
| Exact input consumed | One checked-in FT0 JSON fixture; no source files are opened at runtime |
| Named successor | FT1 candidate temporal contract and revision-pinned query seam |
| What remains false | Production temporal validation, graph storage, as-of projection, provider extraction, API/tool/UI, Timeline product capability |

### Source authority and pinned corpus basis

The fixture is human-authored gold derived from these exact DungeonMindBuddy source revisions. The implementation must copy the manifest identities into the fixture and must not fetch these files during tests.

**Sibling repository pin:**

```text
repository: Drakosfire/DungeonMindBuddy
commit: a0cb1c00206cc5a674b22dc2051bd4fcbe96811f
```

| Source ID | Role | Path | Git blob SHA |
|---|---|---|---|
| `src:hempholm-session-04` | observed play recap | `corpus/eldyrwild-markdown/Longmont Campaign/Campaign 1/Session Recaps/_normalized/Session 04 - The Grotesque Tree of Hempholm.md` | `bc9ae016793efdd5614ebd88339b745d654e5b56` |
| `src:lysandra-mireward-history` | authored dossier / prior-state source | `corpus/eldyrwild-markdown/Longmont Campaign/Campaign 2/NPCs/captain_lysandra_ironveil/lysandra_ironveil_mireward_history.md` | `1d7e7038a60d28af1215f2412e9378501bc07ba7` |
| `src:mireward-session-22` | observed play recap / boundary occurrence source | `corpus/eldyrwild-markdown/Longmont Campaign/Campaign 2/Session Recaps/_normalized/Session 22 - Mireward Road and Lysandro.md` | `1c68ce991857ae47c0407e4852526fa55aa123b4` |

### Source interpretation locked by this handoff

The worker must not silently broaden or “improve” the gold.

#### Hempholm

The observed recap licenses this relative sequence:

```text
arrival at Hempholm
< grotesque tree felled
< evening revelry
< root-beetle attack
```

It does not license an absolute fictional date or clock time for the felling. The frontmatter `session: 4`, source commit, blob SHA, normalization date, and document order are provenance, not fictional occurrence anchors.

#### Lysandra

The authored dossier explicitly says that Lysandra visited Mireward twice yearly earlier in life and that during the C1–C2 campaign arc she “has not been home until S22 forced march.” Therefore the state must be narrowly named:

```text
state: Lysandra has returned home during the current C1–C2 campaign arc
```

Do not model “has never returned since leaving” or any lifetime equivalent.

The dossier supplies the prior `false` state. The observed Session 22 recap supplies the played gate-arrival event and the after-boundary `true` state. The dossier alone must not prove that the gate encounter occurred.

### Existing contract boundary

At the predecessor state, `GraphContributionAssertion.temporal_scope` is an opaque dictionary. FT0 may prove exact Pydantic round-trip of one representative candidate payload through that existing field. It must not:

- change the field type or validators;
- name the fixture schema as a supported DungeonMind schema;
- materialize the payload into `dm_union_graph_v3`;
- interpret temporal payloads in production code;
- claim that an accepted contribution currently makes temporal claims queryable.

## §3 Observable-path and adversarial-sequence inventory

| Path | Current behavior | Required FT0 behavior | Same invariant as §1? | Owning boundary |
|---|---|---|---:|---|
| Fixture load | No FT0 fixture exists | Strict local validation; malformed fixture fails before evaluation | Yes | characterization test loader |
| Hempholm ordering query | No temporal evaluator | Entailed through exact claim path and evidence union | Yes | test-local evaluator |
| Hempholm absolute-time query | No temporal evaluator | Unresolved; no source metadata fallback | Yes | test-local evaluator |
| Lysandra before-boundary query | No temporal evaluator | False with exact prior-state evidence | Yes | test-local evaluator |
| Lysandra after-boundary query | No temporal evaluator | True with exact observed-arrival evidence | Yes | test-local evaluator |
| Incomparable-anchor query | No temporal evaluator | Unresolved; no total-order invention | Yes | test-local evaluator |
| Reverse known ordering | No temporal evaluator | Contradicted when the opposite path is entailed | Yes | test-local evaluator |
| Replay | No FT0 artifact | Same fixture and query produce byte-equivalent result | Yes | test-local evaluator |
| Harmless fixture reordering | Not applicable | Same canonical result after arrays are reordered | Yes | validation + evaluator |
| Cycle / self-before | Not applicable | Fixture rejected, no answer returned | Yes | validation |
| Missing/dangling evidence | Not applicable | Fixture rejected, no answer returned | Yes | validation |
| Opaque carrier round-trip | Existing field accepts arbitrary dictionary | Representative payload survives model dump/reload exactly; no semantic claim | Yes | existing Pydantic contract exercised by test |

### Ordered adversarial sequences

| Sequence | Required safe outcome | Owning proof |
|---|---|---|
| Load valid fixture → reverse anchor/claim/evidence array order → evaluate all four gold queries | Byte-equivalent canonical answers and proof IDs | §7 E7 |
| Load valid fixture → retain `session_provenance=4` → remove all absolute anchors → ask tree absolute time | `unresolved`, reason `no_explicit_absolute_anchor` | §7 E4 |
| Add `tree_felled before beetle_attack` opposite edge creating a cycle → load | Typed/local validation failure; no closure | §7 E8 |
| Delete one evidence record referenced by a proof claim → load | Closed-ledger validation failure | §7 E9 |
| Add unrelated anchor → ask ordering against tree | `unresolved`; unrelated anchor never inherits fixture order | §7 E6 |
| Evaluate query → mutate returned proof/evidence lists → evaluate again | Second result unchanged | §7 E7 |
| Put representative claim payload through `GraphContributionAssertion.temporal_scope` → dump/reload | Exact payload equality; no production evaluator call | §7 E10 |

## §4 Files in scope — strict allowlist

| Action | Path | Purpose |
|---|---|---|
| Create | `Docs/Handoffs/HANDOFF-ft0-fictional-time-characterization.md` | Checked-in design and review authority |
| Create | `tests/fixtures/fictional_time/ft0-two-case-characterization-v0.json` | Sealed source manifest, evidence ledger, anchors, ordering claims, and state boundary |
| Create | `tests/characterization/test_fictional_time_characterization.py` | Test-local validation, evaluator, gold queries, adversarial proofs, and carrier round-trip |

**Bounded discovery exception:** Not applicable. If pytest collection requires another path, stop and report rather than adding it.

## §5 Files and capabilities explicitly out of scope

| Path, layer, or capability | Why this slice must not touch or claim it |
|---|---|
| `src/dungeonmind/**` | FT0 is not production kernel behavior |
| `src/dungeonmind_dnd/**` | Fictional time is not being added to the D&D vocabulary or profile package |
| `migrations/**` | No durable temporal storage or schema |
| `Docs/Architecture/**` | No architectural decision is accepted by a characterization |
| `Docs/Decisions/**` | No ADR until FT0 earns a candidate FT1 design |
| `Docs/Roadmaps/**`, `README.md`, `CONTRIBUTING.md` | Document sync is a separate operation; no production capability landed |
| `src/dungeonmind/application/review_materialization.py` | Do not carry temporal scopes into graph payloads in this slice |
| `src/dungeonmind/application/graph_snapshot.py` | No graph reader or projection semantics |
| publication/review repositories | No write path, no revision, no head mutation |
| FastAPI, CLI, agent tools, examples, browser assets | No transport or consuming surface |
| DungeonMindBuddy repository | Source material is pinned input, not a cross-repo implementation |
| Provider prompts, model calls, extraction runners, cohorts | TL01-style extraction is explicitly deferred |
| Calendar/date parsing, durations, recurrence, fuzzy expressions | Not required by the two cases |
| Allen interval algebra or a generic temporal reasoner | Exceeds the characterized product pull |
| Timeline append or Timeline UI | Separate existing/product capability |

## §6 Implementation contract and conditional matrices

### 6.1 Input fixture shape

Create one strict JSON fixture with this conceptual shape. Exact field names below are part of FT0 test data only, not a production schema.

```json
{
  "fixture_version": "dm_fictional_time_characterization_v0",
  "world_id": "world:ft0-fictional-time",
  "source_manifest": [],
  "evidence": [],
  "anchors": [],
  "strict_before_claims": [],
  "state_boundaries": []
}
```

The fixture must contain no `gold_answers` field. Gold stays in the test so the evaluator cannot read its expected result.

#### Source manifest records

Each manifest record contains exactly:

```text
source_id
repository
repository_commit
path
git_blob_sha
source_class
campaign_id
session_provenance | null
```

`session_provenance` is deliberately present to test leakage resistance. The evaluator must not read the source manifest when determining fictional occurrence.

#### Evidence records

Each evidence record contains:

```text
evidence_id
source_id
locator_hint
```

`locator_hint` may contain a short human-readable section/sentence hint. It is not parsed by the evaluator.

Required evidence identities:

```text
ev:hempholm-tree-felled
ev:hempholm-evening-revelry
ev:hempholm-root-beetle-attack
ev:lysandra-not-home-c1-c2
ev:lysandra-mireward-gate-arrival
```

#### Anchors

Required anchors:

```text
anchor:hempholm-arrival
anchor:hempholm-tree-felled
anchor:hempholm-evening-revelry
anchor:hempholm-root-beetle-attack
anchor:lysandra-mireward-gate-arrival
```

An anchor contains only:

```text
anchor_id
label
absolute_fictional_time | null
```

All FT0 `absolute_fictional_time` values are `null`.

#### Strict-before claims

Required direct claims:

```text
claim:hempholm-arrival-before-tree
claim:hempholm-tree-before-revelry
claim:hempholm-revelry-before-beetles
```

Each contains:

```text
claim_id
before_anchor_id
after_anchor_id
evidence_ids[]
```

The gold tree-before-beetles answer must be derived through the direct claim chain, not inserted as a redundant direct edge.

#### State boundary

Create exactly one state boundary:

```text
state_id: state:lysandra-returned-home-current-campaign-arc
boundary_anchor_id: anchor:lysandra-mireward-gate-arrival
before_value: false
after_value: true
before_evidence_ids: [ev:lysandra-not-home-c1-c2]
after_evidence_ids: [ev:lysandra-mireward-gate-arrival]
```

This boundary says nothing about Lysandra’s lifetime or earlier visits.

### 6.2 Test-local evaluator result

The evaluator returns an immutable/copy-safe local result equivalent to:

```text
query_id
query_kind
status: entailed | contradicted | unresolved
value: true | false | null
proof_claim_ids[]
evidence_ids[]
reason | null
```

This is not exported from a production package and is not serialized as a supported DungeonMind schema.

### 6.3 Query semantics

#### Strict-before

```text
A before B:
  reachable A → B     → entailed / true
  reachable B → A     → contradicted / false
  neither reachable   → unresolved / null
```

Closure is transitive over explicit strict-before claims only. Fixture/source list order, labels, sessions, source timestamps, and IDs never add edges.

For an entailed result, return one deterministic proof path. Use the shortest number of edges; break equal-length ties by lexicographic claim-ID sequence. Evidence is the sorted union of evidence IDs on that path.

#### Absolute fictional time

Return a value only when the queried anchor contains a non-null explicit `absolute_fictional_time`. FT0 has none.

A missing explicit value returns:

```text
status: unresolved
value: null
proof_claim_ids: []
evidence_ids: []
reason: no_explicit_absolute_anchor
```

No source/session metadata fallback is permitted.

#### State at a boundary

FT0 supports only exact lookup of one named Boolean state at one exact named boundary side:

```text
position: immediately_before → before_value + before evidence
position: immediately_after  → after_value + after evidence
```

No interpolation, propagation to other anchors, duration, or interval arithmetic is authorized.

### 6.4 Validation rules

Reject before evaluation when any rule fails:

- unknown fixture version;
- blank or duplicate source, evidence, anchor, claim, or state IDs;
- dangling source/evidence/anchor references;
- unused evidence record;
- strict-before self edge;
- duplicate strict-before pair;
- any cycle in the strict-before graph;
- duplicate state boundary for the same `(state_id, boundary_anchor_id)`;
- `before_value == after_value` in FT0;
- missing prior or after evidence;
- an absolute value constructed from `session_provenance` or any source-manifest field;
- unexpected extra fields if strict local models are used.

Validation errors may name safe IDs and rule names. They must not dump full fixture input or source locator text into a chained traceback if local Pydantic validation is used.

### 6.5 Opaque carrier compatibility proof

Construct one existing `GraphContributionAssertion` in the test with:

```text
assertion_kind: fictional_time_probe
acceptance_state: accepted
temporal_scope:
  fixture_version: dm_fictional_time_characterization_v0
  claim_type: strict_before
  claim_id: claim:hempholm-tree-before-revelry
  before_anchor_id: anchor:hempholm-tree-felled
  after_anchor_id: anchor:hempholm-evening-revelry
```

Supply valid evidence/source identity required by the existing contract. Prove:

```text
model_validate → model_dump(mode="json") → model_validate
```

preserves `temporal_scope` exactly.

This proof establishes only opaque carriage. The test name and assertions must explicitly state that no production semantic validation, graph materialization, or queryability is claimed.

### 6.6 Replay, trust, and side effects

```text
Input:
  one local fixture + one local query

Output:
  one deterministic local result

Failure behavior:
  invalid fixture → local validation error before query
  valid but insufficient claims → unresolved result

Replay / idempotency:
  same fixture + same query → byte-equivalent canonical result
  harmless fixture array reordering → byte-equivalent canonical result
  changed semantic claim → changed result or validation failure

Trust boundary:
  verifies fixture structure, references, partial-order consistency,
  exact state boundary, and evidence closure
  trusts the human-authored corpus interpretation fixed by this handoff

Commit point:
  Not applicable — pure test execution with no persistence or mutation
```

### A. State and fallback matrix

| Observable path | Loading | Exact success | Ordinary miss | Dependency unavailable | Integrity failure | Stale/superseded | Replay |
|---|---|---|---|---|---|---|---|
| fixture/query | local file only | deterministic result | unresolved | not applicable; no dependency | validation failure | not applicable | exact |
| absolute time | local anchor | explicit value only | unresolved | not applicable | validation failure | not applicable | exact |
| opaque carrier | in-memory Pydantic model | exact round-trip | not applicable | not applicable | existing contract failure | not applicable | exact |

No fallback source exists.

### B. Identity matrix

| Situation | Required rule | Ambiguity behavior | Fallback permitted? |
|---|---|---|---|
| Exact anchor/state/claim/evidence ID | exact string equality | duplicates rejected | No |
| Label | display only | never resolves identity | No |
| Source path/session | provenance only | never resolves anchor/time | No |
| Normalized or fuzzy key | prohibited | unresolved / validation error as applicable | No |

### C. Persistence and replay matrix

| Operation | Durable representation | Round-trip guarantee | Duplicate/replay | Compatibility/migration | Rollback |
|---|---|---|---|---|---|
| Fixture checkout | Git-tracked test JSON | byte-stable unless intentionally edited | same bytes, same result | no migration; v0 test data only | Git revert |
| Query evaluation | none | immutable/copy-safe local result | exact | no contract | not applicable |
| Opaque assertion carrier | existing Pydantic model only | temporal dictionary exact through dump/reload | exact | no schema change | not applicable |

### D. Predecessor-to-characterization mapping

**Grounding sources:** current `GraphContributionAssertion` contract, current `review_materialization.py`, and the pinned Buddy corpus manifest.

| Predecessor field/outcome | Real shape | FT0 use | Transformation | Proof |
|---|---|---|---|---|
| `GraphContributionAssertion.temporal_scope` | `dict[str, Any] | None`, opaque | carrier compatibility only | none; exact round-trip | E10 |
| accepted assertion evidence requirement | evidence refs or source identity required | representative carrier assertion supplies valid basis | existing validation only | E10 |
| `dm_union_graph_v3` materialization | label/alias/summary/relationship/evidence effects; no temporal query record | explicitly untouched | none | E11 diff guard |
| Buddy recap `session` | source provenance integer | copied to manifest leakage trap | no occurrence mapping | E4 |
| Buddy observed recap | played occurrence source | evidence identity for event/order | human-authored fixture claim | E2/E3/E5 |
| Buddy authored dossier | background/prior-state source | before-side evidence only | human-authored fixture boundary | E5 |

## §7 Evidence required to merge

| ID | Guarantee / invariant clause | Owning boundary | Evidence class | Command/scenario | Expected evidence | Stop condition |
|---|---|---|---|---|---|---|
| E1 | Fixture pins the exact three source paths, commit, blob SHAs, classes, campaigns, and session provenance | fixture loader | contract | focused test | exact manifest equality | any drift or runtime fetch |
| E2 | Tree felling is before beetle attack via transitive closure, not redundant gold edge | evaluator | characterization | gold ordering test | entailed, proof path tree→revelry→beetles, exact evidence union | direct redundant edge or wrong proof |
| E3 | Strict-before closure is deterministic and evidence-closed | evaluator | adversarial | path/proof tests | canonical shortest/lexicographic proof | invented/missing evidence |
| E4 | Absolute tree time remains unresolved and Session 4 does not leak | evaluator | adversarial | metadata leakage test | `no_explicit_absolute_anchor` | any derived session/date value |
| E5 | Lysandra prior/after state is false/true at exact gate boundary with source-role separation | evaluator | characterization | two gold state tests | prior evidence from dossier; after evidence from observed recap | lifetime claim, dossier-only arrival proof, or swapped evidence |
| E6 | Partial order is not totalized | evaluator | adversarial | unrelated anchor and reverse-order tests | unresolved for incomparable; contradicted only when opposite path exists | fixture-order inference |
| E7 | Replay, reorder, and returned-result mutation are safe | evaluator | regression | replay/shuffle/copy tests | byte-equivalent second result | stateful or order-sensitive output |
| E8 | Cycles and self-before fail closed | validation | adversarial | mutated fixture cases | validation failure before query | closure proceeds |
| E9 | Evidence ledger is closed | validation | adversarial | dangling + unused evidence mutations | validation failure | answer with missing/invented evidence |
| E10 | Existing temporal carrier round-trips opaquely without semantic claim | existing contract via test | compatibility | Pydantic round-trip test | exact dictionary equality | production change or queryability claim |
| E11 | Zero production/durable/public changes | repository diff | scope | diff guards | no changes outside §4; no new deps | any production path/dependency change |
| E12 | Full core suite remains green | repository | regression | non-integration suite | no new failures | new/broader failures |

Run and record exact results:

```bash
uv run pytest -q tests/characterization/test_fictional_time_characterization.py
uv run ruff check tests/characterization/test_fictional_time_characterization.py
uv run pyright
uv run pytest -q -m 'not integration'

git diff --check
git diff --name-only <BASE>...HEAD
git diff --stat <BASE>...HEAD -- \
  Docs/Handoffs/HANDOFF-ft0-fictional-time-characterization.md \
  tests/fixtures/fictional_time/ft0-two-case-characterization-v0.json \
  tests/characterization/test_fictional_time_characterization.py

git diff --name-only <BASE>...HEAD -- \
  src/dungeonmind src/dungeonmind_dnd migrations pyproject.toml uv.lock \
  Docs/Architecture Docs/Decisions Docs/Roadmaps README.md CONTRIBUTING.md

python - <<'PY'
from pathlib import Path
for path, ceiling in [
    (Path('tests/characterization/test_fictional_time_characterization.py'), 450),
    (Path('tests/fixtures/fictional_time/ft0-two-case-characterization-v0.json'), 250),
]:
    nonblank = sum(1 for line in path.read_text().splitlines() if line.strip())
    print(path, nonblank, 'ceiling', ceiling)
    assert nonblank <= ceiling
PY
```

### Minimal live / dogfood proof

Not applicable. FT0 has no runtime consumer, source fetch, provider, API, UI, persistence, or graph publication. Adding one is a split trigger.

### Baseline failure protocol

For any required command already failing on the exact PR #14 merge base:

- run the same command on base and head;
- record both exact results;
- do not call the gate green;
- obtain an explicit operator waiver if the failure remains an acceptance gate.

## §8 Required review handback

The implementation handback must include:

1. Exact PR URL or branch/head SHA.
2. Exact PR #14 merge SHA used as base.
3. §1 mission and merge-ready invariant copied exactly.
4. Source manifest table with exact commit and blob SHAs.
5. The four gold query results, including proof claim IDs and evidence IDs.
6. Every E1–E12 result with provenance: author-local, independent rerun, or CI.
7. Nano-commit list and discrete story for each commit.
8. Actual changed paths and focused diff stat.
9. Confirmation that production-path diff guard is empty.
10. Exact line counts for the fixture and characterization test.
11. Baseline failures and waivers; `none` when none.
12. Paths outside §4; `none` or stop report.
13. Stop conditions encountered; `none` or exact disposition.
14. Explicit statement that FT1, FT2, and FT3 remain false.
15. A result disposition using exactly one value:

```text
FT0_POSITIVE
FT0_INCONCLUSIVE
FT0_NEGATIVE
```

Disposition rules:

- `FT0_POSITIVE`: all four gold queries and all adversarial guards pass with a small, comprehensible implementation; the handback may recommend FT1 design but must not implement it.
- `FT0_INCONCLUSIVE`: the fixture or semantics reveal unresolved modeling choices that prevent one coherent invariant; report them without expanding.
- `FT0_NEGATIVE`: the minimum semantics are not useful or cannot be implemented without violating the cost/scope ceiling.

## §9 Acceptance rubric

- [ ] Exactly one independently useful characterization from §1 was delivered — E1–E10.
- [ ] All four gold questions return the exact required status/value/proof/evidence — E2, E4, E5.
- [ ] Unresolved is preserved where no fictional anchor exists — E4, E6.
- [ ] Source/session metadata cannot become fictional occurrence time — E4.
- [ ] The Lysandra state is scoped to the current C1–C2 campaign arc and does not erase earlier visits — E5 and fixture inspection.
- [ ] The observed recap, not the dossier, proves the gate-arrival occurrence — E5.
- [ ] Proof paths use only fixture claims and closed evidence — E3, E9.
- [ ] Results are deterministic, copy-safe, and independent of harmless array order — E7.
- [ ] Cycles, self-edges, duplicate identities, and evidence defects fail before evaluation — E8, E9.
- [ ] The existing `temporal_scope` field is characterized only as an opaque carrier — E10.
- [ ] No production source, contract, schema, migration, dependency, API, UI, agent, or sibling repo changed — E11.
- [ ] The implementation remains under the explicit code/fixture ceiling.
- [ ] Full non-integration regression remains truthful and green or has an explicit base/head waiver — E12.
- [ ] The named FT1 successor remains unimplemented and unclaimed.

## Stop conditions

Stop and report rather than expanding if implementation discovers:

- PR #14 is not merged or its merge materially changes the predecessor boundary;
- another PR owns temporal contracts or `temporal_scope` semantics;
- the four queries require more than strict-before closure and one exact state boundary;
- source interpretation is ambiguous enough to require new corpus adjudication;
- a public or durable result/schema is needed;
- temporal claims must be materialized into `dm_union_graph_v3`;
- a production module under `src/` is needed;
- persistence, migration, API, CLI, agent tool, source opening, or UI is needed;
- provider calls or prompt calibration are proposed;
- calendar parsing, interval algebra, recurrence, duration, fuzzy resolution, or broad ontology becomes necessary;
- proof requires more fixtures, cohorts, reports, or a management surface;
- any §4 path ceiling or line-count ceiling is exceeded;
- one invariant cannot govern both ordering and the exact state-boundary probe;
- source/session metadata cannot be prevented from leaking into fictional time;
- the current opaque carrier cannot round-trip without changing its contract.

Use this stop report shape:

```text
Stop condition:
Why FT0 cannot absorb it:
Invariant clause affected:
Required evidence now missing:
New public/durable contract discovered:
Affected ownership layer:
Proposed successor or split:
Authority/tracker update needed:
```

## Appendix A — Expected gold results

The test should assert results equivalent to the following canonical values. These values belong in test expectations, not evaluator input.

```json
[
  {
    "query_id": "query:hempholm-tree-before-beetles",
    "query_kind": "strict_before",
    "status": "entailed",
    "value": true,
    "proof_claim_ids": [
      "claim:hempholm-tree-before-revelry",
      "claim:hempholm-revelry-before-beetles"
    ],
    "evidence_ids": [
      "ev:hempholm-evening-revelry",
      "ev:hempholm-root-beetle-attack",
      "ev:hempholm-tree-felled"
    ],
    "reason": null
  },
  {
    "query_id": "query:hempholm-tree-absolute-time",
    "query_kind": "absolute_fictional_time",
    "status": "unresolved",
    "value": null,
    "proof_claim_ids": [],
    "evidence_ids": [],
    "reason": "no_explicit_absolute_anchor"
  },
  {
    "query_id": "query:lysandra-returned-before-gate",
    "query_kind": "state_at_boundary",
    "status": "entailed",
    "value": false,
    "proof_claim_ids": [
      "state-boundary:lysandra-returned-at-mireward-gate"
    ],
    "evidence_ids": [
      "ev:lysandra-not-home-c1-c2"
    ],
    "reason": null
  },
  {
    "query_id": "query:lysandra-returned-after-gate",
    "query_kind": "state_at_boundary",
    "status": "entailed",
    "value": true,
    "proof_claim_ids": [
      "state-boundary:lysandra-returned-at-mireward-gate"
    ],
    "evidence_ids": [
      "ev:lysandra-mireward-gate-arrival"
    ],
    "reason": null
  }
]
```

## Appendix B — What a positive result earns

A positive FT0 result earns a design discussion, not automatic implementation.

FT1 may then consider:

- whether a versioned temporal claim belongs inside `GraphContributionAssertion.temporal_scope` or a different assertion family;
- dedicated evidence for temporal qualifiers;
- per-claim lifecycle/status rather than assertion-wide temporal status;
- deterministic partial-order and state-boundary validation in the kernel;
- revision-pinned “as of focus” read semantics;
- a named Buddy consuming surface operating in shadow mode.

FT1 must still reject source/session time leakage, provider authority, silent calendar invention, and parallel Buddy-kernel ownership.
