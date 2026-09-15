# HANDOFF — V2 generic KnowledgeReadContext + candidate admission seam

**Created:** 2026-09-15  
**Status:** ACTIVE — implementation may be dispatched only after this handoff and the accompanying Steward update are merged to `main`  
**Repository / handoff branch:** `Drakosfire/DungeonMind` / `handoff/v2-knowledge-read-context-admission`  
**Implementation branch:** `kernel/v2-knowledge-read-context-admission`  
**Predecessor:** PR #58 — `KERNEL: legacy v1–v6 compatibility decoder + semantic parity`  
**Predecessor merge:** `6c5e746d3fa3ffbbdb371ddb15d9c392ab3fd3a0`  
**Accepted predecessor head:** `b8ca0a579c00a6fde7f9ea51b6bad709cba1e71f`  
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**One-line mission:** Establish the generic, fail-closed read/admission seam that binds one exact immutable `ParsedKnowledgeRevision`, one exact request context, one coherent targeted source/provenance view, and one pinned pure domain policy—without pre-projecting the whole space or implementing V3 retrieval early.

---

## §0 Dispatch gate — do this before implementation

This handoff is being authored on a docs/handoff branch.

**Do not dispatch an external implementation agent from this branch.**

Repository process requires the implementation handoff to be:

```text
ACTIVE
+ durably checked into main
+ based on current repository truth
```

Before implementation begins:

1. merge this handoff branch to DungeonMind `main`;
2. verify `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md` on `main` records:
   - PR #58 merge `6c5e746d...`;
   - accepted head `b8ca0a57...`;
   - 4 review cycles;
   - final review `5216431557`;
   - `V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED`;
   - `V1_IMMUTABLE_NORMALIZATION_COMPLETE`;
   - `V2 ACTIVE`;
3. verify this handoff is present on `main` with status `ACTIVE`;
4. create `kernel/v2-knowledge-read-context-admission` from that then-current `main`, **not** directly from `6c5e746d...` if the docs merge has advanced main.

If the handoff is absent, non-ACTIVE, or not on `main`, stop.

The Steward update has already been authored as the first commit of this handoff branch:

```text
ea5456054ba9906fea672f1fd043164ea92d7842
STEWARDSHIP: record PR #58 merge, complete V1, and activate V2
```

The implementation agent must not recreate or supersede that authority on its own branch.

---

## §1 Outcome

The successful PR leaves DungeonMind with a generic application-layer read context and candidate-admission pipeline that can answer this question:

> Given one exact immutable `ParsedKnowledgeRevision`, one frozen `ProjectionRequest`-shaped context, one exact pinned `DomainContractDescriptor` / `SemanticProfileDescriptorV2`, one explicit registered domain policy, and one bounded set of candidate assertion IDs, which candidates are admissible under generic Kernel rules and the domain's additional narrowing policy—using only the source/provenance state required by those candidates and without projecting the whole revision?

The end state must make V3 straightforward:

```text
V3 structural candidate discovery
→ V2 context/admission seam
→ admitted exact/complete entity result
```

V2 itself does **not** expose `get_entity` or `get_complete_entity` as new public read APIs.

Only successful final disposition:

```text
V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED
```

Until that exact disposition is recorded by Steward review, V3 remains blocked from merge.

---

## §2 Authority and anchors

Read these in order before editing code.

### 2.1 Binding authority

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
   - generic scope contract;
   - generic visibility;
   - non-configurable Kernel admission;
   - pure pinned domain admission;
   - DomainContract versus SemanticProfile;
   - source/evidence model.
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
   - `KnowledgeReadContext`;
   - safe/unsafe reuse;
   - lazy candidate admission;
   - targeted coherent provenance.
4. `Docs/Roadmaps/ROADMAP.md` — V2 section.
5. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md` — current roadmap checkpoint.
6. `CONTRIBUTING.md`.

### 2.2 Frozen contracts

Read:

```text
src/dungeonmind/contracts/vnext/common.py
src/dungeonmind/contracts/vnext/domain.py
src/dungeonmind/contracts/vnext/projection.py
src/dungeonmind/contracts/vnext/source.py
src/dungeonmind/contracts/vnext/knowledge.py
Docs/Contracts/vnext/dm_vnext_contract_v1.json
```

The V0 aggregate is frozen at:

```text
fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

V2 must not change it.

### 2.3 V1 serving model

Read:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/records.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/frozen_json.py
src/dungeonmind/application/vnext/errors.py
```

V1 established immutable normalized knowledge and revision-local structural indexes. V2 consumes them; it does not redesign them casually.

### 2.4 Historical compatibility boundary

Read:

```text
src/dungeonmind/application/vnext/legacy_compat.py
Docs/Compatibility/dm_legacy_world_compat_v1.json
Docs/Compatibility/legacy_v1_v6_parity_v1.json
```

PR #58 established compatibility as a codec/proof boundary, not migration or current vNext authority.

Do not promote `dungeonmind.compat:*` compatibility metadata into new native authorization semantics merely to make a V2 test pass.

### 2.5 Current proven provenance mechanism

Read for mechanisms and security lessons, not for vocabulary to copy:

```text
src/dungeonmind/application/world_graph_read_context.py
src/dungeonmind/application/source_provenance_snapshot.py
src/dungeonmind/application/graph_scope.py
src/dungeonmind/application/repositories.py
```

R.3a earned these lessons:

- one coherent source view per read;
- source visibility before detailed lifecycle/integrity diagnostics;
- missing authority fails closed;
- per-context evidence memoization is safe;
- source/provenance verdicts are not safe to cache by graph revision alone;
- targeted/batched source loading is valuable;
- World/campaign/GM/PLAYER vocabulary is **not** reusable generic Kernel vocabulary.

---

## §3 Primary question and write lease

### Primary question

> **Can one exact `ParsedKnowledgeRevision` support coherent generic and pinned-domain admission over an arbitrary bounded candidate slice, with targeted fresh source/provenance state, without pre-projecting the entire KnowledgeSpace or changing current World runtime behavior?**

### Write lease

Expected new/modified surface is primarily:

```text
src/dungeonmind/application/vnext/
  read_context.py                 # or equivalent
  admission.py                    # or equivalent
  provenance.py                   # or equivalent
  ports.py                        # if a vNext read-only source port is separated
  errors.py                       # bounded new fail-closed errors
  __init__.py                     # narrow exports only

tests/unit/test_vnext_knowledge_read_context.py

tests/fixtures/vnext/
  <small Buddy-shaped admission fixture if useful>

Docs/Benchmarks/
  vnext_candidate_admission_10k_v1.json

benchmarks/
  <bounded candidate-admission characterization harness if needed>
```

Modifying `application/repositories.py` is acceptable only if the cleanest transport-neutral vNext read-only source port belongs there. Do not reshape old World repository contracts to make V2 generic.

Expected **zero** production behavior changes outside the isolated vNext application seam.

---

## §4 Scope

### In scope

1. A generic `KnowledgeReadContext`-equivalent immutable application object.
2. Exact request/revision/domain/profile identity verification.
3. Generic `ScopeSelector` admission.
4. Generic Public / LabelsAny / LabelsAll visibility admission.
5. Explicit standing selection with no implicit widening.
6. Candidate-local evidence/source dependency collection.
7. One coherent immutable targeted vNext provenance snapshot for a candidate admission operation.
8. A transport-neutral read-only vNext source/provenance port over `SourceArtifactV3` / `SourceRevisionV2`.
9. Per-context evidence/provenance memoization where useful.
10. Generic source lifecycle / visibility / source-revision integrity checks.
11. Explicit, pinned, pure domain-admission policy registration and invocation.
12. Domain policy as narrowing only.
13. DomainContract declaration checks relevant to admission.
14. Basic SemanticProfile predicate/value-kind conformance relevant to candidate assertions.
15. Deterministic candidate admission results/order/digests where results expose a digest.
16. Buddy-shaped opaque scope/label fixture proof without importing Buddy.
17. Non-TTRPG organizational-memory proof using the existing fixture.
18. Source freshness across contexts with the same parsed revision reused.
19. No source-state tear inside one read/context.
20. 10k candidate-local structural/work-count characterization.

### Out of scope — falsification

Do **not** implement:

```text
public get_entity
public get_complete_entity
neighborhood APIs
search APIs
anchor APIs
full-space vNext projection
KnowledgeSpace/head storage runtime
native vNext publication/writes
PostgreSQL vNext authority migration
bridge-genesis migration
DungeonBuddy production policy/runtime
DungeonBuddy dependency repin
World public-read cutover
historical-reader deletion/quarantine
vector retrieval
new distributed cache
new graph database
new durable storage model
```

If the PR needs one of those to answer the primary question, stop and rebrief.

---

## §5 Binding invariants

### 5.1 Exact immutable revision

The context operates against exactly one `ParsedKnowledgeRevision`.

Required checks:

- `request.space_id == parsed.space_id`;
- if `request.revision_id` is present, it equals `parsed.revision_id` exactly;
- if `request.revision_id` is absent, the caller-supplied parsed revision is the resolved exact revision for this context; V2 does not itself resolve a mutable head;
- candidate assertion IDs must all resolve in this exact parsed revision or the operation fails closed;
- never merge candidates from two revisions.

### 5.2 DomainContract and SemanticProfile are pinned data

The context receives exact descriptors, not merely names.

Verify:

```text
DomainContractDescriptor.domain_id/revision
+ canonical descriptor digest
== parsed.domain_contract_ref

SemanticProfileDescriptorV2.profile_id/revision
+ canonical descriptor digest
== parsed.semantic_profile_ref
```

Mismatch is a context-construction failure.

Do not trust a descriptor because its ID string looks right.

### 5.3 Request vocabulary must be declared

Fail closed when the request uses undeclared authorization vocabulary:

- every scope binding/wildcard axis must exist in `DomainContractDescriptor.scope_axes`;
- every effective audience label must exist in `DomainContractDescriptor.visibility_labels`.

`focus` and `domain_context` remain context/ranking/domain-policy inputs. They are not generic authorization dimensions.

### 5.4 Candidate domain declarations

Before custom domain policy, a candidate assertion must be structurally compatible with the pinned domain contract:

- each assertion scope axis is declared;
- each assertion visibility label is declared;
- `claim_mode` is declared;
- `domain_ref` temporal schema is declared when present;
- assertion domain-metadata schemas are declared;
- source/evidence domain annotation schemas are declared where the frozen contract design assigns them to `source_annotation_schemas`.

Do not interpret the business/domain meaning of these terms.

### 5.5 SemanticProfile candidate conformance

For a native vNext candidate:

- the assertion predicate must be present in the pinned profile descriptor when the profile defines predicate admission;
- the assertion value kind must be one of that predicate's declared `allowed_value_kinds`.

Do not invent a JSON-Schema dialect for `literal_schema` in this PR. If a required fixture depends on executable literal-schema validation and no current canonical rule defines the dialect/behavior, stop and rebrief rather than silently ignoring or inventing semantics.

Do not invent generic semantics for `classification_terms` beyond what the frozen profile contract already states.

### 5.6 Scope semantics are exact

For an assertion with no scope bindings:

```text
admitted by generic scope iff request.scope_selector.include_unscoped == true
```

For each assertion `ScopeBinding(axis, value)`, at least one must hold:

```text
request has exact axis/value binding
OR
request wildcard_axes contains axis
```

All assertion scope bindings must be satisfied.

Extra request bindings do not manufacture assertion scope.

### 5.7 Visibility semantics are exact

Generic visibility only:

```text
Public          → visible
LabelsAny(X)    → audience ∩ X is non-empty
LabelsAll(X)    → X ⊆ audience
```

Unknown/undeclared labels fail closed.

Product authorization that determines which audience labels a caller is allowed to claim remains outside DungeonMind.

### 5.8 Standing is explicit

An assertion's standing must be explicitly selected by the request before it may proceed.

Do not invent an implicit "all standings" default.

If `standing_selector` is empty, the implementation may reject the context/request or admit zero candidates, but it must never widen to all standings.

If choosing between those two fail-closed surfaces has externally visible consequences beyond this isolated seam, stop and record the decision before proceeding.

### 5.9 Temporal metadata does not silently consult wall clock

V2 has no canonical `as_of` clock selector.

Therefore:

- do not call the system clock to admit/exclude `utc_interval` assertions;
- preserve temporal metadata for the domain/presentation layer;
- a pure domain policy may only use explicit immutable context supplied to it;
- if correct temporal admission requires a new request-time reference, that is a contract/architecture question and a stop condition.

### 5.10 Evidence is candidate-local

For candidate assertions, derive only their referenced evidence IDs and source identities.

Do not scan every evidence record in the revision to decide a small candidate set.

Assertions with zero evidence refs are not automatically rejected merely because they are evidence-less; the frozen contract permits an empty list. Generic source validity applies to referenced evidence. A domain policy may narrow evidence-less assertions if its domain requires support.

### 5.11 Generic source/provenance validity

For each referenced evidence record:

1. exact `EvidenceRefV3` / normalized evidence identity exists in the parsed revision;
2. referenced source artifact exists in the coherent source snapshot;
3. source artifact visibility is evaluated before detailed lifecycle/integrity diagnostics are exposed;
4. artifact status must be `active` for the evidence chain to be valid;
5. if an exact source revision is referenced:
   - it exists in the same coherent source snapshot;
   - its `source_artifact_id` equals the evidence artifact ID;
6. missing or malformed authority fails closed.

Do **not** require `EvidenceRef.source_revision_id == SourceArtifact.current_revision_id`. Exact older immutable source revisions may remain valid support; the current architecture does not establish current-revision equality as a generic evidence-validity rule.

`authority`, `source_classification`, and domain-specific source annotations are available to the domain policy but do not receive invented Kernel meaning in this PR.

### 5.12 Source visibility before diagnostics

Preserve the earned non-leak ordering from the current World path:

```text
establish source visibility
→ only then inspect/expose detailed lifecycle/revision-integrity reasons
```

If the artifact is missing or its visibility cannot be safely established, fail closed without emitting sensitive source IDs through a caller-facing result surface.

The exact internal result types are implementation choices; the non-leak behavior is binding.

### 5.13 One coherent targeted source view

A V2 candidate-admission operation must not stitch together independent source reads that can observe mutually inconsistent authority states.

Preferred simple shape:

```text
candidate IDs resolved structurally
→ collect required source artifact/revision IDs
→ one targeted repository snapshot call
→ immutable KnowledgeReadContext / provenance snapshot
→ admission
```

An alternative incremental snapshot/session API is acceptable only if it proves all loads in one context share one coherent underlying source state.

Multiple ordinary repository reads with no coherence boundary are not acceptable.

### 5.14 Freshness across contexts

Reusing the same immutable `ParsedKnowledgeRevision` across requests is safe.

Reusing source-authority/admission verdicts by revision alone is not.

Test:

```text
context A over revision R → source active → candidate admitted
mutate live source authority
context B over same exact revision R → source changed → candidate result changes
context A remains internally coherent/unchanged
```

### 5.15 Domain policy is pure narrowing

The domain contract descriptor stays data-only.

A runtime policy seam may look conceptually like:

```text
DomainAdmissionPolicy
  policy_id
  evaluate(candidate, immutable_domain_context) -> ADMIT | EXCLUDE
```

Exact API is flexible. Binding constraints:

- explicit registry/constructor injection only;
- no dynamic import/eval from `admission_policy_id`;
- exact policy identity must match the pinned descriptor/ref context;
- policy receives already Kernel-admissible candidate data only;
- policy receives no repository, database, network client, mutable graph, or clock capability;
- policy may return ADMIT for a Kernel-admissible candidate or EXCLUDE it;
- policy is never called in a way that can recover a candidate already rejected by generic admission;
- missing/unknown/mismatched policy fails closed;
- repeated evaluation over equal immutable inputs is deterministic in tests.

Python cannot sandbox arbitrary imported code merely by declaring it pure. V2 proves **capability purity**: DungeonMind does not hand the policy I/O/clock/mutation capabilities and does not dynamically load arbitrary code. If a stronger execution sandbox is required, stop rather than pretending it exists.

### 5.16 Native vNext proof, not accidental legacy promotion

Primary V2 acceptance should use native vNext fixtures built from the frozen V0 contracts.

The v1–v6 compatibility codec remains available for semantic/migration proof, but V2 must not silently reinterpret compatibility-coarse fields as native domain authorization.

Current World runtime remains untouched until the later migration/cutover phases.

---

## §6 Suggested internal architecture

The exact names are not binding, but this decomposition keeps ownership clean.

### 6.1 `KnowledgeProvenanceSnapshot`

Immutable application-layer view containing only requested:

```text
SourceArtifactV3 by id
SourceRevisionV2 by id
requested ids
missing ids
stable fingerprint / snapshot identity for proof
```

It is not durable authority and not a cross-request admission cache.

### 6.2 `KnowledgeSourceReader` port

Transport-neutral read-only protocol, conceptually:

```text
get_provenance_snapshot(
    artifact_ids: Sequence[str],
    revision_ids: Sequence[str],
) -> KnowledgeProvenanceSnapshot
```

V2 may prove this with an in-memory adapter/test double.

Do not require PostgreSQL vNext persistence.

### 6.3 `KnowledgeReadContext`

Conceptually binds:

```text
ParsedKnowledgeRevision
ProjectionRequest context
pinned DomainContractDescriptor
pinned SemanticProfileDescriptorV2
explicit DomainAdmissionPolicy
one coherent targeted provenance snapshot
per-context evidence resolution memo
```

The context is one-read application state, not durable authority, agent memory, or a product session.

### 6.4 Admission result

An internal deterministic result should make it possible to test:

```text
admitted assertion IDs
excluded assertion IDs
non-sensitive exclusion classes
work counts / requested source IDs
```

Do not design a final public error/coverage DTO in V2 unless V3 demonstrates it is needed.

---

## §7 Required fixtures and semantic witnesses

### 7.1 Existing organizational-memory fixture

Use:

```text
tests/fixtures/vnext/organizational_memory_v1.json
```

It already provides:

- a non-TTRPG DomainContract;
- project/team scope axes;
- team/leadership visibility labels;
- established claims;
- unscoped knowledge;
- `SourceArtifactV3` with `LabelsAll(organization:team)` visibility;
- two exact immutable source revisions;
- evidence refs pinned to different source revisions.

This should be the primary generic witness.

### 7.2 Buddy-shaped opaque fixture

Add a small test-only fixture if needed, using the exact frozen V0.2 semantic mapping vocabulary as **opaque qualified terms**, not Kernel enums:

```text
domain: dungeonbuddy.world / 1
scope axis: dungeonbuddy.scope:campaign
visibility labels:
  dungeonbuddy.visibility:player
  dungeonbuddy.visibility:gm
claim modes representative:
  dungeonbuddy:fact
  dungeonbuddy:belief
  dungeonbuddy:rumor
  dungeonbuddy:plan
  dungeonbuddy:observed_event
```

Required request cases:

```text
campaign C2 + player labels
campaign C2 + gm+player labels
world/cross-campaign wildcard + gm+player labels
session FocusRef with otherwise identical admission context
```

Prove:

- unscoped assertions are included only with `include_unscoped=true`;
- C2 does not admit C3 without wildcard;
- GM-only content is hidden from player labels;
- GM effective labels can see both player and GM visibility requirements;
- session focus does not alter generic scope/visibility admission;
- provisional content appears only when explicitly selected.

No import or dependency on DungeonMindBuddy is allowed.

### 7.3 Domain-policy narrowing fixture

At least one explicit test policy must exclude a candidate that passed all generic Kernel checks.

Also prove:

- the policy is not invoked for a generic-rejected candidate;
- changing policy identity without changing the pinned descriptor fails closed;
- unknown policy fails closed;
- an attempted "ADMIT" result cannot resurrect a generic-rejected candidate because it never reaches policy evaluation.

---

## §8 Acceptance matrix

The implementation may organize tests differently, but the following proofs are required.

### A. Exact identity / pinning

1. request `space_id` mismatch fails closed;
2. explicit request `revision_id` mismatch fails closed;
3. unknown candidate assertion ID fails closed;
4. DomainContract ID mismatch fails closed;
5. DomainContract revision mismatch fails closed;
6. DomainContract descriptor digest mismatch fails closed;
7. SemanticProfile ID/revision/digest mismatch fails closed;
8. frozen V0 aggregate remains exact.

### B. Request/domain vocabulary

9. unknown request scope axis fails closed;
10. unknown wildcard scope axis fails closed;
11. unknown audience label fails closed;
12. assertion using undeclared scope axis fails closed;
13. assertion using undeclared visibility label fails closed;
14. undeclared claim mode fails closed;
15. undeclared domain temporal schema fails closed;
16. undeclared domain metadata/source annotation schema fails closed where applicable.

### C. Generic scope

17. unscoped + `include_unscoped=false` excludes;
18. unscoped + `include_unscoped=true` admits when other gates pass;
19. exact axis/value binding admits matching scoped assertion;
20. mismatched value excludes;
21. wildcard axis admits any value on that declared axis;
22. multi-axis assertion requires all bindings satisfied.

### D. Generic visibility

23. Public passes with empty audience;
24. LabelsAny passes on one matching declared label;
25. LabelsAny excludes with no match;
26. LabelsAll requires every label;
27. source artifact visibility can exclude an otherwise visible assertion.

### E. Standing / context separation

28. established/provisional/retracted are eligible only when explicitly selected;
29. empty standing selector never widens to all;
30. FocusRef does not change generic admission;
31. domain_context does not change generic admission before domain policy.

### F. SemanticProfile

32. declared predicate/value kind passes;
33. unknown predicate fails closed when the pinned profile is authoritative for predicate admission;
34. disallowed value kind fails closed;
35. no invented literal-schema or classification-term semantics.

### G. Provenance integrity

36. missing source artifact excludes/fails closed;
37. source visibility is established before detailed inactive/revision diagnostics;
38. inactive/superseded/retracted source artifact makes referenced evidence invalid;
39. missing referenced source revision makes chain invalid;
40. source revision pointing to another artifact makes chain invalid;
41. exact older source revision remains valid when artifact current revision differs;
42. unrelated sources are not loaded for a bounded candidate set;
43. duplicate evidence/source IDs are deduplicated before repository load;
44. context source snapshot is deeply immutable against caller mutation.

### H. Coherence / freshness

45. one admission operation uses one coherent targeted source snapshot;
46. mutating backing source state after context A is built does not mutate context A;
47. context B over the same exact parsed revision observes the changed source state;
48. parsed revision reuse does not reuse stale source-admission verdicts.

### I. Domain policy

49. exact registered policy identity resolves;
50. missing policy fails closed;
51. mismatched policy identity fails closed;
52. policy can exclude a generic-admitted candidate;
53. policy never sees a generic-rejected candidate;
54. policy cannot broaden/recover rejected knowledge;
55. equal immutable inputs produce deterministic policy result.

### J. Cross-domain proof

56. organizational-memory fixture passes expected admissions;
57. Buddy-shaped campaign/player fixture reproduces expected generic admission;
58. Buddy GM effective labels reproduce expected visibility without a Kernel GM enum;
59. Buddy session focus changes no generic authority verdict;
60. no generic application module imports `dungeonmind_dnd` or DungeonMindBuddy code.

### K. Regression / boundary

61. V1.1 normalized-model suite remains green;
62. V1.2 compatibility/parity suite remains green;
63. historical reader files remain at pinned content digests;
64. current public World services/retrieval behavior is unchanged;
65. frozen V0 contract generator `--check` remains exact.

The number 65 is not itself authority. If the implementation exposes another path that can weaken these invariants, add the needed proof.

---

## §9 Performance / structural-work characterization

V2 is not a latency-optimization contest, but it must prove the intended work shape.

Add:

```text
Docs/Benchmarks/vnext_candidate_admission_10k_v1.json
```

Use a deterministic native-vNext synthetic workload or a clearly identified derived fixture.

Minimum workload:

```text
~10k assertions
non-trivial evidence/source cardinality
candidate batches at small and moderate sizes (for example 1 / 10 / 100)
```

Record:

```text
exact base/head
fixture/workload digest
parsed semantic digest
candidate assertion count
candidate evidence count
unique artifact IDs requested
unique source revision IDs requested
repository snapshot-call count
assertions actually evaluated
policy evaluations
p50/p95 admission time if measured meaningfully
peak traced memory if practical
```

Binding structural proof:

> For a small candidate set, provenance/source work is proportional to the candidate support set, not to all evidence/sources in the 10k revision.

A single targeted snapshot call is the preferred witness.

Do not claim 100k behavior from a 10k run.

No V2 absolute latency gate is required. Preserve semantic proof before performance credit.

---

## §10 Work plan

### Step 1 — re-anchor and freeze the implementation base

After the docs handoff merges:

```bash
git fetch origin
git switch main
git pull --ff-only
git rev-parse HEAD
```

Create:

```text
kernel/v2-knowledge-read-context-admission
```

Record exact base SHA in the PR body.

Verify Steward and this handoff are on that base.

### Step 2 — context identity and descriptor pinning

Implement the minimal immutable context construction surface and fail-closed identity checks.

Do not add retrieval yet.

### Step 3 — generic admission primitives

Implement pure functions for:

```text
standing
scope
visibility
DomainContract declaration checks
basic SemanticProfile predicate/value-kind checks
```

Keep them independently testable.

### Step 4 — targeted provenance port/snapshot

Implement the vNext read-only source snapshot abstraction.

Prove one coherent candidate-local load and deep immutability.

### Step 5 — evidence/source admission

Resolve evidence chains against the context snapshot with per-context memoization.

Preserve source visibility-before-diagnostics ordering.

### Step 6 — pinned domain policy registry

Add explicit policy registration/resolution and pure narrowing evaluation.

No dynamic import by policy ID.

### Step 7 — candidate orchestration

Wire the above into one deterministic candidate-admission operation.

The operation starts with assertion IDs already structurally selected by V1 indexes and ends with admitted/excluded candidate results.

No entity DTO assembly.

### Step 8 — cross-domain fixtures and adversarial tests

Use organizational memory plus the Buddy-shaped opaque fixture.

Run the complete acceptance matrix.

### Step 9 — 10k structural characterization

Generate/check in the benchmark artifact and a deterministic `--check` path if practical.

### Step 10 — regression gates and handback

Run exact gates below, report inherited failures honestly, and hand back exact base/head/PR identity.

---

## §11 Acceptance commands

Adjust only for actual file names introduced by the implementation; do not weaken the gates.

Focused:

```bash
uv sync --locked

uv run pytest -q \
  tests/unit/test_vnext_knowledge_read_context.py \
  tests/unit/test_vnext_parsed_knowledge_revision.py \
  tests/unit/test_vnext_legacy_compatibility.py
```

Relevant contract/conformance:

```bash
uv run pytest -q -m conformance
uv run python scripts/generate_vnext_contract_bundle.py --check
uv run python scripts/generate_legacy_compatibility_parity_artifact.py --check
```

Quality:

```bash
uv run ruff check .
uv run pyright
git diff --check
```

Repository default/core/integration posture:

- run the repository's current normal unit/default suite;
- require core CI green;
- require integration CI green unless a failure is proven inherited on exact base and untouched by this PR;
- classify `benchmark-smoke` against the exact base.

Known inherited baseline entering V2:

```text
benchmark-smoke currently fails in benchmarks/world_graph_reads.py because
WorldGraphProjectionService construction is missing reviewed_world_initializations.
```

This inherited red is not permission for a new V2 benchmark failure.

Benchmark artifact check should be deterministic if a generator/check script is added, e.g.:

```bash
uv run python benchmarks/vnext_candidate_admission.py --check
```

Do not invent that exact filename if a cleaner repository convention is chosen; report the real command.

---

## §12 Stop conditions

Stop and hand back instead of improvising if any of the following occurs.

### Contract / architecture

1. Frozen V0 contract bundle must change.
2. V2 needs a new generic field to express Buddy-shaped semantics.
3. Correct temporal admission requires an `as_of`/clock contract not currently present.
4. `literal_schema` requires an unchosen executable schema dialect to prove required semantics.
5. `focus` must become hidden authorization.
6. Domain policy must broaden generic admission.
7. Domain policy requires arbitrary dynamic plugin loading.
8. Domain policy requires storage/network/clock/mutation capability.

### Provenance

9. Candidate-local provenance cannot be coherent without preloading all source state.
10. One context requires multiple independent live source reads that can tear.
11. Correct generic evidence validity requires a new source lifecycle rule not established by current architecture.
12. Source freshness can only be achieved by revision-only caching of mutable verdicts.
13. Hidden source identity would have to leak through detailed rejection diagnostics.

### V1 / compatibility

14. V2 requires rewriting `ParsedKnowledgeRevision` authority semantics rather than consuming it.
15. Historical v1–v6 payloads must be rewritten.
16. Compatibility-coarse legacy metadata must be promoted into native authorization semantics.
17. Historical reader semantics must change.

### Scope creep

18. `get_entity` / `get_complete_entity` must be implemented to prove V2.
19. Current World public reads must change.
20. PostgreSQL vNext schema migration is required.
21. Bridge genesis/cutover must begin.
22. DungeonMind needs a dependency on DungeonMindBuddy or `dungeonmind_dnd` in generic vNext application code.
23. Storage redesign is required.

### Evidence

24. Tests can pass only by weakening a fail-closed expectation.
25. Source freshness/coherence cannot be demonstrated.
26. 10k work counts reveal the implementation scans full revision/source state for a small candidate set.

Required stop report:

```text
Stop condition:
Exact base/head:
Observed evidence:
Which assumption failed:
Affected authority/architecture document:
Why this PR cannot safely compensate:
Proposed design decision / experiment:
What remains safe in parallel:
```

If the decision is architectural, update the canonical architecture/roadmap before resuming implementation.

---

## §13 PR description / review contract

The implementation PR body must contain:

```text
Primary question
Exact base SHA
Exact current head SHA
Intended changed surface
Frozen V0 aggregate
Binding invariants
Domain-policy identity design
Source coherence design
Required semantic evidence
Actual test/benchmark evidence
Known inherited failures
What remains false
Named successor
```

Steward review must inspect the exact head and explicitly verify:

- no whole-space projection hidden inside context construction;
- no all-source snapshot hidden behind the targeted provenance interface;
- no source verdict cached by revision alone;
- no dynamic policy import;
- policy cannot see generic-rejected candidates;
- focus/domain context did not become hidden authorization;
- no current World path changed;
- no V0 contract drift;
- 10k work counts match the claimed structure.

Potential final disposition:

```text
PASS — V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED
```

If a docs/test-only finalization commit is needed after substantive PASS, anchor any acceptance artifact to the accepted substantive head rather than requiring self-reference.

---

## §14 What remains false after a successful V2

Even after V2 passes:

- there is no new public `get_entity` or `get_complete_entity` vNext read;
- there is no bounded neighborhood/search/anchor vNext service;
- there is no current `KnowledgeSpace` durable runtime/head migration;
- current public World readers still own production reads;
- no native vNext write/publication runtime exists;
- DungeonBuddy has not implemented its production vNext domain runtime;
- no bridge-genesis migration has occurred;
- no vNext authority has replaced current World authority;
- no cutover has occurred;
- historical readers remain required;
- larger 50k/100k characterization remains incomplete;
- V11 storage optimization remains unauthorized.

Do not describe V2 as a runtime cutover.

---

## §15 Named successor and mandatory Steward mutation

If V2 merges with:

```text
V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED
```

then the named successor is:

```text
V3 — lazy exact / complete entity reads
```

The **first bookkeeping commit of the V3 successor branch**, before substantive V3 implementation, must update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
```

with:

```text
V2 PR number/title
actual V2 merge SHA
accepted V2 implementation head
review-cycle count
final PASS review ID
V2 disposition
candidate-admission benchmark artifact + key digests/work counts
V2 COMPLETE
V3 ACTIVE
updated remains-false list
V3 primary question
```

Do not allow V3 to merge while the Steward handoff still says V2 is active.

V3 primary question is expected to remain:

> Can exact entity truth be returned with work proportional to the selected entity and its support rather than the whole space?

The V3 handoff must be designed from the actual accepted V2 implementation, not merely copied from the roadmap.

---

## §16 Handback requirements

Return all of the following.

### Repository identity

```text
repo
branch
exact base SHA
exact head SHA
PR number/title/url
mergeability/status
```

### Decisions

For each material implementation choice:

```text
question
evidence
decision
rejected alternatives
consequences
reversal path
```

At minimum cover:

- context lifetime/coherence mechanism;
- vNext source reader/snapshot shape;
- domain policy registry identity;
- empty standing-selector behavior;
- diagnostic privacy shape;
- SemanticProfile conformance boundary.

### Verification

Exact commands/results for:

- focused V2 tests;
- V1.1 regression;
- V1.2 parity regression;
- contract bundle check;
- conformance;
- ruff;
- pyright;
- diff check;
- default/core/integration tests;
- benchmark generation/check;
- CI status and inherited red classification.

### Evidence artifact

Report:

```text
Docs/Benchmarks/vnext_candidate_admission_10k_v1.json
workload digest
semantic digest
candidate cardinalities
source IDs requested
snapshot call counts
policy evaluation counts
latency/memory observations if measured
```

### What remains false

Copy the explicit §14 list and update only facts actually changed by the implementation.

### Successor

Name V3 only after V2 receives Steward PASS.
