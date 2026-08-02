# ADR-0005 — Executable D&D profile boundary and Threat semantics

**Status:** Accepted (PR B.2c)
**Date:** 2026-08-01
**Deciders:** B.2c implementing agent, per operator dispatch
**Supersedes:** none
**Extended by:** ADR-0006 (pinned profile create-or-connect contribution planning)
**Related:** ADR-0004 (semantic profile boundary), `src/dungeonmind_dnd/`,
`contracts/semantic_profile.py` (kernel, unchanged),
`tests/unit/test_import_boundaries.py`

## Question

May the `dungeonmind_dnd` profile package contain executable code, and —
if so — what is the first concrete D&D semantic capability, under what
constraints? ADR-0004 established the one-way kernel/profile boundary with
`dungeonmind_dnd` as a *data-only* descriptor carrier and deliberately left
concrete D&D semantics false. The approaching Threat consumer needs to know
whether a narrow D&D vocabulary can reliably constrain extraction before
any LLM, identity-resolution, or publication capability is built.

## Context

`dm_union_graph_v3` (B.2b) admits qualified `namespace:local` terms against
a pinned descriptor; the kernel validates namespaces only and never
interprets terms. Nothing yet says which exact `dnd5e:*` kinds and
predicates exist, how an extractor proposes graph-shaped candidates, or how
such proposals are validated deterministically before identity work. The
project's graph-construction research identifies the dominant extraction
failures as schema drift, cross-class collisions, predicate drift, inverted
relationships, dangling edges, weak provenance, and premature identity
merging; the recommended minimal sequence is schema-guided packet → typed
node/edge candidates → deterministic validation → (later) identity work →
(later) contribution planning → (later) publication.

A product observation drives the central semantic decision: a creature can
threaten a location now and cease threatening it later. Threat is therefore
contextual, not ontological identity.

## Decision

1. **`dungeonmind_dnd` may contain side-effect-free executable contracts
   and pure deterministic application logic.** The B.2b phrase "data-only
   package" evolves into "profile-owned, side-effect-free package with
   contracts and pure validation". The package performs no registration,
   configuration discovery, network access, database access, provider
   calls, or durable writes, and reads no package data at import time
   (resource reads occur only inside loader functions).
2. **The dependency remains strictly one-way.** No code under
   `src/dungeonmind` imports `dungeonmind_dnd`. The D&D package may import
   only `dungeonmind.contracts.base`, `dungeonmind.contracts.evidence`,
   `dungeonmind.contracts.semantic_profile`, and
   `dungeonmind.domain.canonical` (plus stdlib and pydantic) — enforced by
   `tests/unit/test_import_boundaries.py`.
3. **Profile revision v1 is immutable; v2 carries concrete semantics.**
   `dnd5e-v1.json` is unchanged byte-for-byte. `dnd5e-v2.json`
   (`dungeonmind.dnd5e` / `dnd5e-profile-v2`, namespace `dnd5e`) is the
   exact profile identity pinned by the first vocabulary. Both revisions
   remain loadable; the example registry config retains v1 and adds v2.
4. **The first vocabulary is deliberately Threat-oriented and narrow.**
   `vocabularies/threat-v1.json` (`dmdnd_semantic_vocabulary_v1`) pins the
   full v2 `SemanticProfileRef` (id + revision + descriptor digest) and
   contains exactly four object kinds (`dnd5e:creature`, `dnd5e:location`,
   `dnd5e:faction`, `dnd5e:encounter`) and four predicates
   (`dnd5e:located_at`, `dnd5e:member_of`, `dnd5e:participates_in`,
   `dnd5e:threatens`) with closed subject/object kind direction. Catalog
   digests use DungeonMind canonical JSON hashing; any content change
   requires a new immutable vocabulary revision.
5. **Threat is a contextual `dnd5e:threatens` relationship, never an
   object kind.** The candidate contract rejects `dnd5e:threat` as a kind
   (or surface-form alias) outright. NPC, monster, ally/enemy, creature
   type, encounter role, and mechanics remain unresolved
   classifications/roles for later, independently evidence-scoped slices.
6. **Candidate identity is not graph identity.** Candidates carry
   temporary IDs (never `obj:`/`rel:` prefixes), closed evidence ledgers
   (kernel `dm_evidence_ref_v1` records; every candidate and relationship
   evidenced, no dangling or unused refs), and no properties bags,
   confidence scores, canon/visibility fields, stable IDs, merge outcomes,
   or write-path fields. Existing graph objects are referenced explicitly
   (`existing_object_id` + `expected_kind`) but are **not verified**
   against any graph — that belongs to a graph-aware successor.
7. **Prompt and JSON Schema rendering are deterministic and never
   authority.** The prompt fragment is generated only from catalog data
   plus static contract rules; validation authority is always the catalog
   via `validate_threat_candidate_packet`.
8. **No generic interpretation layer is created.** The kernel still admits
   namespaces only. A graph may contain profile-qualified terms not
   produced by this candidate package. Candidate validation does not make
   a fact canonical. A second, materially different system must create
   pressure before any shared abstraction is designed.
9. **Candidate-to-contribution planning is a named successor (B.2d).**
   This PR produces no graph reads, writes, identity resolutions,
   contribution plans, or publications.
10. **Raw candidate payloads enter only through a package-owned sanitizing
    parse boundary.** `parse_threat_candidate_packet` is the documented
    ingestion API. Pydantic `ValidationError` is converted into a sanitized
    `DndCandidateValidationError` carrying only validator message strings —
    never raw `errors()` records, rejected input values, labels, summaries,
    evidence locators, or source prose (`raise ... from None` also suppresses
    the chained Pydantic traceback). Candidate contracts set
    `hide_input_in_errors=True` as defense in depth so even the raw
    exception's formatted output omits rejected input. Raw `model_validate`
    remains available internally but is not the ingestion API.
11. **The bundled Threat catalog is the only candidate-validation
    authority.** `validate_threat_candidate_packet` always enforces the
    bundled, pin-verified catalog identity: an injected catalog must exactly
    match the bundled vocabulary ID, revision, pinned profile ref, and
    canonical digest, or it is rejected with
    `DndVocabularyIntegrityError` — an internally consistent caller-built
    catalog cannot widen the four-kind/four-predicate inventory.
    `_validate_against_catalog` is the private seam reserved for unit-test
    injection.

## Consequences

- `dungeonmind_dnd` gains `contracts/` (vocabulary catalog + candidate
  packet models), `domain/errors.py` (package-owned typed errors,
  transport-free), and `application/threat_candidates.py` (pure
  loader/renderer/validator). No file under `src/dungeonmind/` changes.
- Candidate ingestion is fail-closed against prose leakage: the parse
  boundary converts Pydantic failures into sanitized package-owned errors
  before any caller can observe rejected input.
- Validation authority is fail-closed against catalog substitution: only
  the bundled, digest-pinned Threat catalog can authorize candidate terms.
- Packet-level invariants (closed evidence ledger, endpoint resolution,
  grounding, ≥1 `dnd5e:threatens`, strict shapes) are model-enforced;
  catalog-dependent rules (exact term membership, namespace admission,
  predicate direction/domain/range, pin agreement) are enforced by the
  pure validator against the loaded catalog.
- The extraction portability rule holds: all executable code can move to
  another distribution later without changing profile/vocabulary
  identities, digests, schema versions, or packet shapes.
- Old consumers remain valid: v1 descriptors and namespace-only v3 graphs
  are untouched; the kernel's behavior is unchanged.

## Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| D&D kinds/predicates as kernel enums | Reject | Reverses the ADR-0004 ownership boundary |
| Open `properties` JSON bag on candidates | Reject | Recreates the universal WorldObject failure mode |
| Universal candidate schema in the kernel | Reject | Premature; no second-system evidence |
| `dnd5e:threat` object kind | Reject | Threat is contextual, not ontological identity |
| Graph publication from candidates | Reject | Candidate→contribution and contribution→publication are separate capabilities |
| LLM/provider integration in this slice | Reject | The contract must exist before any runtime chooses a provider |
| Statblock/mechanics fields | Reject | Independently useful successor (B.3); needs evidence-scoped semantics |
| Editing `dnd5e-profile-v1` in place | Reject | Published descriptors are immutable |
| Confidence scores on candidates | Reject | Confidence is never authority (founding invariant) |
| Verifying existing-object refs against a graph | Defer | Requires graph read authority; B.2d capability |
| Generic kernel term registry | Defer | Would begin the interpretation layer prematurely |
| Exposing raw Pydantic errors at candidate ingestion | Reject | Formatted errors and `errors()` records can carry rejected payloads (labels, summaries, locators) |
| Caller-supplied validation catalogs | Reject | The checked-in catalog is authoritative; injected catalogs must match its exact pinned identity |

## Reversal path

The D&D package is additive: deleting it removes no kernel capability and
no stored graph readability (kernel admission uses descriptors through the
registry port, not this package's contracts). Vocabulary and profile
revisions are immutable; a `threat-v2` catalog or `dnd5e-profile-v3`
descriptor can supersede semantics without rewriting v1/v2 artifacts or any
candidate packet shape already produced. Extracting the package to another
distribution is a packaging move that must keep descriptor/catalog bytes —
and therefore every digest — identical.
