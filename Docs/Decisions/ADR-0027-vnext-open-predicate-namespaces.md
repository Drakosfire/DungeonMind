# ADR-0027 — Versioned authored-predicate namespaces in vNext

**Status:** Accepted — `SEMANTIC_PROFILE_V3_OPEN_PREDICATE_NAMESPACES_ACCEPTED`
**Scope:** Generic DungeonMind vNext semantic-profile admission
**Predecessor:** ADR-0024 and the immutable `dm_semantic_profile_v2` contract
**Evidence:** PR #77, substantively reviewed head `0f709d76fdc53bac9c9258d1751463ae2c76ca71` (`SEMANTIC_PROFILE_V3_SUBSTANTIVE_PASS`), merged as `a9051f02dfd95e051a83c1d74b26bb04a2b3e5bf`

## Problem

A consumer may allow a human to author a new relationship predicate while a
knowledge space retains a governed, digest-pinned semantic profile. A finite
list of predicate terms cannot admit a term created after the profile was
published. Replacing that list with an empty V2 list admits every value kind
for every qualified predicate and discards the useful fixed-term checks.

## Decision

`dm_semantic_profile_v3` extends the V2 descriptor with
`open_predicate_namespaces`. Each entry names one declared term namespace and
the value kinds admitted for otherwise unlisted predicates in that namespace.
For example, a consumer may open `dungeonbuddy.custom` for `entity_ref` values
without opening its fixed fact predicates or any other namespace.

The descriptor and its digest remain pinned by each immutable knowledge
revision. Exact predicate specs and open namespaces must be disjoint, so a
term cannot silently fall back to an open rule if its fixed spec is removed.
V3 rejects an unlisted term outside its open namespaces and a term whose
value kind is not admitted by its matching namespace rule. V2 admission is
unchanged, including its historical empty-predicate behavior.

Both governed materialization and knowledge reads use the same predicate
admission function. A custom predicate is an ordinary assertion predicate;
it has no built-in identity, merge, equivalence, inverse, or transitive
meaning. Qualification and lexical validity remain enforced by the existing
`QualifiedTerm` contract. The consumer owns any UI normalization and must not
silently substitute a different predicate.

## Version and transition boundary

This change does not rewrite a historical V2 descriptor or its digest. A new
space may pin V3 at initialization. Existing revisions remain readable under
their own pins. Governed publication currently inherits the parent's exact
profile ref; changing an already-created space from V2 to V3 requires a
separately designed profile-transition capability. This ADR does not add one
or imply that a child publication may silently change semantic authority.

## Not included

- A global open-vocabulary switch or a D&D vocabulary in the kernel.
- Registration of individual terms as graph identity or source evidence.
- Human review UX, automatic synonym/identity merging, or an HTTP endpoint.
- Profile migration for an existing space.
