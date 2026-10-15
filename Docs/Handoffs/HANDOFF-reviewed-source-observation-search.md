# Reviewed source observation discovery

Status: ACTIVE. PRIME implements; ARCHITECTURE independently reviews.
Base: `1d120886b00acf7f97b3744e88619abd97c34591`.
Branch: `codex/reviewed-source-search`; topology: serial Core producer, then
separately bounded Buddy consumer after accepted Core revision.

## Outcome and contract

Ordinary Mirathorn conversation can open sources after Buddy #1199, but Core
search for role/concern terms finds nothing when those terms live only in a
reviewed source observation. Exact-name lookup reaches that preserved facet.
Core owns revision-scoped discovery; Buddy owns its Harness presentation.

Reuse the existing finalized-publication observation admission path once per
nonempty search. Rank admitted subjects from eligible observation text without
mutating canonical summaries, properties, relationships or membership. Return
separate typed matching excerpts with source/review/publication/assertion
identity, qualification and evidence refs; derive openable anchors from the
same coherent read. Excerpts carry exact original offsets, original length and
SHA256; an excerpt is navigation/evidence discovery, not a new canonical fact.

Preserve exact identity and explicit seeds, alias exclusions, deterministic
ties, scope/focus/visibility, correction suppression and result bounds. Multiple
observations must not accumulate a ranking bonus. Matching observations and
canonical property rows share the existing assertion count budget; report
truncation. Do not scan publication history for an empty/noise-only query.
Bound each excerpt to768Unicode characters and report its slice explicitly.

## Exact write lease

- `Docs/Handoffs/HANDOFF-reviewed-source-observation-search.md`
- `src/dungeonmind/application/world_graph_retrieval.py`
- `tests/conformance/test_reviewed_source_observation_search.py`

No open Core PRs at activation. Isolated checkout
`/tmp/prime-mind-reviewed-source-search`. No serving runtime, retained state,
provider, schema migration, vector index or source-file edits.

## Verification

Synthetic accepted publication: observation-only role/concern query finds
subject with unchanged canonical fields, typed evidence and openable anchor.
Parent/unpublished/rejected/deferred/private/out-of-scope/corrected/invalid
sources cannot affect hits. V3 worldbuilding evidence follows the same rules.
Prove deterministic bounded excerpts and matching history without duplicate
ranking inflation; exact identities/seeds/alias blocking remain dominant.
Run existing native retrieval/observation conformance and owning search unit
suite, Ruff and cumulative diff. Open PR, request independent exact-head review.
Buddy adoption must measure complete serialized Harness payload, including its
ledger; no live conversation acceptance is claimed by this producer slice.

CI contract settlement: additionally lease
`tests/unit/test_vnext_knowledge_read_context.py`, changing only the shared
expected `GraphSearchResult` field tuple to include this intentional additive
reviewed-source match facet. The three vNext suites reuse that expectation;
retain their checks for every other public type, field and service signature.
