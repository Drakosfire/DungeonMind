# MIND — indexed authorized alias-search read

ACTIVE. Owner/designer: MIND Elderwyld completion lane under explicit operator
full design/implementation/review/merge/launch authority. No ARCHITECTURE or PRIME
gate. Core branchcodex/v10-authorized-alias-search, exactbase
cf197b9939f7b9106c75a8afb9fcf918c8b4aa1c in the existing task-owned Core checkout.
Serial after Buddy4120/4122 merged035419350/0044d0598. This is a generic Core
prerequisite, followed by a separate exact-pin Buddy adoption/default proof;
there is no unmerged Git stack. Search/default activation is not this slice.

## Outcome, critique and authority

Buddy SubjectSearch cannot drop classic alias phrase/token discovery while
retiring its classic reader. Exact alias lookup alone misses those candidates;
whole-World entity admission would restore graph-size work. Add a generic alias
read over indexed structural candidates, using existing alias authorization.
No domain labels/scores, alias scope invention or raw-index authority. Existing
SearchReadService behavior, frozen V0 wire contracts and source writes stay intact.

Choose a separately versioned lazy structural index/cache, built only by alias
search. Do not add work to ParsedKnowledgeRevision construction, neighborhood
reads, builder or artifact decoding. Current artifacts store verified primary
facts, not indexes; retain parsed model/format/compatibility/source-wire identities.
This is an explicit revision-local lexical accelerator permitted by accepted
read architecture, not activation of post-vNext O1/O2 or new physical storage.
First alias query builds O(alias text) index work; warm reuse avoids that build.
Never claim constant first-alias cost or a deployed speed improvement from units.

## Exclusive ten-path lease and review map

- This handoff; Docs/Decisions/ADR-0030-authorized-alias-search.md (new).
- Docs/Plans/HANDOFF-MIND-prospective-evidence-aliases.md: compact truthful
  predecessor231 settlement and known Buddy adoption facts only.
- src/dungeonmind/application/vnext/alias_search_index.py (new): pure versioned
  normalization/matching/postings and explicit bounded structural cache.
- src/dungeonmind/application/vnext/alias_search.py (new): public authorized read,
  immutable results and private work trace; call existing _authorize_aliases.
- src/dungeonmind/application/vnext/__init__.py: explicit additive public exports.
- tests/unit/test_vnext_alias_search_index.py (new): independent matching oracle,
  immutable indexes/cache identity/eviction/concurrency/retention and work proof.
- tests/unit/test_vnext_alias_search.py (new): actual read/admission/source lifecycle.
- tests/unit/test_vnext_read_artifact.py: current artifact parity and no eager build.
- tests/integration/test_postgres_vnext_read_artifacts.py: existing-format artifact
  compatibility through the actual PostgreSQL reader and new alias API.

Core open158/150/149/148/147/146/145/143 patches inspected at activation: no vNext
runtime overlap.158 owns global Steward/roadmap files; do not edit them. Do not
edit model/builder/codec/formats/entity admission/SQL schemas, Buddy, WK, profiles,
CI/classification, dependencies or serving. Return to MIND for any necessary
boundary/path/capability rebrief; do not absorb adjacent native label/search work.

## Candidate and cache contract

Use casefolded character-gram postings keyed to alias IDs (defined one/two/three
codepoint handling). Union conservative candidates for normalized full query,
ASCII alphanumeric tokens of length>1, and their defined singular/plural variants.
Verify exact text after lookup: trimmed casefold exact equality; literal phrase
with ASCII letter/digit/underscore/colon/hyphen continuation boundaries; tokens
with naive singular/plural tolerance. No arbitrary prefix/substring match.
There is no stopword omission in this generic candidate policy; consumer ranking
may ignore token reasons. Match tokens/kinds are deterministic and versioned.

Cache stores only immutable postings, alias-ID strings and complete identity
values, never ParsedKnowledgeRevision/context/source reader/admission/provenance.
Key includes space/revision, graph payload hash, parsed semantic digest, parsed
format and compatibility key (therefore pinned domain/profile compatibility),
plus index/matching algorithm version. Consume existing computed digests: no
whole-revision serialization/hash on lookup. Do not use revision ID or bare id()
alone. Explicit max_entries/max_postings bounds; deterministic eviction/clear;
oversized indexes may serve uncached. No process-global cache, silent hidden
retention, partial index or fabricated completeness. Optional caller injection
makes lifetime explicit. Synchronize builds/eviction; authorize outside that lock.

Index helper interface for implementation split: AliasSearchIndexCache with
get_or_build(parsed) -> (immutable index, cache_hit), clear(), entry_count and
posting_count; immutable index exposes key, posting_count and
candidate_ids(terms: tuple[str,...]) -> sorted alias IDs. Private pure helpers
normalize_alias_query, alias_query_tokens, alias_token_variants and
alias_match_text(text, normalized_query, tokens) -> (ordered kinds, matched_tokens).
Service imports those internally; Buddy must use the public authorized read.

## Public read and privacy contract

AliasSearchReadService.search_aliases(context, query, *, limit=20, index_cache=None)
returns an immutable AliasSearchResult with pinned SearchReadIdentity, normalized
query, request digest, matching-policy version, limit, tuple AliasSearchHit,
explicit complete/partial status and result digest. Each hit contains the actual
ParsedIdentityAlias, match kinds/tokens and ambiguous flag. No public structural
candidate/work/source inventory. Trace counts are package-private characterization.
Use SearchReadIntegrityError for invalid query/limit/cache identity; preserve
existing deterministic persistence/admission failures. Reject bool/negative limits.

Re-fetch/verify indexed aliases from this context; authorize all actual matching
records through existing standing/evidence/source/visibility owner before bounds.
Aliases remain source-authorized space-wide identities, without requiring an
admitted assertion or adding scope. Buddy must separately require scoped entity
presence. Empty evidence retains existing alias semantics. Reauthorize every call
against its fresh coherent read context, even on cache hit; no cached admission.

Compute ambiguity from all authorized aliases sharing exact normalized alias text
and distinct entity IDs before truncation. Duplicates for one entity do not invent
ambiguity. Limit1 cannot turn an ambiguous identity unique. Hidden/withdrawn aliases
cannot add public text, counts, suppression or digest influence. Do not port the
classic omitted-alias suppression policy, which conflicts with authorized-only
privacy. Order by strongest generic match class, matched-token strength, normalized
text, entity ID and alias ID, with no Buddy score weights. Mark partial/result_limit
if authorized hits exceed limit (including limit0); never label a capped stream
complete. Complete-stream consumers may request len(parsed.aliases_by_id), an O(1)
bound, before their own composition. Common queries may have large true candidates;
no arbitrary pre-admission work ceiling is introduced by this slice.

## Proof and delivery

Independent brute-force oracle for exact/phrase/token/plural, Unicode casefold,
punctuation/emoji, opaque-ID boundaries and nonmatching prefixes; input permutation,
immutability and deterministic ties/digests; duplicate/ambiguous aliases before cap;
standing/source labels/missing/corrupt/withdrawn support; index reused with new read
context denies withdrawn evidence; globally authorized aliases without assertions;
no visibility-driven ordering/limit/privacy leak. Candidate-local provenance and
policy work; cache-hit no rebuild; first build explicitly counted as alias-linear.
Unrelated postings cannot cause unrelated alias admission or source fetches.

Existing-format artifact -> index/query equals ordinary parse; semantic digest,
compatibility/source bytes unchanged. Patch index construction to fail while
ordinary/artifact/neighborhood preparation runs, proving it is not eager. Actual
PostgreSQL artifact path remains source-verified, no backfill or read mutation.
Full required core/integration checks plus Ruff/Pyright and independent cumulative
source/evidence review before expected-head merge. Frozen classic retrieval baseline
is not rerun. No standalone latency claim from lookup counters. Buddy adoption must
measure candidate routes and retain V8 speed gate before any deployment/cutover.

Alias API alone is not classic label/ranking equivalence. Existing native search
admits/ranks all candidates before slicing; len(parsed.entities_by_id) requests its
complete native stream, not complete classic candidates. Consumer proof must handle
matching-policy differences and compose before final cap; never union into top20
and claim parity. Search/related-recap retirement and V11 remain unaccepted here.

## Resources and retention

Reuse /home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind;
verified Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and writable parent before
allocation. Scratch/v8-core/v10-authorized-alias-search; existing Core unit/tools
cache. Only a newly named task-owned disposable PostgreSQL test DB on32903 may
receive destructive fixtures; do not reuse prior proof DBs or live54330/54331.
No new checkout/port/provider/ingestion/serving state. MIND retains scratch/cache/
proof resources for active goal; no manual removal/reclaimedbytes claim. Cleanup
follow-up needs approvedscope, active task/process/mount/DB, dirty/unique-data and
protected-commit checks at goal completion. Full optimization/deployment/rollback/
V10/V11 remains active; no ARCHITECTURE wait or narrowed completion token.
