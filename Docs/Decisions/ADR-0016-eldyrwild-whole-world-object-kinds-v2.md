# ADR-0016 — Eldyrwild whole-world object kinds v2

**Status:** Accepted
**Date:** 2026-08-08
**Deciders:** implementing agent, per operator dispatch
(`dnd/eldyrwild-world-object-v2`)
**Supersedes:** none
**Related:** ADR-0013 (world-object mechanics re-anchor), ADR-0014
(assertion-scoped graph v4), ADR-0015 (source/evidence provenance v2),
`vocabularies/world-object-v1.json`, `vocabularies/world-object-v2.json`,
`application/world_object_vocabulary.py`

## Question

How does the D&D semantic package admit the five persistent world-object kinds
proven missing by the real Eldyrwild whole-world adoption audit
(`item`, `mystery`, `group`, `party`, `event`) without rewriting historical
catalogs, expanding relationships, inventing property semantics, or silently
advancing mechanics/loader pins to a "latest" vocabulary?

## Context

DungeonMindBuddy PR #522 inventoried an exact Eldyrwild World Graph revision
and reported `WORLD_OBJECT_KIND` blocker count **260**, composed of:

| Buddy kind | Count |
| --- | ---: |
| item | 125 |
| mystery | 93 |
| group | 29 |
| party | 11 |
| event | 2 |

`world-object-v1` already publishes seven peer kinds and four predicates under
`dnd5e-profile-v3`. Relationship and attribute blockers remain larger and
require separate adjudication (`located_in ≠ located_at`, `attacks ≠ threatens`,
`node.role` property meaning). This revision therefore closes **kinds only**.

## Decision

1. **`world-object-v1` remains immutable.** Package-data bytes and catalog
   digest
   `7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880`
   are unchanged. Existing loaders and refs continue to mean v1.
2. **`world-object-v2` is additive** under the same
   `vocabulary_id = dungeonmind.dnd5e.world_object`, pinned to the **unchanged**
   `dnd5e-profile-v3` descriptor digest
   `2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496`.
3. **No `dnd5e-profile-v4`.** Namespace admission (`dnd5e`) is unchanged; a
   profile bump would add revision churn without semantic meaning.
4. **No `dmdnd_semantic_vocabulary_v2`.** Schema version and catalog revision
   are different axes. This slice adds kinds only, which
   `dmdnd_semantic_vocabulary_v1` already models.
5. **Five new peer kinds** are admitted with explicit meanings and negative
   boundaries:
   - `dnd5e:item` — persistent in-world item/object identity; does **not**
     imply mechanics, magical status, ownership, inventory, or an external
     mechanics resource.
   - `dnd5e:mystery` — persistent unresolved investigative identity; does
     **not** imply `epistemic_kind = speculative` (and speculative does not
     imply mystery).
   - `dnd5e:group` — coherent collection identity; peer to Faction and Party,
     not a superclass/subclass of either.
   - `dnd5e:party` — adventuring/expedition party identity; does **not** imply
     Faction, Group, or automatic PC membership.
   - `dnd5e:event` — occurrence-shaped world identity; does **not** imply
     Encounter, Session, or a fictional-time anchor; occurrence standing is
     owned by assertion metadata / temporal knowledge.
6. **`dnd5e:` denotes D&D-profile-owned semantics**, not necessarily official
   SRD/Wizards terminology. Existing profile terms such as `faction`,
   `encounter`, and `threat` already live in this authority boundary.
7. **Predicates are exact v1 copies.** The four terms
   `located_at`, `member_of`, `participates_in`, `threatens` keep identical
   labels, descriptions, and subject/object kind lists. Domain/range is **not**
   expanded to the new kinds in this revision.
8. **Relationship semantics are deferred.** No
   `located_in` / `attacks` / `contains` (or other observed predicates) are
   added or aliased.
9. **Property semantics are deferred.** No `dnd5e:role` (or other property
   catalog) is published. Kernel property storage from graph v4 does not grant
   D&D meaning.
10. **Mechanics remain pinned to `world-object-v1`.**
    `DndWorldObjectMechanicsBinding` / derive / hydrate continue to expect the
    exact v1 vocabulary pin. New kinds are not mechanics-eligible under that
    contract. No "v1 or v2" permissive check.
11. **Loaders do not silently advance.**
    `load_builtin_world_object_vocabulary()` and
    `builtin_world_object_vocabulary_ref()` remain historical v1.
    Additive `load_builtin_world_object_v2_vocabulary()` /
    `builtin_world_object_v2_vocabulary_ref()` are explicit pins. No
    `latest` / `current` / sort-and-take-last API.
12. **No Buddy runtime dependency or adapter.** Target terms are published
    only; Buddy→`dnd5e:*` mapping stays in a future Buddy conformance layer.
13. **No graph migration or rewrite.** Catalog publication mutates no stored
    revision and synthesizes no relationships.
14. **No hierarchy interpreter.** All twelve kinds are peers for current
    kernel purposes (`is_a` / `subclass_of` / kind families are out of scope).

## Consequences

- Package data gains `vocabularies/world-object-v2.json` and an additive hatch
  map entry. Historical `world-object-v1.json` is untouched.
- Application exports gain explicit v2 loader/ref symbols alongside unchanged
  v1 symbols.
- The complete 260-instance `WORLD_OBJECT_KIND` gap is structurally closable by
  a future explicit Buddy adapter. `WHOLE_GRAPH_ADOPTION_READY` remains false
  while relationship, property, contribution-history, and adoption seams stay
  unresolved.
- Named successor: adjudicate the full observed Eldyrwild relationship
  vocabulary before property semantics.

## Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Edit `world-object-v1` in place | Reject | Published catalogs are immutable |
| Create `dnd5e-profile-v4` with identical namespaces | Reject | Churn without semantic change |
| Introduce `dmdnd_semantic_vocabulary_v2` | Reject | Kinds-only change fits v1 schema |
| Expand predicate domains to new kinds | Reject | Relationship adjudication is a successor |
| Add `located_in` / `attacks` / `contains` | Reject | Explicit architecture decisions pending |
| Publish `dnd5e:role` | Reject | Property contract not designed |
| Repoint mechanics / historical loaders to v2 | Reject | Silent pin advance; invalidates bindings |
| Add `load_latest_world_object_vocabulary()` | Reject | No hidden latest |
| Infer mystery ↔ speculative or event ↔ session/ftime | Reject | Kind ≠ epistemic/temporal axes |
| Treat group as faction subtype / party as group subtype | Reject | No subtype interpreter; peers only |

## Reversal path

Stop calling the v2 loader/ref. Historical v1 bytes, digests, mechanics pins,
and Threat candidate paths remain readable. No stored graph carries an implicit
dependency on v2 until a consumer explicitly pins it.
