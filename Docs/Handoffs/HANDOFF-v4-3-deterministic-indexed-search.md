# HANDOFF — V4.3 deterministic indexed search

**Created:** 2026-09-17  
**Status:** ACTIVE / IMPLEMENTATION NOT YET ACCEPTED — V4.2 accepted and merged; V4.3 may begin from current `main`  
**Repository:** `Drakosfire/DungeonMind`  
**Implementation branch:** `kernel/v4-3-deterministic-indexed-search`  
**Accepted predecessor merge:** `74733ddf9fc338469293c27c12302004fc1be99a` — merged PR #67  
**Implementation branch base:** branch from the current `main` that contains this handoff; record that exact SHA in the implementation PR before runtime work begins  
**Frozen vNext contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**Roadmap phase:** V4.3 — deterministic indexed search  
**Successor:** V5 — generic governed writes  
**Conversation provenance:** `MIND`  
**One-line mission:** Make deterministic entity discovery a first-class bounded vNext read by generating match-witness candidates from immutable revision-local indexes before authority evaluation, then returning only admissible matches without full-space projection, full-space scanning, hidden-match leakage, or domain-specific search semantics.

---

# 0. Repository truth and accepted predecessor

V4.2 is complete.

Binding predecessor facts:

```text
PR:
  #67 — KERNEL: V4.2 evidence reads + source anchors

implementation base:
  7f5df9eace6f1ab23a0d817e0b350c379923641f

accepted exact head:
  84fe11fbf583732366d3828e01ed9a0051e4bd7a

substantive repair head:
  28a4dbe16507b89d601a335b559d3203623cffd4

logical Steward review cycles:
  2

final PASS review:
  5237236070

disposition:
  V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED

actual merge:
  74733ddf9fc338469293c27c12302004fc1be99a

benchmark:
  Docs/Benchmarks/vnext_evidence_support_10k_v1.json

benchmark substantive head:
  28a4dbe16507b89d601a335b559d3203623cffd4

structural gate:
  PASS

10k exact evidence p95:
  ~2.06 ms
```

The V4.2 acceptance established:

```text
exact assertion
→ candidate-local V2 admission
→ exact evidence support

exact evidence
→ exact supporter index
→ candidate-local V2 admission
→ admitted supporters only

admitted evidence
→ deterministic context-bound source anchor

anchor
→ exact target recovery
→ fresh V2/provenance revalidation
```

It also established the privacy discipline that carries into V4.3:

```text
internal structural diagnostics
≠
public semantic result
```

Raw hidden-candidate counts are not public API.

This handoff is intentionally pre-positioned on `main` by the Steward. Do not create another handoff-only PR.

---

# 1. First implementation commit — close V4.2 and activate V4.3

The code agent must branch from the current `main` containing this handoff.

Before runtime implementation, record the exact branch-base SHA in the PR body and in the durable Steward bookkeeping.

The first implementation commit must contain **no V4.3 runtime implementation**.

Suggested commit:

```text
STEWARDSHIP: complete V4.2 and activate V4.3
```

Update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v4-2-evidence-source-anchors.md
Docs/Roadmaps/ROADMAP.md   # only where needed to reflect the bounded V4.3 contract below
```

Record durably:

```text
V4.2:
  COMPLETE
  V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED

PR #67:
  accepted head:
    84fe11fbf583732366d3828e01ed9a0051e4bd7a

  substantive repair head:
    28a4dbe16507b89d601a335b559d3203623cffd4

  review cycles:
    2

  final PASS:
    5237236070

  merge:
    74733ddf9fc338469293c27c12302004fc1be99a

  benchmark:
    Docs/Benchmarks/vnext_evidence_support_10k_v1.json

V4.3:
  ACTIVE
  IMPLEMENTATION NOT YET ACCEPTED

V5:
  BLOCKED ON V4.3 ACCEPTANCE
```

Advance the V4.2 handoff to accepted/complete truth.

Do not create another V4.3 handoff file. This file is the design authority for the implementation PR.

---

# 2. Required reading

Read, in order:

```text
Docs/Architecture/AUTHORITY.md
Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md
Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v4-2-evidence-source-anchors.md
this handoff
CONTRIBUTING.md
```

Then inspect:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/read_context.py
src/dungeonmind/application/vnext/entity_reads.py
src/dungeonmind/application/vnext/neighborhood.py
src/dungeonmind/application/vnext/evidence_reads.py
src/dungeonmind/application/vnext/source_anchors.py

src/dungeonmind/contracts/vnext/domain.py
src/dungeonmind/contracts/vnext/knowledge.py
src/dungeonmind/contracts/vnext/projection.py
```

The frozen V0 contract aggregate remains authority.

Do not change `contracts/vnext/**` merely to make search convenient.

If V4.3 requires changing the frozen public contract bundle, stop and rebrief.

---

# 3. Primary question

Answer exactly this:

> Can deterministic entity search generate an exact structural match-witness set from immutable revision-local indexes, admit only those witnesses through the pinned V2 authority path, and rank only admitted matches so that work grows with the real query match set rather than the whole KnowledgeSpace, while hidden or excluded matches cannot affect public result membership, ordering, or digest?

Only successful disposition:

```text
V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED
```

Do not claim that disposition in implementation code, tests, benchmark output, or PR prose before Steward exact-head review.

---

# 4. Slice boundary

V4.3 is **not** “build a general search engine.”

It proves one narrow architecture claim:

```text
query
→ revision-local structural candidate generation
→ exact match witnesses
→ candidate-local V2 admission
→ admitted-match aggregation
→ deterministic ranking
→ bounded public results
```

Search indexes discover candidates. They never authorize them.

The important unit is the **match witness**.

For ordinary lexical / predicate / term search, the match witness is an assertion whose searchable structure produced the match. That assertion must pass V2 before it may contribute to a public result or score.

This prevents the unsafe shape:

```text
hidden assertion text matches query
→ entity becomes a candidate
→ unrelated visible assertion makes entity return
```

That would leak the hidden match relation even if the hidden assertion itself were omitted.

V4.3 must instead preserve the structural reason a candidate matched and authorize that reason before using it.

---

# 5. Public search surface

Preferred conceptual API:

```python
SearchReadService.search_entities(
    context: KnowledgeReadContext,
    query: str,
    *,
    limit: int = 20,
) -> SearchResult
```

Exact naming is implementation latitude.

The public result should be an application-layer immutable DTO, not a new frozen V0 contract.

Conceptually:

```text
SearchResult
  identity
  normalized_query
  hits[]
  completeness
  result_digest

SearchHit
  entity
  admitted_match_assertions[]
  match_kinds[]
  deterministic_score

SearchCompleteness
  complete | partial
  reason?
```

Ordinary V4.3 search should be `complete` with respect to the implemented deterministic index semantics.

`limit` is an output/ranking limit. It must not silently become a pre-admission candidate cap that lets hidden candidates suppress visible results.

Internal work telemetry may exist for characterization but must follow the V4.2 privacy rule: raw hidden-candidate counts are not public semantic output.

---

# 6. Searchable structural sources

V4.3 may use only immutable, rebuildable revision-local structures.

## 6.1 Exact entity ID

If the normalized query exactly equals an existing `entity_id`, the service may produce an exact-ID candidate through direct lookup.

This path may reuse accepted V3 exact-entity semantics.

Do not substring-scan entity IDs.

Exact ID match outranks non-exact lexical matches.

## 6.2 String-literal tokens

The current `lexical_candidate_index` maps tokens to entity IDs and therefore loses the assertion that caused a string-literal match.

That is insufficient as the public authorization witness for V4.3.

Add or derive an assertion-level lexical index, conceptually:

```text
lexical_assertion_index
  normalized token
  → assertion IDs whose literal string value contains that token
```

The existing entity-level lexical index may remain for compatibility/characterization, but public V4.3 lexical authority must be recoverable to exact matching assertion IDs without scanning all subject assertions.

## 6.3 Qualified predicates

Add or derive a deterministic revision-local index:

```text
predicate_assertion_index
  qualified predicate term
  → assertion IDs
```

A query that exactly matches a qualified predicate may produce those assertions as match witnesses.

Do not fuzzy-match predicate names in V4.3.

## 6.4 Qualified term-ref values

Add or derive:

```text
term_ref_assertion_index
  qualified term-ref value
  → assertion IDs
```

A query that exactly matches a qualified term may produce those assertions as match witnesses.

## 6.5 Exact literal lookup

The existing `literal_exact_index[(predicate, canonical_json_text)]` remains valid structural substrate.

V4.3 does not need to invent a public query language for predicate/value exact lookup unless doing so is necessary to satisfy a concrete acceptance fixture. Do not broaden the slice merely because the index exists.

---

# 7. Alias decision — do not improvise authority

`IdentityAlias` is Kernel identity machinery, but it is **not** an assertion and does not currently pass through the V2 assertion-admission seam.

The current `alias_exact_index` is therefore valid structural substrate but is not, by itself, authorization to reveal that an alias maps to an entity.

V4.3 must not implement this unsafe shape:

```text
normalized alias match
→ entity ID
→ entity has some unrelated admitted assertion
→ return entity
```

That leaks the alias relation without authorizing the alias match itself.

Therefore, for this slice:

```text
public alias-backed search is NOT REQUIRED for acceptance
```

The first implementation bookkeeping commit must tighten the roadmap wording accordingly: the revision may retain `alias_exact_index`, but V4.3 public results are assertion-backed unless an already-accepted checked-in authority rule is found that can authorize an alias match without new contract semantics.

If implementation discovers that alias search is already unambiguously authorized by existing accepted contracts/architecture, stop before coding it and hand that evidence back to the Steward for a bounded design amendment.

Do not invent alias scope, alias visibility, alias domain-policy semantics, or “aliases are public by default.”

This is intentional scope control, not a missing optimization.

---

# 8. Query normalization

V4.3 normalization must be deterministic, locale-independent, and shared between index construction and lookup.

At minimum:

```text
trim surrounding whitespace
case-fold or lowercase consistently with the chosen index contract
tokenize with one checked-in deterministic rule
reject an empty normalized query
```

Do not have builder normalization and search normalization drift apart.

Prefer one helper owned by the vNext search/index layer rather than duplicated regexes with subtly different semantics.

Changing normalization changes search semantics. Cover it with direct tests and deterministic digest witnesses.

No stemming, spell correction, fuzzy edit distance, synonym expansion, semantic embeddings, or language-model rewriting in V4.3.

---

# 9. Candidate generation and admission

For ordinary assertion-backed search:

```text
normalized query
→ exact token / predicate / term postings
→ union exact matching assertion IDs
→ deterministic dedupe
→ V2 evaluate_candidates(exact match-witness assertion IDs)
→ admitted matching assertion IDs only
```

Do not:

```text
scan all assertions
scan all entities
build a full projection
run V3 complete reads for every structural candidate
admit unrelated assertions merely because they share a subject entity
```

After V2 admission:

```text
admitted match assertions
→ group by subject_entity_id
→ exact entity lookup for each admitted subject
→ score using admitted matches only
→ deterministic sort
→ apply public result limit
```

If an admitted match assertion references an entity that is missing from the immutable revision, fail closed as structural corruption rather than skipping it silently.

---

# 10. Hidden-match non-interference

This is the central V4.3 privacy invariant.

Given the same visible/admitted knowledge, adding unrelated or hidden matching assertions must not change:

```text
which visible entities are returned
visible hit ordering
visible deterministic scores
visible match kinds
visible result digest
```

Hidden/excluded matches may increase internal characterization work because they are real structural candidates.

They may **not** contribute to ranking or consume a pre-admission top-K slot.

Therefore the implementation must not do:

```text
structural rank all matches
→ truncate to K
→ admit only K
```

because hidden high-ranked candidates could suppress visible lower-ranked candidates.

Correct shape:

```text
complete exact structural match set for the implemented query semantics
→ admission
→ rank admitted matches
→ output limit
```

This means a very common token may honestly produce a large candidate set. That is not a correctness failure. Characterize it explicitly rather than hiding it behind an authority-unsafe cap.

---

# 11. Deterministic ranking

Keep ranking deliberately simple.

Ranking must depend only on:

```text
caller query
admitted match witnesses
stable immutable IDs / deterministic structural fields
```

It must not depend on:

```text
hidden/excluded match counts
iteration order
Python hash order
wall-clock state
source repository ordering
LLM judgment
embedding similarity
mutable popularity counters
```

Preferred ranking posture:

```text
1. exact entity-ID match
2. assertion-backed exact qualified predicate / term match
3. assertion-backed lexical match strength
4. stable entity_id tie-break
```

Exact numeric weights are implementation latitude but must be small, integer/deterministic, documented in code, and covered by ranking tests.

For multi-token lexical queries, score only tokens witnessed by admitted assertions.

If two results are semantically tied, `entity_id` ascending is the final tie-breaker.

Repeated identical search over the same pinned context must return byte-for-byte equivalent semantic result content and the same digest.

---

# 12. Output semantics

A public hit returns only admitted match material required to explain why the entity matched.

Do not automatically expand a search hit into a complete entity read.

Search is discovery, not full object hydration.

Conceptually:

```text
hit:
  entity identity
  admitted matching assertions
  deterministic match kinds / score
```

A consumer that wants full selected-object truth can call accepted V3 `get_complete_entity` after selecting a hit.

This keeps search cost proportional to search candidates rather than multiplying it by complete-object assembly for every result.

Do not return evidence/source/anchor bundles for every search hit unless the existing application result contract requires them. V4.3 only needs enough authority evaluation to know that the match witness is admissible.

---

# 13. Result digest

The public result digest must bind all caller-visible search semantics that could affect interpretation, including at minimum:

```text
space/revision/domain/profile identity
normalized query
limit
ordered returned entity IDs
ordered admitted match assertion IDs per hit
ordered match kinds per hit
deterministic score per hit
completeness state
```

Do not hash:

```text
excluded assertion IDs
V2 exclusion reasons
raw structural candidate counts
hidden-match counts
internal timing/work traces
```

A hidden-only change that leaves visible admitted results unchanged must leave the public semantic digest unchanged.

---

# 14. Work characterization

V4.3 must make its cost model visible.

Internal characterization should record enough to prove at least:

```text
index lookups performed
structural assertion candidates discovered
deduped match-witness assertions
assertions evaluated
policy evaluations
unique artifact IDs requested
unique revision IDs requested
provenance snapshot calls
admitted match assertions
returned entities
```

If exact-ID lookup is exercised, characterize that separately from assertion-backed lexical search.

Raw candidate counts are internal characterization only, following the V4.2 privacy discipline.

Do not expose them through ordinary public search result DTOs.

---

# 15. Required semantic fixtures

At minimum cover:

## A. Exact entity ID

```text
query == exact entity ID
→ deterministic exact hit
→ no full-space scan
```

## B. Single lexical token

```text
visible string-literal assertion contains token
→ assertion index produces exact witness
→ V2 admits witness
→ subject entity returned
```

## C. Multi-token aggregation

```text
multiple admitted matching assertions / tokens
→ one entity hit
→ deterministic admitted-only score
```

## D. Predicate match

```text
query == exact qualified predicate
→ only assertions with that predicate are candidates
→ admitted subjects returned
```

## E. Term-ref match

```text
query == exact qualified term-ref value
→ only exact term-ref assertions are candidates
```

## F. Hidden-only match

```text
hidden matching assertion
→ no public result
→ no hidden ID/detail/count in public DTO
```

## G. Mixed visible + hidden match on same entity

```text
visible witness + hidden witness both match
→ entity may return because of visible witness
→ score/match kinds/digest use visible admitted witness only
```

## H. Hidden high-score decoys

Construct hidden/excluded candidates that would outrank a visible result structurally.

Prove they do not suppress or reorder the visible result because admission precedes public ranking/limit.

## I. Out-of-scope / standing / domain-policy / source-inadmissible matches

Each must behave as non-matches publicly.

## J. Deterministic tie

Two equally scored visible entities return in stable `entity_id` order.

## K. Unrelated growth

Grow from approximately 1k to 10k with non-matching entities/assertions.

Fixed low-frequency query candidate/admission work must remain unchanged.

## L. Honest high-frequency query

Create a token with many real matching assertions.

Work must scale with that real match set and must not be silently truncated before admission.

## M. Genericity

Exercise both:

```text
organizational-memory-shaped opaque domain
DungeonBuddy-shaped opaque domain fixture
```

No TTRPG vocabulary in generic search implementation.

## N. Alias safety

Prove public V4.3 does not use `alias_exact_index` as an authorization bypass.

---

# 16. Benchmark / characterization artifact

Add a deterministic synthetic benchmark, preferred artifact:

```text
Docs/Benchmarks/vnext_deterministic_search_10k_v1.json
```

and a generator under:

```text
benchmarks/vnext_deterministic_search_10k.py
```

At minimum include:

```text
1k low-frequency lexical query
10k low-frequency lexical query
10k exact entity-ID query
10k predicate query
10k term-ref query
10k mixed visible/hidden query
10k hidden-decoy ranking query
10k high-frequency real-match query
```

Record:

```text
exact base
exact substantive head
fixture parameters / deterministic seed
semantic result digest
returned hit count
structural candidate count
assertions evaluated
policy evaluations
unique source work
p50 / p95
structural gate result
```

Directional architecture target:

```text
10k deterministic search p95 < 100 ms
```

This is directional evidence, not permission to weaken semantics.

Primary acceptance is structural:

```text
non-matching corpus growth does not increase fixed-query candidate/admission work
```

and semantic:

```text
hidden/excluded matches cannot influence visible result membership/order/digest
```

The high-frequency lane is expected to scale with the real matching set. Record that honestly.

---

# 17. Acceptance criteria

Steward acceptance requires all of the following on one exact reviewed head.

## Bookkeeping

- V4.2 is durably marked COMPLETE with PR #67 accepted head, repair head, review count, final review, merge SHA, and benchmark artifact.
- V4.3 is durably ACTIVE / IMPLEMENTATION IN REVIEW / NOT ACCEPTED.
- V5 remains BLOCKED ON V4.3 ACCEPTANCE.
- The implementation PR records the exact branch base from `main` containing this handoff.
- Frozen V0 aggregate remains unchanged.

## Structural candidate generation

- Search does not invoke full projection.
- Search does not scan all entities or all assertions for an ordinary low-frequency query.
- String-literal lexical matches preserve exact assertion-level match witnesses.
- Predicate and term-ref matches use deterministic revision-local indexes.
- Exact entity-ID search uses direct structural lookup.
- Indexes remain immutable, revision-local, rebuildable derived state and never become authority.

## Authority

- Every non-ID public search match is justified by at least one admitted exact match-witness assertion.
- Candidate assertions pass through the existing pinned V2 admission path.
- Domain policy may narrow results and can never broaden Kernel admission.
- Search ranking never manufactures authority.
- Public alias search does not bypass the absence of accepted alias-admission semantics.

## Privacy / non-interference

- Hidden-only, out-of-scope, standing-excluded, domain-policy-excluded, and source-inadmissible matches return no public hit.
- Hidden/excluded match witnesses never contribute score, match kind, or digest.
- Hidden high-ranked structural candidates cannot consume a pre-admission result cap and suppress visible hits.
- Public DTOs do not expose raw structural candidate counts or V2 exclusion reasons.
- Adding hidden matching knowledge while visible admitted knowledge is unchanged does not change visible result membership, order, score, or digest.

## Determinism

- Query normalization is shared/deterministic.
- Candidate dedupe is deterministic.
- Ranking uses admitted matches only.
- Ties resolve deterministically by stable ID.
- Repeated identical search on one pinned context produces identical semantic results and digest.
- Result digest binds all caller-visible search semantics and excludes hidden/internal telemetry.

## Locality / performance shape

- Fixed low-frequency query work remains unchanged under unrelated 1k→10k corpus growth.
- Source/provenance loading is candidate-local.
- High-frequency query work equals the real structural match set rather than an arbitrary truncation.
- The 10k characterization artifact is generated from the substantive implementation head and reports a structural PASS.
- 10k deterministic search p95 is recorded against the `<100 ms` directional target without treating timing as a correctness substitute.

## Genericity

- Organizational-memory and DungeonBuddy-shaped fixtures use the same search engine.
- Generic V4.3 code contains no `GM`, `PLAYER`, campaign, NPC, fictional-time, or other TTRPG-specific search logic.
- No vector/embedding dependency is introduced.

## Regression

- V0 frozen-contract tests remain green.
- V1 normalized/index tests remain green.
- V2 admission tests remain green.
- V3 exact/complete entity read tests remain green.
- V4.1 neighborhood tests remain green.
- V4.2 evidence/anchor tests remain green.
- Ruff / type checking / unit tests are green for the intended vNext surface.
- Any inherited baseline failure is reproduced and classified against the exact implementation base rather than merely asserted.

Only after every applicable criterion is evidenced may Steward record:

```text
V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED
```

---

# 18. Explicit non-goals

Do not implement in V4.3:

```text
fuzzy search
edit-distance spelling correction
stemming / lemmatization
synonym expansion
BM25 / external FTS backend
vector embeddings
semantic/vector retrieval
hybrid retrieval
LLM query rewriting
LLM reranking
cross-revision search
cross-space search
search-result hydration into complete entity reads
source-body fetch
new public alias authorization semantics
native vNext writes/publication
KnowledgeSpace/head persistence runtime
bridge-genesis migration
DungeonBuddy cutover
current World reader replacement
historical-reader deletion/quarantine
Redis
new graph database
revision-only authorization caches
```

FTS/BM25 and vectors remain escalation options only if later measured need justifies them.

---

# 19. Intended changed surface

Prefer a tight implementation surface, approximately:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v4-2-evidence-source-anchors.md
Docs/Roadmaps/ROADMAP.md

src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/search.py          # expected new service
src/dungeonmind/application/vnext/errors.py         # only if a search-specific integrity error is justified
src/dungeonmind/application/vnext/__init__.py       # public semantic service/results only

tests/unit/test_vnext_parsed_knowledge_revision.py  # or existing V1 index owner
 tests/unit/test_vnext_search.py                     # expected focused acceptance suite

benchmarks/vnext_deterministic_search_10k.py
Docs/Benchmarks/vnext_deterministic_search_10k_v1.json
```

Exact test filename is implementation latitude.

Do not touch `contracts/vnext/**` unless a stop/rebrief is triggered and Steward explicitly redesigns the slice.

Do not modify current World search/retrieval to make the vNext tests pass.

---

# 20. Stop / rebrief conditions

Stop rather than compensating locally if any of these become true:

- frozen V0 contract changes are required;
- correct low-frequency search requires full projection;
- correct low-frequency search requires scanning all entities or all assertions;
- lexical search cannot preserve the exact assertion that caused the match without redesigning accepted V1 state beyond a rebuildable derived index;
- hidden/excluded candidates must be ranked before admission to achieve the desired API;
- a pre-admission candidate cap is required for correctness or performance;
- visible ranking necessarily depends on hidden candidate counts;
- alias-backed public search requires inventing alias visibility/scope/domain-admission semantics;
- current public World readers must change;
- a revision-only authorization cache is required;
- vector search or external FTS is required to make the baseline deterministic search viable;
- Buddy/TTRPG vocabulary must enter generic Kernel search code;
- V2 fail-closed admission must be weakened;
- V3/V4.1/V4.2 accepted semantics regress.

When a stop condition fires, report:

```text
Stop condition:
Roadmap phase:
Observed evidence:
Which assumption failed:
Affected authority/architecture document:
Why V4.3 cannot safely compensate:
Proposed design decision / experiment:
What remains safe in parallel:
```

Do not widen the PR silently.

---

# 21. Required implementation evidence

The PR handback must include:

```text
repository
branch
exact branch base
exact reviewed head
substantive implementation head
artifact commit if separate
changed-file census
```

For the primary question, report:

```text
query normalization rule
indexes consulted
match-witness representation
candidate set size
admitted match count
returned hit count
ranking rule
result digest
```

Verification must include exact commands and outcomes for:

```text
ruff
pyright / configured type checker
focused V4.3 tests
V1 index regressions
V2 admission regressions
V3 entity-read regressions
V4.1 neighborhood regressions
V4.2 evidence/anchor regressions
10k V4.3 benchmark characterization
repository CI
```

If repository CI has an inherited failure, provide the exact traceback and prove whether the failing file/behavior is unchanged from the implementation base.

---

# 22. What remains false after V4.3

Even after successful V4.3 acceptance:

```text
no fuzzy / semantic / vector search
no public alias-discovery authority contract
no native vNext governed write runtime
no vNext KnowledgeSpace/head persistence runtime
no bridge-genesis migration
no joint DungeonMind/DungeonBuddy cutover acceptance
no current public World cutover
no historical-reader quarantine/deletion
no deeper storage redesign
```

Search acceptance means only that deterministic indexed discovery is structurally local, authority-preserving, private, generic, and deterministic.

---

# 23. Successor

After Steward records:

```text
V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED
```

V4 is complete and V5 may begin.

V5 primary question remains:

> Can generic governed write contracts preserve immutable revision, explicit head, expected-parent CAS, source/evidence integrity, identity/governance disposition, and replay/recovery semantics after removing World/Graph-Review-specific transport shapes?

Do not begin V5 runtime work in the V4.3 PR.
