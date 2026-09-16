# HANDOFF — V4.2 evidence + source-anchor support

**Created:** 2026-09-16  
**Status:** DESIGN-DRAFT / BLOCKED — safe to refine, not authorized to merge or activate until V4.1 implementation is accepted and merged  
**Repository / design branch:** `Drakosfire/DungeonMind` / `handoff/v4-2-evidence-source-anchors`  
**Design base:** `82a5c3e6889ad4e5648fef8f358423b5a576cb9b` — merged PR #64, V4.1 handoff/bookkeeping control surface  
**Predecessor required before activation:** V4.1 bounded neighborhood implementation — not yet accepted or merged at creation time  
**Predecessor accepted head:** `PENDING_V4_1_ACCEPTANCE`  
**Predecessor final Steward review:** `PENDING_V4_1_ACCEPTANCE`  
**Predecessor logical review cycles:** `PENDING_V4_1_ACCEPTANCE`  
**Predecessor disposition required:** `V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED`  
**Predecessor merge:** `PENDING_V4_1_MERGE`  
**Predecessor benchmark:** `Docs/Benchmarks/vnext_neighborhood_10k_v1.json` — pending V4.1 acceptance  
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**Roadmap phase after activation:** V4.2 — evidence + source-anchor support  
**Successor:** V4.3 — deterministic indexed search  
**One-line mission:** Resolve exact assertion/evidence support and context-bound source anchors through revision-local support indexes plus the accepted V2 admission/provenance seam, without whole-space supporter rediscovery and without allowing an anchor to become an authorization bypass.

---

## §0 This is a design draft, not an active roadmap transition

At creation time:

```text
PR #64 handoff/bookkeeping      MERGED
V4.1 implementation             NOT YET ACCEPTED
V4.2                            BLOCKED
```

The Steward explicitly permits design work for V4.2 while V4.1 is active, but V4.2 must not merge early.

Therefore this file intentionally contains placeholders for the eventual V4.1 implementation facts.

### Activation gate

Before this handoff may become mergeable/active:

1. V4.1 implementation receives exact Steward disposition:

```text
V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
```

2. V4.1 implementation merges to `main`.
3. Re-anchor this branch on that exact merge.
4. Replace every `PENDING_V4_1_*` placeholder with checked-in facts.
5. Update `HANDOFF-STEWARDSHIP-vnext-roadmap.md` with:

```text
actual V4.1 merge SHA
accepted V4.1 head
logical review-cycle count
final PASS review ID
V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
Docs/Benchmarks/vnext_neighborhood_10k_v1.json
benchmark substantive head / structural gate
V4.1 COMPLETE
V4.2 ACTIVE
V4.3 BLOCKED ON V4.2 ACCEPTANCE
V5 BLOCKED ON V4.3 ACCEPTANCE
```

6. Change this file's status from `DESIGN-DRAFT / BLOCKED` to `ACTIVE`.
7. Only then may the V4.2 implementation branch be created.

If V4.1 acceptance changes any assumption this handoff relies on, revise this design before activation rather than preserving stale prose.

---

## §1 Primary question

> **Can exact assertion/evidence support and context-bound source anchors be retrieved and revalidated through revision-local `assertion_evidence` / `evidence_supporters` indexes plus candidate-local V2 admission/provenance, with work proportional to the requested support set rather than the whole KnowledgeSpace?**

Only successful V4.2 implementation disposition:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```

Until that disposition is recorded and V4.2 merges, V4.3 remains blocked from merge.

---

## §2 Why V4.2 exists separately

V3 already proved that an entity read can return the direct evidence/source records required by its admitted assertions.

V4.1 is proving that bounded traversal can return the direct support required by admitted traversal edges.

Neither slice establishes a **standalone exact support API** or a **revalidatable source-anchor capability**.

V4.2 answers that missing question without absorbing search.

```text
V4.1
  bounded admitted graph traversal

V4.2
  exact assertion → evidence
  exact evidence → admitted supporters
  admitted evidence → source anchor
  source anchor → exact revalidation

V4.3
  deterministic indexed candidate search
```

Do not use V4.2 to pre-build V4.3 search/ranking.

---

## §3 Authority and required reading

Read in this order before implementation.

### 3.1 Binding architecture / roadmap

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
6. this handoff after activation

### 3.2 Frozen source/evidence contract

Read:

```text
src/dungeonmind/contracts/vnext/source.py
src/dungeonmind/contracts/vnext/knowledge.py
src/dungeonmind/contracts/vnext/common.py
```

Binding frozen source/evidence records include:

```text
SourceArtifactV3
  source_artifact_id
  source_classification
  current_revision_id
  authority
  visibility
  status
  uri
  foreign_refs
  domain_metadata
  created_at / updated_at

SourceRevisionV2
  source_revision_id
  source_artifact_id
  content_sha256
  body_storage
  locator
  created_at

EvidenceRefV3
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
  domain_metadata
```

Do not add a V0 contract field merely to make anchor implementation convenient.

### 3.3 Accepted immutable support indexes

Read:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/records.py
```

The relevant V1 substrate already exists:

```text
assertions_by_id
assertion_evidence

evidence_by_id
evidence_supporters
```

Meaning:

```text
assertion_evidence[assertion_id]
  → exact evidence_ref IDs named by that assertion

evidence_supporters[evidence_ref_id]
  → exact assertion IDs that cite that evidence ref
```

These are revision-local derived indexes. They discover structural candidates only. They do not establish caller authority.

### 3.4 Accepted V2 authority seam

Read:

```text
src/dungeonmind/application/vnext/read_context.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/provenance.py
src/dungeonmind/application/vnext/ports.py
```

Reuse exactly:

- one pinned `KnowledgeReadContext`;
- exact request/domain/profile identity;
- generic standing/scope/visibility checks;
- candidate-local evidence/source dependency collection;
- coherent source-authority epoch;
- source visibility before detailed lifecycle diagnostics;
- pure domain policy that can narrow only;
- new context sees changed live source authority;
- same context remains coherent after live mutation.

V4.2 must not invent a separate evidence authorization engine.

### 3.5 Accepted V3/V4.1 lessons

Read V3 entity reads and, once accepted, V4.1 neighborhood implementation/tests.

Carry forward:

```text
visible result digest binds returned authority only
hidden/excluded candidate provenance does not perturb visible digest
source support is candidate-local
no ordinary result cap may masquerade as complete truth
work counters expose actual inspected candidates
```

### 3.6 Historical World anchor implementation

Read current World retrieval/anchor code for behavioral lessons only.

Do not import:

```text
WorldGraphProjectionRequestV2
ProjectionSnapshotV2
campaign / GM / PLAYER enums
World-specific object/relationship DTOs
current full-projection dependency
```

into generic vNext.

---

## §4 Write lease

Expected production surface:

```text
src/dungeonmind/application/vnext/
  evidence_reads.py          # illustrative name
  source_anchors.py          # may be one module with evidence_reads if cleaner
  __init__.py
  errors.py                  # bounded support/anchor integrity errors only
```

Bounded internal refactor allowed in:

```text
entity_reads.py
read_context.py
provenance.py
```

only to extract generic direct-support helpers already proven in V3/V4.1.

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

Expected zero changes to:

```text
src/dungeonmind/contracts/vnext/*
current World public retrieval
legacy v1-v6 readers
legacy compatibility semantics
publication/write repositories
PostgreSQL schema/migrations
DungeonBuddy
```

Frozen V0 contract change → stop/rebrief.

---

## §5 Fundamental authority rule: evidence is not independently public

Evidence/source records justify admitted knowledge. They must not become a side door around assertion admission.

V4.2 therefore adopts this rule:

> **An EvidenceRef is returnable through the generic evidence-read surface only when the current pinned context can establish at least one admitted supporter assertion for that EvidenceRef.**

Consequences:

```text
exact evidence ID exists structurally
+ all supporters hidden/excluded
→ evidence unavailable
→ no source IDs
→ no locator
→ no URI
→ no span metadata
→ no anchor

exact evidence ID exists structurally
+ at least one supporter admitted
→ evidence may be returned
→ only admitted supporter assertions are returned
→ source/provenance is validated through V2
→ anchors may be derived
```

Do not infer a new evidence-level scope/visibility model from source/evidence metadata.

The authority path remains assertion-first.

---

## §6 Exact assertion evidence read

Preferred conceptual operation:

```python
get_assertion_evidence(
    context,
    assertion_id: str,
) -> AssertionEvidenceResult
```

Exact naming is implementation latitude; semantics are binding.

### 6.1 Candidate discovery

```text
caller exact assertion ID
→ exact assertions_by_id lookup
→ if structurally present, evaluate that one assertion through V2
```

No alias/search/fallback.

### 6.2 Privacy posture

An assertion itself carries scope/visibility/standing and can be hidden.

Therefore the standalone support API must not distinguish:

```text
assertion does not exist
assertion exists but is not admitted
```

through public result detail.

Preferred public-safe shape:

```text
found = false
```

for both.

The caller-supplied ID may be echoed because the caller supplied it. Do not echo hidden predicate, subject, source IDs, rejection reason, or source lifecycle details.

### 6.3 Admitted assertion result

If admitted:

```text
assertion
→ assertion_evidence[assertion_id]
→ exact ParsedEvidenceRef records
→ exact targeted provenance from the same V2 evaluation/context
→ source artifact/revision DTOs
→ derived anchors
```

Do not perform a second authority decision over a different source epoch.

### 6.4 No evidence means valid empty support

An admitted assertion may legitimately cite zero evidence refs if allowed by its domain/standing semantics.

Return an admitted assertion with an empty evidence/anchor collection rather than inventing a missing-support error unless accepted V2/domain policy already rejects it.

---

## §7 Exact evidence read

Preferred conceptual operation:

```python
get_evidence(
    context,
    evidence_ref_id: str,
) -> EvidenceLookupResult
```

### 7.1 Candidate discovery

```text
caller exact evidence_ref_id
→ exact evidence_by_id lookup
→ evidence_supporters[evidence_ref_id]
→ supporter assertion IDs only
→ V2 evaluate those supporter assertions
```

This is the central V4.2 architecture witness.

Do not rediscover supporters by scanning:

```text
all assertions
all assertion metadata
a full admitted projection
all entity reads
```

### 7.2 Evidence availability

Evidence is available only if at least one supporter is admitted.

Preferred public-safe behavior:

```text
missing evidence ID                 → found=false
existing evidence, zero supporters  → found=false
existing evidence, all hidden       → found=false
existing evidence, supporters rejected by source/domain/scope → found=false
one or more admitted supporters     → found=true
```

Do not expose which unavailable case occurred through detailed public diagnostics.

### 7.3 Mixed supporter visibility

If one evidence record has:

```text
supporter A  admitted
supporter B  hidden
supporter C  out of scope
```

return:

```text
evidence record
supporter A only
validated source/provenance
anchors
```

Do not return B/C IDs merely because they structurally support the same evidence.

### 7.4 High-support evidence

An evidence record may have many real supporter assertions.

V4.2 may perform work proportional to that exact supporter set.

The claim is:

```text
O(exact supporters + their support dependencies)
```

not constant time regardless of returned truth.

Work accounting must expose high supporter counts honestly.

---

## §8 Source-anchor semantics

A source anchor is a **derived, context-bound reference to already-admitted evidence**.

It is not:

```text
a new authority record
a durable database row
a permission grant
a shortcut around V2 admission
a source-body cache
a globally searchable locator
```

### 8.1 Minimum anchor meaning

An anchor should identify enough admitted state to let a client later ask:

> Does this same evidence location remain valid and admissible under this exact read context?

Illustrative immutable DTO:

```python
@dataclass(frozen=True, slots=True)
class SourceAnchor:
    anchor_id: str
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None
    can_open_source: bool
    can_highlight_span: bool
    locator: str | None
    uri: str | None
    source_locator: str | None
    line_ref: str | None
    source_span_ref_id: str | None
    admitted_supporter_assertion_ids: tuple[str, ...]
```

Exact fields may be narrower if the client does not need all of them.

Do not expose `SourceRevisionV2.body_storage` merely because it exists in the frozen authority record. Opening/fetching body content is outside V4.2.

### 8.2 Anchor identity must be context-bound

The anchor identity must bind enough state that it cannot be replayed as if it were valid in a different authority context.

At minimum bind canonical values equivalent to:

```text
anchor schema/version
space_id
knowledge revision_id
exact request/admission-context identity
pinned DomainContract identity
pinned SemanticProfile identity

evidence_ref_id
source_artifact_id
source_revision_id

evidence locator/open fields returned to caller
source_span_ref_id

returned source artifact authority fields relevant to visible meaning
returned source revision content identity relevant to visible meaning
```

The exact request/admission-context binding may be represented as one deterministic digest of the sealed request + pinned descriptors.

Do not bind timing or work counters.

### 8.3 Anchor token must support exact revalidation

A later resolver must be able to recover the exact structural evidence target from the anchor token without scanning the evidence corpus.

Acceptable shapes include:

```text
versioned self-describing token carrying an encoded evidence_ref_id + integrity digest

or

another deterministic opaque format from which Kernel code can recover the exact evidence_ref_id directly
```

The token is opaque to clients even if Kernel code can decode its versioned payload.

Not acceptable:

```text
anchor_id = sha256(all fields)
then resolve by scanning every EvidenceRef until one hashes to anchor_id
```

If exact target recovery cannot be achieved without a new durable reverse index or contract change, stop/rebrief instead of hiding a scan.

### 8.4 Anchor integrity is not authorization

A caller may manufacture or mutate an anchor token.

Token parse/hash integrity may reject malformed/tampered tokens, but authorization still requires fresh revalidation through the pinned context.

Do not rely on obscurity or a token digest as an access-control boundary.

---

## §9 Anchor creation

Anchors may be created only from evidence that is already available through the current V4.2 evidence authority path.

Conceptually:

```text
admitted assertion/evidence read
→ exact validated EvidenceRef
→ exact validated source artifact/revision
→ deterministic SourceAnchor
```

One EvidenceRef should normally produce one deterministic anchor per exact context and returned source state.

If an EvidenceRef lacks usable locator/open/span metadata, it may still produce a provenance anchor if useful, but:

```text
can_open_source = false
can_highlight_span = false
```

must remain honest.

Do not manufacture a URI or source span.

---

## §10 Anchor revalidation

Preferred conceptual operation:

```python
resolve_source_anchor(
    context,
    anchor_id: str,
) -> SourceAnchorResolution
```

Exact naming is implementation latitude.

### 10.1 Bounded resolution shape

```text
anchor token
→ parse/verify version + recover exact evidence_ref_id
→ evidence_by_id exact lookup
→ evidence_supporters exact supporter IDs
→ V2 candidate admission on those supporters
→ require at least one admitted supporter
→ exact evidence/source provenance
→ recompute canonical current-context anchor
→ compare anchor identity
→ resolved or unavailable
```

No full-space projection and no global anchor scan.

### 10.2 Public-safe failure

For an anchor supplied by the caller, preferred public behavior is one unavailable result for:

```text
malformed/unknown anchor version
evidence removed/missing
all supporters now hidden/excluded
source now inactive/retracted
source revision mismatch
context/request mismatch
domain/profile mismatch
locator/source authority changed such that anchor identity no longer matches
```

Internal typed diagnostics may exist for integrity/observability, but public output must not reveal hidden source/assertion identity that the current context cannot admit.

### 10.3 Same-context coherence / new-context freshness

Required witness:

```text
context A created
→ evidence admitted
→ anchor A created

live source authority mutates

resolve anchor A in context A
→ remains coherent with context A's pinned authority epoch

context B created over same ParsedKnowledgeRevision
→ observes new source authority
→ old anchor A either becomes unavailable or resolves only if all bound visible authority remains exactly valid
→ if still admissible but bound visible source state changed, newly generated anchor identity changes
```

Do not cache anchor validity by knowledge revision alone.

---

## §11 Returned source metadata

V4.2 may reuse/extract the source DTOs established by V3 rather than defining competing semantics.

Minimum returned source artifact meaning commonly needed:

```text
source_artifact_id
status
current_revision_id
source_classification
authority
```

Minimum source revision meaning:

```text
source_revision_id
source_artifact_id
content_sha256
```

Anchor/open metadata may additionally expose only the already-admitted locator/URI fields required for client navigation.

Do not expose fields merely because they are present in persistence.

If a caller-visible returned field changes, semantic result/anchor digests must change accordingly.

---

## §12 Result digests

Standalone evidence/support result digests must bind caller-visible semantic meaning.

For assertion evidence reads, bind at minimum:

```text
exact read identity
caller assertion ID
found/admitted state
returned assertion ID
returned evidence records + locator fields
returned source artifact fields
returned source revision fields
returned anchors
completeness state
```

For evidence reads, bind at minimum:

```text
exact read identity
caller evidence ID
found state
returned evidence record
admitted supporter assertion IDs
returned source records
returned anchors
completeness state
```

Rules inherited from V3:

```text
visible returned authority changes → digest changes
hidden/excluded supporter/source detail changes → visible digest does not change
work counters/timing → never part of semantic digest
```

An anchor's own identity digest is separate from the containing result digest.

---

## §13 Completeness

Preferred first implementation is complete-or-fail-closed for exact support retrieval.

```text
valid exact target + intact authority → complete support result
unavailable/unauthorized target       → public-safe not found/unavailable
structural integrity failure          → typed fail-closed error
```

Do not silently cap:

```text
supporter assertions
evidence refs
source artifacts
source revisions
anchors
```

and still label the result complete.

If resource partiality is introduced, use a closed reason vocabulary and explicit truncation fields.

---

## §14 Work accounting

At minimum record/expose:

### Assertion evidence read

```text
assertion lookups
assertions evaluated
policy evaluations
evidence IDs discovered
artifact IDs requested
revision IDs requested
provenance snapshot calls
anchors produced
```

### Evidence read / anchor revalidation

```text
evidence lookups
supporter assertion candidates
supporter assertions evaluated
policy evaluations
artifact IDs requested
revision IDs requested
provenance snapshot calls
anchors produced/revalidated
```

If anchor token parsing performs anything beyond bounded decode/hash work, account for it.

Do not report only returned supporters while hiding a larger supporter scan.

---

## §15 Required semantic witnesses

The implementation must include focused proof for at least the following.

### A. Exact assertion evidence

1. admitted exact assertion returns its exact evidence refs;
2. admitted assertion with zero evidence returns valid empty support;
3. missing assertion ID returns public-safe unavailable;
4. hidden assertion and missing assertion are not distinguishable through source/evidence detail;
5. out-of-scope assertion exposes no evidence/source locator;
6. domain-policy excluded assertion exposes no evidence/source locator;
7. inactive/missing source behavior remains V2 fail-closed;
8. no search/alias fallback for assertion IDs.

### B. Exact evidence lookup

9. exact evidence with one admitted supporter returns evidence + supporter;
10. missing evidence returns unavailable;
11. orphan evidence with zero supporters returns unavailable;
12. evidence with hidden-only supporters returns unavailable;
13. hidden-only evidence leaks no source artifact/revision/locator/span IDs;
14. mixed admitted + hidden supporters returns only admitted supporters;
15. out-of-scope supporter is omitted;
16. domain-policy excluded supporter is omitted;
17. evidence supporter direction uses `evidence_supporters`, not all-assertion scan;
18. parallel admitted supporters are deterministic and complete.

### C. Source-anchor creation

19. admitted evidence yields deterministic anchor under same exact context;
20. same-context repeated creation yields same anchor ID;
21. anchor contains/recovers exact evidence target without global scan;
22. locator/span/open fields are copied exactly, never invented;
23. `can_open_source=false` remains false;
24. `can_highlight_span=false` remains false;
25. body storage is not exposed by public anchor DTO;
26. hidden evidence cannot produce anchor.

### D. Anchor revalidation

27. exact valid anchor resolves under same context;
28. malformed anchor fails safely;
29. unknown anchor version fails safely;
30. context/request mismatch fails safely;
31. domain/profile mismatch fails safely;
32. source becomes inactive → new context rejects old anchor;
33. source revision/content identity mismatch invalidates bound anchor;
34. locator/source visible metadata change invalidates old bound anchor when part of returned meaning;
35. hidden supporters do not become visible during failed resolution;
36. resolver does not scan all evidence/anchors.

### E. Coherence/freshness

37. context A remains coherent after live source mutation;
38. context B sees changed source authority;
39. no revision-only evidence/anchor authorization cache;
40. multiple reads on same context do not tear across source epochs.

### F. Structural locality

41. assertion evidence read does not scan all evidence;
42. evidence read does not scan all assertions;
43. evidence supporter candidate count is unchanged under unrelated 1k→10k graph growth;
44. unrelated evidence growth does not change exact-target candidate work;
45. unrelated source growth does not change requested source IDs;
46. high-support evidence cost grows with its actual supporter count and is reported honestly;
47. anchor revalidation candidate work matches exact evidence supporter set;
48. no full-space projection.

### G. Digests / privacy

49. returned source authority metadata change perturbs visible result digest;
50. hidden supporter provenance change does not perturb visible result digest;
51. hidden-only evidence detail cannot be inferred from digest shape beyond unavailable state;
52. work/timing changes do not perturb semantic digest;
53. anchor identity changes when bound visible authority/context identity changes;
54. seed/request input ordering where applicable is deterministic.

### H. Genericity

55. organizational-memory fixture uses same engine;
56. Buddy-shaped fixture uses opaque generic scope/visibility labels only;
57. no GM/PLAYER/campaign/NPC/D&D/fictional-time dependency in generic V4.2 code;
58. no dynamic domain-policy loading;
59. frozen V0 aggregate remains exact.

### I. Regression/scope

60. V1 support-index tests green;
61. V2 candidate-admission tests green;
62. V3 entity-read tests green;
63. accepted V4.1 neighborhood tests green;
64. current World public retrieval unchanged;
65. no write/publication changes;
66. no durable storage migration;
67. no V4.3 search API exported;
68. no source-body fetch/open implementation added.

The exact test count is not authority. These obligations are.

---

## §16 Benchmark / characterization

Create:

```text
benchmarks/vnext_evidence_support_10k.py
Docs/Benchmarks/vnext_evidence_support_10k_v1.json
```

### 16.1 Exact assertion support: fixed target, 1k vs 10k unrelated space

Same assertion/evidence/source chain; increase unrelated graph/evidence/source records dramatically.

Require unchanged:

```text
assertions evaluated
evidence IDs discovered
artifact IDs requested
revision IDs requested
provenance snapshot calls
```

### 16.2 Exact evidence support: fixed low-support evidence, 1k vs 10k unrelated space

Require unchanged:

```text
supporter candidate IDs
supporters evaluated
requested source IDs
returned supporter count
```

### 16.3 Unrelated-evidence growth witness

Add thousands of unrelated EvidenceRefs and supporter assertions.

Exact target lookup must remain on `evidence_by_id` + `evidence_supporters[target]`.

### 16.4 High-support honest-cost witness

One evidence ref has many real supporting assertions.

Show work grows with exact supporter count.

Do not treat that as a failure.

### 16.5 Anchor revalidation witness

Repeated anchor resolution should show bounded work equivalent to exact target + its supporter set, not whole-space anchor/evidence work.

### Artifact fields

Record at minimum:

```text
schema version
exact base SHA
exact substantive head SHA
workload digests
parsed semantic digest(s)
target assertion/evidence IDs
returned semantic result digests
anchor IDs for stable-context witness
candidate/evaluation/source counts
p50/p95 where meaningful
structural gate verdict
```

If artifact refresh lands after substantive code, `exact_head` may bind the substantive implementation commit rather than self-reference.

### Directional performance posture

The roadmap's V4.2 requirement is structural first: exact support indexes must remove whole-space supporter rediscovery.

Do not invent a new hard latency SLO not present in canonical architecture merely to produce a number.

Record timings for characterization and compare unrelated 1k/10k workloads.

---

## §17 Expected implementation shape

Illustrative only:

```python
class EvidenceReadService:
    def get_assertion_evidence(
        self,
        context: KnowledgeReadContext,
        assertion_id: str,
    ) -> AssertionEvidenceResult:
        ...

    def get_evidence(
        self,
        context: KnowledgeReadContext,
        evidence_ref_id: str,
    ) -> EvidenceLookupResult:
        ...


class SourceAnchorService:
    def resolve_source_anchor(
        self,
        context: KnowledgeReadContext,
        anchor_id: str,
    ) -> SourceAnchorResolution:
        ...
```

Preferred decomposition:

```text
exact target lookup
→ exact structural supporter discovery
→ V2 candidate admission
→ admitted-only evidence/source assembly
→ deterministic anchor derivation
→ immutable result + semantic digest
```

Anchor resolution:

```text
parse exact target from anchor
→ exact evidence/supporter lookup
→ V2 admission
→ provenance
→ recompute current anchor
→ exact identity compare
```

Prefer extracting one shared internal source DTO/direct-support assembler from V3/V4.1 instead of copying subtle provenance/digest semantics into three services.

---

## §18 Explicitly out of scope

Do **not** implement in V4.2:

```text
lexical search
alias search
ranked search
FTS/BM25
vector retrieval
semantic retrieval
source-anchor search
list-all evidence
list-all source artifacts
source body fetching
PDF/text body opening
source body storage access through public API
mutable head resolution
KnowledgeSpace durable runtime
native vNext writes/publication
PostgreSQL vNext authority migration
bridge-genesis migration
DungeonBuddy production domain policy
DungeonBuddy repin/cutover
current World public-reader replacement
historical-reader quarantine/deletion
Redis/distributed cache
new graph database
```

V4.3 owns search.

---

## §19 Stop / rebrief conditions

Stop and return to Steward if any become true:

1. exact assertion/evidence retrieval requires full-space projection;
2. evidence authority cannot be derived safely from admitted supporter assertions;
3. evidence with zero admitted supporters must be exposed for a required product workflow;
4. correct source-anchor resolution requires scanning all EvidenceRefs or all assertions;
5. anchor target recovery requires a new durable reverse index or frozen V0 contract change;
6. an anchor must act as authorization independent of V2 admission;
7. source-body access is required for anchor correctness;
8. source freshness cannot remain coherent through one pinned `KnowledgeReadContext`;
9. evidence/support result correctness requires a revision-only mutable-authority cache;
10. Buddy/TTRPG vocabulary must enter generic V4.2 code;
11. V4.3 search/ranking is required before exact support can work;
12. current public World retrieval must change to prove V4.2;
13. tests must weaken V2/V3/V4.1 fail-closed semantics to proceed.

Stop report:

```text
Stop condition:
Roadmap phase:
Observed evidence:
Which assumption failed:
Affected authority/architecture document:
Why V4.2 cannot safely compensate locally:
Proposed decision / experiment:
What remains safe in parallel:
```

Architectural assumption change → update canonical architecture/roadmap before resuming.

---

## §20 Activation bookkeeping task

This draft deliberately does **not** mutate Steward today because V4.1 has not been accepted.

When V4.1 passes and merges, the V4.2 handoff/bookkeeping PR must update Steward before it can merge.

Required exact facts:

```text
V4.1 implementation PR number/title
actual V4.1 merge SHA
accepted V4.1 head SHA
logical review-cycle count
final PASS review ID
V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED
Docs/Benchmarks/vnext_neighborhood_10k_v1.json
benchmark substantive head
structural gate / key locality evidence
V4.1 COMPLETE
V4.2 ACTIVE
V4.3 BLOCKED ON V4.2 ACCEPTANCE
V5 BLOCKED ON V4.3 ACCEPTANCE
```

Also update this handoff header/status with the same predecessor facts.

Do not fill these values from chat or anticipated SHAs. Read them from merged repository/PR truth.

---

## §21 V4.2 implementation PR body requirements

The eventual implementation PR should contain:

```text
Primary question
Exact base SHA (merged V4.2 handoff/bookkeeping PR)
Exact substantive head
Frozen V0 aggregate
Accepted V4.1 predecessor identity
Exact assertion-evidence authority shape
Exact evidence-supporter authority shape
Anchor token/revalidation design
Privacy behavior for missing vs hidden targets
Semantic witnesses
Structural work evidence
Benchmark artifact + substantive head
Actual tests/CI
Known inherited failures
What remains false
Named successor: V4.3 deterministic indexed search
```

Do not claim V4.2 acceptance before Steward records it.

---

## §22 Review gate

Steward review must verify:

### Sequencing

- V4.1 accepted and merged before this handoff activates;
- Steward contains exact V4.1 accepted facts;
- V4.2 implementation branches from the merged/activated handoff;
- V4.3 remains blocked.

### Authority/privacy

- assertion target itself passes V2 before evidence leaks;
- evidence is available only through admitted supporter assertions;
- hidden/missing evidence cases are public-safe;
- mixed-support evidence returns admitted supporters only;
- source lifecycle/visibility remains fail-closed;
- anchors never bypass V2.

### Structural work

- assertion → evidence uses `assertion_evidence`;
- evidence → supporters uses `evidence_supporters`;
- anchor resolution recovers exact evidence target without global scan;
- no full projection;
- unrelated-space growth does not increase fixed-target support work;
- high-support target cost is honest.

### Coherence/digests

- one pinned context/source epoch per operation;
- new context observes source changes;
- visible authority changes affect digests/anchors;
- hidden excluded changes do not perturb visible result digests;
- immutable DTO backing cannot be poisoned.

### Regression/scope

- V0 unchanged;
- V1/V2/V3/V4.1 green apart from explicitly accepted inherited baseline failures;
- current World runtime unchanged;
- no V4.3/V5 creep.

Only successful implementation disposition:

```text
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
```

After V4.2 merges, the V4.3 successor handoff/bookkeeping PR records:

```text
actual V4.2 merge SHA
accepted V4.2 head
review-cycle count
final PASS review ID
V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED
vnext_evidence_support_10k_v1.json evidence
V4.2 COMPLETE
V4.3 ACTIVE
V5 BLOCKED ON V4.3 ACCEPTANCE
```

---

## §23 What remains false after this handoff eventually activates

Even after the V4.2 handoff/bookkeeping PR merges, until implementation is accepted:

- no standalone vNext assertion-evidence API is accepted;
- no standalone vNext evidence lookup API is accepted;
- no vNext source-anchor generation/revalidation API is accepted;
- no deterministic indexed search API is accepted;
- no source-body opening API is accepted;
- no vNext KnowledgeSpace/head storage runtime exists;
- no native vNext governed write path exists;
- no bridge-genesis migration exists;
- no current public World cutover has occurred;
- no historical-reader quarantine/deletion is authorized;
- no DungeonBuddy runtime repin/cutover has occurred;
- deeper storage optimization remains unauthorized.

This design is intentionally early. V4.1 implementation evidence outranks it and may require revision before activation.
