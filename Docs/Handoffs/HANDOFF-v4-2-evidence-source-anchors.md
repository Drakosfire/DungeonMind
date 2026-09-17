# HANDOFF — V4.2 evidence reads + source anchors

**Created:** 2026-09-16
**Status:** ACTIVE / IMPLEMENTATION NOT YET ACCEPTED — V4.1 accepted and merged; V4.2 may begin from exact current `main`
**Repository:** `Drakosfire/DungeonMind`
**Implementation branch:** `kernel/v4-2-evidence-source-anchors`
**Exact implementation base:** `7f5df9eace6f1ab23a0d817e0b350c379923641f`
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`
**Roadmap phase:** V4.2 — evidence + source-anchor support
**Successor:** V4.3 — deterministic indexed search
**One-line mission:** Make exact assertion support, exact evidence support, deterministic source-anchor creation, and source-anchor revalidation first-class bounded vNext reads without full projection, without evidence becoming independent authority, and without anchors becoming authorization tokens.

---

# 0. Repository truth and predecessor

V4.1 is complete.

Binding predecessor facts:

```text
PR:
  #66 — KERNEL: V4.1 bounded neighborhood reads

accepted head:
  9b0fd143552ea5e4def3f4a7c8d08050b206eb52

substantive repair head:
  626a5fcd2bea3395c62d62aa091b7c666b2ab26f

logical Steward review cycles:
  3

final PASS review:
  5230663567

disposition:
  V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED

actual merge:
  7f5df9eace6f1ab23a0d817e0b350c379923641f

benchmark:
  Docs/Benchmarks/vnext_neighborhood_10k_v1.json

benchmark substantive head:
  626a5fcd2bea3395c62d62aa091b7c666b2ab26f

structural gate:
  PASS

10k low-degree depth-1 p95:
  ~1.97 ms
```

Current `main` is exactly the V4.1 merge:

```text
7f5df9eace6f1ab23a0d817e0b350c379923641f
```

Do not branch from draft PR #65.

Do not cherry-pick PR #65.

PR #65 is superseded design history. Its useful design conclusions are incorporated into this handoff. It must remain unmerged and should be closed as housekeeping once this implementation PR exists.

---

# 1. Process rule

Handoffs do not get standalone PRs.

This handoff belongs to the **V4.2 implementation PR**.

Correct sequence:

```text
current main after V4.1
        ↓
create kernel/v4-2-evidence-source-anchors
        ↓
first commit:
  durable Steward bookkeeping
  mark V4.1 COMPLETE
  mark V4.2 ACTIVE
  add this V4.2 handoff
  repair stale V4.1 handoff status
        ↓
implementation
        ↓
tests
        ↓
benchmark / characterization artifact
        ↓
Steward exact-head review
        ↓
PASS + merge
```

Do not create a bookkeeping-only PR.

Do not create another handoff PR.

---

# 2. First commit — bookkeeping before runtime

Create the implementation branch from exact `main`:

```text
kernel/v4-2-evidence-source-anchors
base:
7f5df9eace6f1ab23a0d817e0b350c379923641f
```

The first commit must contain **no V4.2 production runtime implementation**.

Suggested commit:

```text
STEWARDSHIP: complete V4.1 and activate V4.2
```

Update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v4-1-bounded-neighborhood.md
Docs/Handoffs/HANDOFF-v4-2-evidence-source-anchors.md
```

Record durably:

```text
PR #66:
  KERNEL: V4.1 bounded neighborhood reads

accepted head:
  9b0fd143552ea5e4def3f4a7c8d08050b206eb52

substantive repair head:
  626a5fcd2bea3395c62d62aa091b7c666b2ab26f

review cycles:
  3

final PASS:
  5230663567

disposition:
  V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED

merge:
  7f5df9eace6f1ab23a0d817e0b350c379923641f

benchmark:
  Docs/Benchmarks/vnext_neighborhood_10k_v1.json

V4.1:
  COMPLETE

V4.2:
  ACTIVE
  IMPLEMENTATION NOT YET ACCEPTED

V4.3:
  BLOCKED ON V4.2 ACCEPTANCE

V5:
  BLOCKED ON V4.3 ACCEPTANCE
```

The V4.1 handoff currently reflects its pre-merge review state. Advance it to accepted/complete truth.

Add this handoff as:

```text
Docs/Handoffs/HANDOFF-v4-2-evidence-source-anchors.md
```

Then begin runtime implementation.

---

# 3. Required reading

Read, in order:

```text
Docs/Architecture/AUTHORITY.md
Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md
Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v4-1-bounded-neighborhood.md
this handoff
```

Then inspect:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/records.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/read_context.py
src/dungeonmind/application/vnext/provenance.py
src/dungeonmind/application/vnext/entity_reads.py
src/dungeonmind/application/vnext/neighborhood.py

src/dungeonmind/contracts/vnext/source.py
src/dungeonmind/contracts/vnext/projection.py
src/dungeonmind/contracts/vnext/domain.py
```

The frozen V0 contracts are authority.

Do not alter them merely because an application-level anchor DTO would be easier with another field.

---

# 4. Primary question

Answer exactly this:

> Can exact assertion/evidence support and context-bound source anchors be retrieved and revalidated through revision-local `assertion_evidence` / `evidence_supporters` indexes plus candidate-local V2 admission/provenance, with work proportional to the exact requested support set rather than the whole KnowledgeSpace?

Only successful disposition:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```

Do not claim that disposition yourself.

It belongs to Steward exact-head review.

---

# 5. What V4.2 finishes

V3 established:

```text
admitted entity assertions
→ direct evidence/source support
```

V4.1 established:

```text
admitted traversal assertions
→ direct evidence/source support
```

V4.2 makes support itself independently addressable:

```text
exact assertion
→ admitted assertion
→ exact evidence

exact evidence
→ exact structural supporter assertions
→ admitted supporters
→ evidence/source authority

admitted evidence
→ deterministic source anchor

source anchor
→ exact evidence target
→ fresh admission/provenance revalidation
→ valid or unavailable
```

V4.2 does **not** implement search.

That is V4.3.

---

# 6. Existing structural substrate

Use the existing immutable revision-local indexes.

Relevant structures are conceptually:

```text
assertions_by_id

assertion_evidence
  assertion_id
  → evidence_ref_ids

evidence_by_id

evidence_supporters
  evidence_ref_id
  → assertion_ids
```

These indexes are derived/rebuildable revision state.

They provide structural candidates.

They do **not** authorize those candidates.

Authority still comes through the pinned `KnowledgeReadContext` and V2 candidate admission.

---

# 7. Fundamental authority rule

This is the most important V4.2 rule:

> Evidence is not independently public.

An `EvidenceRef` may be returned through V4.2 only when the current pinned context establishes at least one **admitted assertion supporter** for that evidence.

The authority shape is:

```text
EvidenceRef
    ↑
assertion cites evidence
    ↑
assertion passes Kernel admission
    ↑
domain policy may narrow
```

Not:

```text
caller knows evidence ID
→ therefore evidence is readable
```

And not:

```text
caller possesses source anchor
→ therefore evidence is readable
```

---

# 8. Assertion-backed evidence only

`IdentityAlias` may carry `evidence_ref_ids`.

That remains valid V1 structure.

It is **not** a V4.2 authorization path.

Therefore:

```text
assertion-backed evidence
  eligible for V4.2 authority evaluation

alias-only evidence
  structurally valid
  not independently returnable by V4.2

evidence with no assertion supporters
  not returnable by V4.2
```

Do not:

```text
scan aliases_by_id
scan every IdentityAlias.evidence_ref_ids
add evidence_alias_supporters
put alias IDs into evidence_supporters
treat an alias like an assertion
```

Do not label an unavailable record “orphan” merely because `evidence_supporters` is empty.

It could be alias-only.

V4.2 does not need to know which.

Public result:

```text
unavailable
```

for both.

Alias-backed evidence authority can be designed later if a real workflow requires it.

---

# 9. Public privacy rule

These cases must have the same public-safe unavailable posture:

```text
target does not exist
target exists but no assertion supports it
target is alias-only
all assertion supporters are hidden
all supporters are out of scope
all supporters are standing-excluded
all supporters are domain-policy excluded
source authority makes all supporters inadmissible
```

Do not expose:

```text
hidden assertion IDs
hidden predicates
hidden subjects
hidden source IDs
hidden locators
hidden URIs
hidden spans
V2 exclusion reasons
candidate counts that reveal hidden supporters
```

Caller-supplied IDs/tokens may be echoed because the caller supplied them.

---

# 10. Important diagnostics/privacy distinction

V4.2 must prove structural locality, which requires honest work counts.

But raw supporter counts can themselves reveal hidden structure.

Example:

```text
missing evidence:
  supporter candidates = 0

hidden-only evidence:
  supporter candidates = 7
```

Returning those counts in the public result would defeat the public-safe unavailable contract.

Therefore V4.2 has two layers:

```text
PUBLIC SEMANTIC RESULT
  no hidden-candidate work telemetry

INTERNAL / CHARACTERIZATION TRACE
  exact lookup counts
  supporter candidate counts
  assertions evaluated
  policy evaluations
  artifact/revision IDs requested
  provenance snapshot calls
```

The raw structural trace is for:

```text
tests
benchmark characterization
engineering observability
Steward evidence
```

It is **not** part of the exported semantic DTO.

Do not hash it into the semantic result digest.

Do not export an API that lets an unauthorized caller use diagnostics to distinguish missing from hidden.

A package-private/internal diagnostic structure is acceptable.

Exact mechanism is implementation latitude.

---

# 11. Operation A — exact assertion evidence

Preferred conceptual API:

```python
EvidenceReadService.get_assertion_evidence(
    context: KnowledgeReadContext,
    assertion_id: str,
) -> AssertionEvidenceResult
```

Exact naming may differ.

## 11.1 Structural lookup

```text
caller assertion ID
→ exact assertion lookup
```

No:

```text
alias fallback
label fallback
substring lookup
search
nearest match
```

## 11.2 Admission

If the assertion exists structurally:

```text
evaluate exactly that assertion through V2
```

Only an admitted assertion may expose evidence.

## 11.3 Public unavailable behavior

Both:

```text
assertion missing
assertion structurally present but excluded
```

return the same public-safe unavailable shape.

Illustratively:

```python
AssertionEvidenceResult(
    requested_assertion_id="...",
    available=False,
    assertion=None,
    evidence=(),
    source_artifacts=(),
    source_revisions=(),
    anchors=(),
    result_digest="...",
)
```

Exact shape is implementation latitude.

Do not expose the V2 exclusion reason.

## 11.4 Available assertion

If admitted:

```text
assertion_evidence[assertion_id]
→ exact evidence records
→ exact source artifact/revision records already proven by the V2 evaluation
→ one deterministic anchor per returned evidence record
```

Return only the evidence directly cited by that assertion.

Do not expand:

```text
other assertions sharing that evidence
other evidence from nearby entities
aliases
graph neighbors
```

## 11.5 Empty evidence is valid

If an assertion is admitted and legitimately cites zero evidence records:

```text
available = true
assertion returned
evidence = ()
anchors = ()
```

Do not invent a missing-evidence error unless existing admission semantics already reject the assertion.

---

# 12. Operation B — exact evidence lookup

Preferred conceptual API:

```python
EvidenceReadService.get_evidence(
    context: KnowledgeReadContext,
    evidence_ref_id: str,
) -> EvidenceLookupResult
```

## 12.1 Structural shape

```text
exact evidence_ref_id
→ evidence_by_id lookup
→ evidence_supporters[evidence_ref_id]
→ exact assertion supporter IDs
→ evaluate supporter assertions through V2
```

This is the central V4.2 locality witness.

Do not discover supporters by scanning:

```text
all assertions
assertion metadata
all entity reads
full projection
all aliases
```

## 12.2 Missing target

If `evidence_by_id` misses:

```text
available = false
```

No supporter scan.

No source access.

## 12.3 Zero assertion supporters

If the evidence structurally exists but:

```text
evidence_supporters[evidence_ref_id] = ()
```

return:

```text
available = false
```

Do not inspect aliases to determine whether the record is alias-only or truly unsupported.

## 12.4 Supporter admission

Evaluate the **complete exact supporter set**.

If zero supporters are admitted:

```text
available = false
```

If one or more are admitted:

```text
available = true
```

Return:

```text
the requested EvidenceRef
only admitted supporter assertions
the requested evidence's source artifact/revision support
one deterministic source anchor for the requested evidence
```

## 12.5 Mixed visibility

Given:

```text
E supported by:
  S1 admitted
  S2 hidden
  S3 out of scope
```

return:

```text
E
S1
source support for E
anchor for E
```

Never:

```text
S2 ID
S3 ID
their predicates/subjects
their unrelated evidence
their source records
```

## 12.6 Important targeted-support rule

V2 may load provenance needed to decide every supporter assertion.

Some supporter assertions may cite evidence in addition to the requested target.

That provenance is admission input.

It is **not** automatically output.

For `get_evidence(E)`:

```text
return E's source support
not every evidence/source record consulted while evaluating E's supporters
```

This avoids turning an exact evidence read into a transitive evidence dump.

---

# 13. High-support evidence

An evidence record may have many real supporter assertions.

V4.2 must evaluate the complete supporter set if it claims complete support.

No ordinary cap such as:

```text
32 supporters
64 supporters
100 supporters
```

may silently truncate and still call the result complete.

Expected cost:

```text
O(exact supporter set
  + evidence/source dependencies required to admit those supporters)
```

That is acceptable.

The claim is locality, not constant-time truth.

---

# 14. Source-anchor model

A source anchor is:

> A deterministic, context-bound reference to an exact evidence location that has already passed V4.2 evidence authority.

It is not:

```text
an authority record
a database row
a capability granting access
a bearer token
a permission cache
a source-body cache
a globally searchable locator
```

Possessing an anchor never bypasses admission.

---

# 15. SourceAnchor DTO

Illustrative immutable DTO:

```python
@dataclass(frozen=True, slots=True)
class SourceAnchor:
    anchor_id: str

    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None

    evidence_role: str
    can_open_source: bool
    can_highlight_span: bool

    locator: str | None
    uri: str | None
    source_locator: str | None
    line_ref: str | None
    source_span_ref_id: str | None

    admitted_supporter_assertion_ids: tuple[str, ...]
```

Exact fields may vary.

Rules:

* all fields are copied from admitted/revalidated authority;
* never synthesize URI/locator/span data;
* preserve false `can_open_source`;
* preserve false `can_highlight_span`;
* do not expose `body_storage`;
* supporter IDs are deterministic/sorted;
* returned backing is immutable.

`admitted_supporter_assertion_ids` are **resolution metadata**.

They are not part of anchor identity.

They are part of the containing evidence result's semantic meaning.

---

# 16. Anchor context binding

Anchor identity must bind the exact knowledge/read authority relevant to the evidence.

Create a deterministic context-binding digest from at least:

```text
space_id
actual ParsedKnowledgeRevision revision_id
canonical sealed ProjectionRequest content
pinned DomainContract identity
  domain_id
  domain_revision
  descriptor_sha256
pinned SemanticProfile identity
  profile_id
  profile_revision
  descriptor_sha256
DomainAdmissionPolicy.policy_id
```

Do not serialize arbitrary policy implementation state.

The current policy contract exposes `policy_id`, not a policy-state digest.

Authorization is therefore still established by **rerunning the actual policy** during anchor resolution.

If correct anchor semantics ever require a durable digest/version of arbitrary domain-policy configuration beyond `policy_id`, stop/rebrief rather than introspecting arbitrary policy objects.

---

# 17. Anchor identity inputs

Compute an anchor identity digest over canonical values equivalent to:

```text
anchor schema/version

context binding digest

evidence_ref_id
source_artifact_id
source_revision_id

evidence_role
can_open_source
can_highlight_span
locator
uri
source_locator
line_ref
source_span_ref_id

returned source artifact authority fields:
  source_artifact_id
  status
  current_revision_id
  source_classification
  authority

returned source revision identity where present:
  source_revision_id
  source_artifact_id
  content_sha256
```

Bind all caller-visible anchor/source meaning.

Do not bind:

```text
admitted_supporter_assertion_ids
timing
work counters
benchmark metadata
V2 exclusion reasons
hidden provenance
```

---

# 18. Why supporter IDs are not anchor identity

Explicit rule:

> Two anchor DTOs that share the same bound context, evidence location, and returned source authority, and differ only in `admitted_supporter_assertion_ids`, have the same anchor identity.

This is intentional.

The anchor identifies:

```text
this evidence location
under this authority context/source state
```

not:

```text
the exact list of assertions that happened to justify it
```

The containing `EvidenceLookupResult.result_digest` **does** bind admitted supporter IDs.

Test the identity rule directly.

Do not create an impossible test where a single immutable `KnowledgeReadContext` spontaneously gains a new structural supporter.

---

# 19. Anchor token format

The resolver must recover the exact evidence target without scanning the evidence corpus.

Use a small versioned opaque-by-contract token.

Preferred shape:

```text
dm-source-anchor-v1.<base64url(canonical payload)>
```

where canonical payload contains at minimum:

```json
{
  "version": 1,
  "evidence_ref_id": "...",
  "identity_digest": "..."
}
```

Exact encoding may differ.

Requirements:

```text
versioned
deterministic
URL-safe where practical
bounded decode
exact evidence_ref_id recoverable
identity digest carried
no server-side anchor registry required
```

The token is **opaque by API contract**, not secret.

A caller can potentially decode or manufacture it.

That is safe because:

```text
token integrity ≠ authorization
```

Resolution always reruns admission.

Do not design security around the token being unforgeable.

Do not add an HMAC/secret infrastructure requirement merely to make the token look like a capability.

---

# 20. Anchor creation

Create an anchor only after evidence has passed V4.2 authority.

Conceptually:

```text
admitted assertion/evidence operation
→ requested EvidenceRef
→ validated source artifact/revision
→ canonical context binding
→ canonical anchor identity digest
→ versioned anchor token
→ immutable SourceAnchor
```

One exact evidence record under the same exact context/source state should generate the same anchor deterministically.

Repeated calls on one pinned context must produce the same anchor.

---

# 21. Operation C — resolve source anchor

Preferred conceptual API:

```python
SourceAnchorService.resolve_source_anchor(
    context: KnowledgeReadContext,
    anchor_id: str,
) -> SourceAnchorResolution
```

Resolution shape:

```text
anchor token
→ bounded parse/version validation
→ recover exact evidence_ref_id
→ exact evidence lookup
→ exact evidence_supporters lookup
→ V2 admission of exact supporters
→ require at least one admitted supporter
→ assemble requested evidence/source support
→ recompute current anchor identity
→ compare to token identity_digest
→ resolved or unavailable
```

No:

```text
all-anchor scan
all-evidence scan
full projection
anchor database
revision-wide authorization cache
```

---

# 22. Anchor resolution is fresh authorization

Anchor resolution must rerun current-context authority.

A valid token is not enough.

If:

```text
evidence exists
token digest is syntactically valid
source IDs match
```

but the current context admits no supporter assertion:

```text
resolved = false
```

The anchor does not grant access.

---

# 23. Public-safe anchor failure

Use the same public unavailable posture for:

```text
malformed token
unknown version
evidence missing
zero admitted supporters
hidden-only supporters
out-of-scope supporters
domain-policy exclusion
source inactive
source revision invalid
context mismatch
domain/profile mismatch
bound visible source metadata changed
bound locator/span/open metadata changed
identity digest mismatch
```

Do not tell an unauthorized caller:

```text
"the evidence exists but is hidden"
"the source went inactive"
"you have the wrong campaign"
"the anchor points to evidence X"
```

beyond information already literally present in their supplied token.

Internal typed diagnostics may exist for engineering observability.

They are not public semantic output.

---

# 24. Same-context coherence

Carry forward V2/V3/V4.1 semantics:

```text
context A created
→ coherent source view A pinned

create evidence result / anchor A

live backing source mutates

repeat read or resolve in context A
→ still sees authority epoch A
→ same semantic result / anchor

create context B over same parsed KnowledgeRevision
→ coherent source view B sees mutation
→ old anchor either:
     resolves if all bound visible authority remains identical
   or
     becomes unavailable
→ newly generated anchor changes when bound state changed
```

Do not cache anchor validity by revision ID alone.

---

# 25. Source DTO reuse

Do not create competing source semantics.

Prefer extracting/reusing the direct-support DTOs already proven by V3/V4.1:

```text
source_artifact_id
status
current_revision_id
source_classification
authority
```

and source revision:

```text
source_revision_id
source_artifact_id
content_sha256
```

Evidence navigation metadata comes from the exact `EvidenceRef`.

Do not expose persistence-only fields merely because they exist.

---

# 26. Result shape — assertion evidence

Illustrative:

```python
@dataclass(frozen=True, slots=True)
class AssertionEvidenceResult:
    identity: EvidenceReadIdentity
    requested_assertion_id: str
    available: bool

    assertion: ParsedAssertion | None

    evidence: tuple[ParsedEvidenceRef, ...]
    source_artifacts: tuple[...]
    source_revisions: tuple[...]
    anchors: tuple[SourceAnchor, ...]

    completeness: ...
    result_digest: str
```

No raw hidden-candidate diagnostics in the exported result.

---

# 27. Result shape — exact evidence

Illustrative:

```python
@dataclass(frozen=True, slots=True)
class EvidenceLookupResult:
    identity: EvidenceReadIdentity
    requested_evidence_ref_id: str
    available: bool

    evidence: ParsedEvidenceRef | None
    admitted_supporter_assertions: tuple[ParsedAssertion, ...]

    source_artifacts: tuple[...]
    source_revisions: tuple[...]
    anchors: tuple[SourceAnchor, ...]

    completeness: ...
    result_digest: str
```

For unavailable:

```text
evidence = None
admitted_supporter_assertions = ()
source_artifacts = ()
source_revisions = ()
anchors = ()
```

No exclusion reason.

---

# 28. Result shape — anchor resolution

Illustrative:

```python
@dataclass(frozen=True, slots=True)
class SourceAnchorResolution:
    identity: EvidenceReadIdentity
    requested_anchor_id: str
    resolved: bool

    anchor: SourceAnchor | None
    evidence: ParsedEvidenceRef | None
    admitted_supporter_assertions: tuple[ParsedAssertion, ...]

    source_artifacts: tuple[...]
    source_revisions: tuple[...]

    completeness: ...
    result_digest: str
```

Exact naming is implementation latitude.

---

# 29. Semantic result digests

Result digests bind caller-visible meaning.

## Assertion evidence digest

Bind at least:

```text
read identity
requested assertion ID
available state
returned assertion ID
returned evidence records and visible navigation fields
returned source artifact fields
returned source revision fields
returned anchor IDs / visible anchor fields
completeness state
```

## Evidence lookup digest

Bind at least:

```text
read identity
requested evidence ID
available state
returned evidence record
admitted supporter assertion IDs
returned source records
returned anchor
completeness state
```

## Anchor resolution digest

Bind at least:

```text
read identity
caller-supplied anchor ID
resolved state
returned current anchor when resolved
returned evidence/supporter IDs
returned source records
completeness state
```

Do not bind:

```text
diagnostic work
timing
excluded supporter IDs
excluded provenance
V2 exclusion reasons
```

Inherited V3 rule:

> Hash returned authority, not hidden authority consulted while deciding it.

---

# 30. Unavailable digest privacy

An unavailable semantic digest must not fingerprint the hidden structural reason.

Do not hash:

```text
number of hidden supporters
their IDs
their exclusion reasons
their sources
internal candidate counts
```

The digest may bind:

```text
read/context identity
caller-supplied target
available/resolved = false
```

because those are already public.

---

# 31. Completeness

V4.2 is complete-or-fail-closed.

For an available assertion/evidence:

```text
return the complete exact support set required by the operation
```

No silent caps.

For an unavailable target:

```text
return public-safe unavailable
```

For structural corruption:

```text
typed integrity failure
```

Do not invent partial-result semantics merely for convenience.

If partial/resource semantics become necessary, stop/rebrief.

---

# 32. Internal characterization diagnostics

Create an internal non-exported diagnostic structure sufficient to prove locality.

Conceptually:

```python
@dataclass(frozen=True, slots=True)
class _EvidenceReadTrace:
    assertion_lookups: int
    evidence_lookups: int

    supporter_candidates: int
    assertions_evaluated: int
    policy_evaluations: int

    evidence_ids_consulted: int

    unique_artifact_ids_requested: int
    unique_revision_ids_requested: int
    provenance_snapshot_calls: int

    anchors_constructed: int
    anchors_revalidated: int
```

Names may differ.

Lessons from V4.1 are binding:

* `artifact_ids_requested` means operation-wide **unique IDs**, not summed per-batch events;
* same for source revision IDs;
* provenance snapshot calls separately record request events;
* do not under-report real inspected candidates.

Tests/benchmarks may inspect this diagnostic path.

Public result DTOs must not expose candidate-dependent details that reveal hidden structure.

---

# 33. Required semantic witnesses

The exact number of tests is not authority.

These obligations are.

## A. Exact assertion evidence

1. admitted exact assertion returns its exact evidence refs;
2. admitted assertion with zero evidence returns valid empty support;
3. missing assertion returns public-safe unavailable;
4. hidden assertion returns the same public semantic shape as missing;
5. out-of-scope assertion exposes no evidence/source metadata;
6. standing-excluded assertion exposes none;
7. domain-policy excluded assertion exposes none;
8. inactive/missing source preserves V2 fail-closed semantics;
9. no alias/search fallback;
10. repeated same-context read is deterministic;
11. evidence ordering is deterministic;
12. anchors are deterministic and one-per-returned-evidence.

## B. Exact evidence lookup

13. one admitted supporter returns target evidence;
14. missing evidence returns unavailable;
15. zero assertion supporters returns unavailable;
16. alias-only evidence returns unavailable without alias scan;
17. alias-only evidence is not called orphan;
18. hidden-only supporters return unavailable;
19. out-of-scope-only supporters return unavailable;
20. domain-policy-only exclusion returns unavailable;
21. mixed visible/hidden support returns only admitted supporter assertions;
22. supporter IDs are deterministic;
23. parallel admitted supporters are complete;
24. exact lookup uses `evidence_supporters[target]`;
25. no all-assertion scan;
26. only requested target evidence is returned;
27. other evidence consulted to admit supporters is not surfaced.

## C. Privacy

28. unavailable result contains no source IDs;
29. unavailable result contains no locator;
30. unavailable result contains no URI;
31. unavailable result contains no span ID;
32. unavailable result contains no exclusion reason;
33. public DTO contains no raw supporter-candidate count;
34. public digest does not fingerprint hidden candidate count;
35. hidden provenance changes do not perturb an unchanged visible result digest.

## D. Source anchors

36. admitted evidence yields deterministic anchor;
37. repeated creation in same context yields same anchor ID;
38. token permits exact target recovery;
39. resolver does not scan all evidence;
40. resolver does not scan all anchors;
41. false open flag remains false;
42. false highlight flag remains false;
43. locator copied exactly;
44. URI copied exactly;
45. line/span copied exactly;
46. absent navigation metadata remains absent;
47. body storage is not exposed.

## E. Anchor identity

48. context binding includes exact parsed revision;
49. request change changes context binding;
50. domain contract identity change changes context binding;
51. semantic profile identity change changes context binding;
52. bound evidence-location change changes anchor identity;
53. returned source-authority change changes anchor identity where bound;
54. source revision content digest change changes identity;
55. two anchors differing only in supporter metadata have equal anchor identity;
56. containing evidence result digest still changes when returned supporter set changes.

Do not implement test #56 by mutating one pinned immutable context into another state. Use separate fixtures/identity inputs.

## F. Anchor revalidation

57. valid same-context anchor resolves;
58. malformed token fails safely;
59. unknown token version fails safely;
60. token with unknown evidence target fails safely;
61. zero admitted current supporters fails safely;
62. current request excluding supporters fails safely;
63. current domain policy excluding supporters fails safely;
64. changed bound visible source state invalidates old anchor;
65. changed locator/open/span state invalidates old anchor;
66. anchor never bypasses V2;
67. manufactured anchor for an inaccessible evidence ID remains unavailable.

## G. Coherence

68. context A remains coherent after live source mutation;
69. repeated anchor resolution in A does not tear;
70. new context B observes changed source authority;
71. no revision-only authorization cache;
72. no global mutable anchor cache.

## H. Structural locality

73. exact assertion support does not scan all evidence;
74. exact evidence lookup does not scan all assertions;
75. unrelated graph growth 1k→10k leaves fixed-target candidate work unchanged;
76. unrelated evidence growth leaves fixed-target work unchanged;
77. unrelated source growth leaves requested source IDs unchanged;
78. anchor revalidation work equals exact-target supporter work, not space size;
79. high-support evidence work scales honestly with actual supporter count;
80. no full-space projection.

## I. Genericity

81. organizational-memory fixture works through same engine;
82. Buddy-shaped fixture works using opaque generic scope/visibility labels;
83. no `GM`;
84. no `PLAYER`;
85. no `campaign_id`;
86. no NPC semantics;
87. no D&D semantics;
88. no fictional-time dependency in generic V4.2 implementation;
89. no dynamic domain-policy loading;
90. frozen V0 aggregate remains exact.

## J. Regression / scope

91. V1 normalized/index tests green;
92. V1 legacy compatibility tests green;
93. V2 candidate-admission tests green;
94. V3 entity-read tests green;
95. V4.1 neighborhood tests green;
96. current World public retrieval unchanged;
97. no publication/write changes;
98. no storage migration;
99. no V4.3 search API exported;
100. no source-body fetch implementation.

---

# 34. Benchmark

Create:

```text
benchmarks/vnext_evidence_support_10k.py
Docs/Benchmarks/vnext_evidence_support_10k_v1.json
```

Use native vNext fixtures.

The 10k lane should contain at least 10,000 assertions and thousands of entities/evidence records—not a nominally named tiny fixture.

---

# 35. Benchmark lane 1 — exact assertion support

Fixed local assertion/evidence/source chain.

Compare:

```text
1k unrelated corpus
10k unrelated corpus
```

Require unchanged:

```text
target assertion lookup count
assertions evaluated
exact evidence IDs discovered
unique artifact IDs requested
unique revision IDs requested
provenance snapshot calls
returned evidence count
```

Record p50/p95.

Directional 10k exact evidence target:

```text
p95 < 25 ms
```

This is a directional architecture target, not permission to weaken semantics.

---

# 36. Benchmark lane 2 — exact evidence, low support

One target evidence record with a small fixed supporter set.

Compare 1k vs 10k unrelated corpus.

Require unchanged:

```text
target evidence lookups
supporter candidate count
supporters evaluated
unique artifact IDs requested
unique revision IDs requested
returned admitted supporter count
```

The target must be identical in local shape across sizes.

---

# 37. Benchmark lane 3 — unrelated evidence/source growth

Add thousands of unrelated:

```text
EvidenceRefs
supporter assertions
source artifacts
source revisions
```

Exact target lookup must remain:

```text
evidence_by_id[target]
evidence_supporters[target]
```

No corpus scan.

---

# 38. Benchmark lane 4 — high-support honest cost

One evidence record with a meaningful real supporter set.

For example:

```text
4 supporters
64 supporters
256 supporters
```

Show work grows with actual support degree.

Do not call that a locality failure.

Record:

```text
supporter candidates
assertions evaluated
source IDs requested
p50/p95
returned admitted supporters
```

---

# 39. Benchmark lane 5 — anchor revalidation

Create one valid target anchor and repeatedly resolve it.

Compare same local support shape under 1k vs 10k unrelated space.

Require unchanged structural work.

Resolution must recover exact evidence ID directly from token.

No global anchor scan.

---

# 40. Benchmark lane 6 — privacy/admission characterization

Include at least:

```text
visible supporter
hidden-only supporter set
mixed visible/hidden supporter set
```

Characterization trace may record real work internally.

Public semantic result must not expose hidden candidate counts.

Verify hidden-only public result remains unavailable with no evidence/source/anchor detail.

---

# 41. Benchmark artifact

Record at least:

```text
schema_version
exact_base
exact substantive head

workload identities
workload digests
parsed semantic digests

target assertion/evidence IDs

semantic result digests
anchor IDs

returned cardinalities

internal structural diagnostics:
  lookups
  supporter candidates
  assertions evaluated
  policy evaluations
  unique artifact IDs requested
  unique revision IDs requested
  provenance snapshot calls

p50
p95

structural gate
directional target result
```

If the artifact commit comes after substantive implementation, pin:

```text
exact_head = substantive implementation head
```

not the artifact's self-referential commit.

---

# 42. Structural benchmark gate

The artifact's structural gate must require at least:

```text
fixed assertion-support work:
  1k == 10k

fixed evidence-support work:
  1k == 10k

unrelated evidence growth:
  no candidate growth

unrelated source growth:
  no requested-source growth

anchor revalidation:
  exact supporter-set work only

high-support:
  work == actual supporter shape
```

Do not define PASS only as “fast enough.”

---

# 43. Suggested production modules

Prefer a narrow surface:

```text
src/dungeonmind/application/vnext/
  evidence_reads.py
  source_anchors.py
  errors.py
  __init__.py
```

Tests:

```text
tests/unit/test_vnext_evidence_reads.py
tests/unit/test_vnext_source_anchors.py
```

Benchmark:

```text
benchmarks/vnext_evidence_support_10k.py
Docs/Benchmarks/vnext_evidence_support_10k_v1.json
```

A single `evidence_reads.py` containing anchor logic is acceptable if that is genuinely clearer.

---

# 44. Bounded refactoring allowed

Small refactoring is allowed in:

```text
entity_reads.py
neighborhood.py
read_context.py
provenance.py
admission.py
```

only to extract/reuse generic helpers already semantically proven.

Good refactor examples:

```text
shared source DTO construction
shared exact evidence→source support assembly
shared context-binding helper
shared visible-source semantic serialization
```

Do not alter V2 admission ordering or broaden policy behavior.

Do not duplicate subtle source/digest logic three times if one small internal helper prevents divergence.

---

# 45. Expected zero changes

Expected zero frozen-contract changes:

```text
src/dungeonmind/contracts/vnext/*
```

Expected zero changes to:

```text
World public retrieval semantics
legacy v1-v6 compatibility behavior
publication repositories
governed writes
PostgreSQL schema/migrations
DungeonBuddy
```

If those become necessary, stop.

---

# 46. Explicitly out of scope

Do not implement:

```text
V4.3 deterministic search
lexical search
alias search
ranked search
FTS
BM25
vector retrieval
semantic retrieval

anchor search
list-all evidence
list-all sources

alias-backed evidence authorization
runtime alias-only/orphan classification
evidence_alias_supporters

source body fetching
PDF opening
text-body retrieval
body_storage public API

mutable head resolution
KnowledgeSpace durable runtime

native vNext writes
publication
V5 work

PostgreSQL vNext migration

bridge genesis
World cutover
Buddy repin
Buddy domain runtime implementation

Redis
distributed cache
graph database
```

---

# 47. Stop / rebrief conditions

Stop if any of these become true:

1. exact assertion evidence requires full projection;
2. exact evidence lookup requires scanning all assertions;
3. anchor resolution requires scanning all EvidenceRefs;
4. anchor resolution requires a durable anchor registry;
5. evidence must be returned despite zero admitted assertion supporters for a required workflow;
6. alias-only evidence must become publicly readable in V4.2;
7. correct alias authority requires a new reverse index;
8. frozen V0 contract change appears necessary;
9. source-body access is required for anchor correctness;
10. anchors must act as authorization independent of V2;
11. source freshness cannot remain coherent through the pinned read context;
12. correct context identity requires serializing opaque arbitrary policy state;
13. V4.3 search is needed to make exact support work;
14. Buddy/TTRPG semantics must enter generic code;
15. World public retrieval must change;
16. a revision-only authorization cache is required;
17. V2/V3/V4.1 fail-closed behavior must be weakened.

Stop report:

```text
Stop condition:
Observed evidence:
Which assumption failed:
Affected authority document:
Why V4.2 cannot compensate locally:
Proposed bounded decision/experiment:
What remains safe:
```

Do not redesign architecture silently.

---

# 48. CI posture

Run normal CI.

Any new failure in:

```text
lint
typing
core
V1
V2
V3
V4.1
integration
```

is blocking.

There is existing inherited benchmark-smoke debt in the old World benchmark:

```text
WorldGraphProjectionService.__init__()
missing reviewed_world_initializations
```

Do not fix unrelated World baseline debt inside V4.2.

If it remains the identical inherited failure, document and waive it exactly as prior accepted phases have.

---

# 49. Implementation PR

Open exactly one implementation PR.

Suggested title:

```text
KERNEL: V4.2 evidence reads + source anchors
```

Its first commit is the bookkeeping/handoff commit described above.

Then implementation commits.

Do not open another PR solely for this handoff.

---

# 50. PR body requirements

The V4.2 implementation PR body should contain:

```text
Primary question

Exact base:
  7f5df9eace6f1ab23a0d817e0b350c379923641f

Frozen V0 aggregate:
  fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea

Accepted predecessor:
  PR #66
  accepted head 9b0fd143552ea5e4def3f4a7c8d08050b206eb52
  substantive repair head 626a5fcd2bea3395c62d62aa091b7c666b2ab26f
  review cycles 3
  final review 5230663567
  disposition V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
  merge 7f5df9eace6f1ab23a0d817e0b350c379923641f

Exact substantive V4.2 head

Assertion → evidence authority shape

Evidence → supporter authority shape

Assertion-backed-only decision

Alias-only behavior

Public privacy behavior

Public diagnostics/privacy separation

Anchor token format

Anchor identity inputs

Explicit fact that supporter IDs are not anchor identity

Anchor revalidation shape

Same-context coherence / new-context freshness

Semantic witnesses

Structural locality witnesses

Benchmark artifact
Benchmark substantive head

10k exact evidence characterization

Actual tests / CI

Known inherited failure

What remains false

Successor:
  V4.3 deterministic indexed search
```

Do not claim acceptance.

---

# 51. Steward review gate

Steward must verify all of the following.

## Bookkeeping

* branch base is exact V4.1 merge `7f5df9...`;
* first commit is bookkeeping/handoff, not runtime;
* V4.1 is durably COMPLETE;
* V4.2 is durably ACTIVE / NOT ACCEPTED;
* V4.3 remains blocked;
* no standalone handoff PR.

## Authority

* assertion evidence requires assertion admission first;
* evidence availability requires at least one admitted assertion supporter;
* alias-only evidence is not authorized;
* aliases are not scanned;
* no evidence reverse index beyond accepted `evidence_supporters`;
* anchors do not grant authority.

## Privacy

* missing versus excluded does not leak source/evidence detail;
* hidden-only evidence returns unavailable;
* mixed supporter result returns admitted supporters only;
* raw candidate counts are not exposed through public semantic DTOs;
* hidden provenance is absent from result digests.

## Locality

* assertion→evidence uses `assertion_evidence`;
* evidence→supporters uses `evidence_supporters`;
* anchor token recovers exact evidence target;
* no full projection;
* no whole-assertion scan;
* no whole-evidence scan;
* unrelated 1k→10k growth leaves fixed-target work unchanged.

## Anchors

* deterministic;
* versioned;
* exact-target recoverable;
* context/source bound;
* supporter IDs excluded from identity;
* evidence result digest still binds supporter IDs;
* revalidation reruns current admission;
* same context stays coherent;
* new context sees changed authority.

## Regression

* V0 unchanged;
* V1 green;
* V2 green;
* V3 green;
* V4.1 green;
* World runtime unchanged;
* no V4.3/V5 creep.

Only successful disposition:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```

---

# 52. What success looks like

The final V4.2 architecture should read plainly as:

```text
EXACT ASSERTION SUPPORT

exact immutable revision
→ exact assertion ID
→ V2 admission
→ assertion_evidence
→ exact evidence/source support
→ deterministic anchors
→ immutable semantic result
```

```text
EXACT EVIDENCE SUPPORT

exact immutable revision
→ exact evidence ID
→ evidence_supporters
→ V2 admission of exact supporters
→ require >=1 admitted supporter
→ target evidence/source support only
→ deterministic anchor
→ immutable semantic result
```

```text
ANCHOR REVALIDATION

versioned anchor
→ recover exact evidence ID
→ evidence_supporters
→ V2 admission
→ exact source authority
→ recompute context/source identity
→ compare
→ resolved or unavailable
```

And the negative guarantees should be equally obvious:

```text
no full projection
no corpus supporter scan
no alias scan
no hidden-source leak
no anchor authorization bypass
no source-body fetch
no V4.3 search
no contract drift
no storage migration
```

---

# 53. After V4.2 acceptance

Once Steward records:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```

and the implementation PR merges, the **V4.3 implementation PR's first commit** will record:

```text
actual V4.2 merge SHA
accepted V4.2 head
substantive benchmark head
review-cycle count
final PASS review ID
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
Docs/Benchmarks/vnext_evidence_support_10k_v1.json

V4.2 COMPLETE
V4.3 ACTIVE
V5 BLOCKED ON V4.3 ACCEPTANCE
```

There is no standalone V4.3 handoff PR.

Do not begin V4.3 in this PR.

---

# 54. Final implementation instruction

Implement the smallest generic Kernel surface that proves:

> Exact evidence/support can be addressed directly, authorized only through admitted assertions, converted into deterministic revalidatable source anchors, and served with work proportional to the requested support set.

Do not solve anything larger than that.

When implementation, focused tests, characterization artifact, PR metadata, and CI evidence are ready, stop and hand the exact PR head to Steward review.

Do not merge until the exact-head disposition is:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```
