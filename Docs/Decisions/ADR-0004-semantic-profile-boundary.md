# ADR-0004 — Semantic profile boundary (kernel vs game meaning)

**Status:** Accepted (PR B.2b)
**Date:** 2026-08-01
**Deciders:** B.2b implementing agent, per operator dispatch
**Supersedes:** none
**Related:** ADR-0001 (datastore), ADR-0002 (lifecycle ownership), ADR-0003
(derived indexes), `contracts/semantic_profile.py`,
`application/semantic_profiles.py`, `application/graph_snapshot.py` (v3),
`src/dungeonmind_dnd/`

## Question

Who owns D&D (or any game system's) semantic vocabulary in DungeonMind, and
how does a stored graph revision name the semantics its object kinds and
relationship predicates belong to — without making the first consumer the
universal ontology?

## Context

`dm_union_graph_v1` and `dm_union_graph_v2` carry open, unqualified `kind`
and `predicate` strings (`"artifact"`, `"advances_toward"`). The kernel
treats them as opaque labels; nothing records which vocabulary they come
from. DungeonMindBuddy's Threat/statblock work is approaching as a real
consumer with a D&D-flavored taxonomy. If D&D enums land in the kernel to
serve that consumer, the kernel becomes the owner of D&D meaning, the first
consumer's vocabulary becomes the de facto universal ontology, and every
future game system inherits a boundary violation that cannot be undone
without rewriting published revisions.

Closed invariants already in force: published graph schemas and durable
contracts are immutable and versioned; readers dispatch by exact
`graph_schema`; identity is opaque and never a label, path, or locator;
deployment configuration is never durable identity.

## Decision

1. **DungeonMind is a governed semantic kernel, not the owner of D&D
   meaning.** The kernel owns identity, evidence, revisions, retrieval, and
   admission. Game-system vocabulary is owned by a named, versioned semantic
   profile that lives outside the kernel's contract families.
2. **`dm_union_graph_v3` stores an exact profile reference in the graph
   payload** — a `SemanticProfileRef` (`dm_semantic_profile_ref_v1`) pinned
   by `profile_id` + `profile_revision` + `descriptor_sha256`. The ref lives
   in the payload, not in the `dm_graph_revision_v1` envelope; the envelope
   contract is untouched.
3. **Descriptor location is configuration; identity is the ref.** A
   descriptor's filesystem path exists only in a local registry config
   (`dm_semantic_profile_registry_config_v1`, resolved relative to the
   config file). Paths are never stored in graph payloads, public responses,
   or error details. Relocating an identical descriptor file and updating
   the config does not change graph identity; changing descriptor bytes
   changes the digest and requires a new immutable profile revision.
4. **V3 terms are qualified.** Every v3 node `kind` and relationship
   `predicate` is a `namespace:local` token whose namespace must be admitted
   by the pinned descriptor's `term_namespaces`. The kernel validates
   qualification and admission; it does not interpret the terms.
5. **V1 and V2 remain immutable and unqualified.** Their stored payloads
   reject a `semantic_profile` field, their vocabularies keep existing
   behavior byte-for-byte, and their fixture vocabulary is not retroactively
   claimed as canonical taxonomy.
6. **`dungeonmind_dnd` begins as a sibling package in the same repository
   and wheel.** One distribution currently contains both packages; the D&D
   5e descriptor ships as package data
   (`dungeonmind_dnd/profiles/dnd5e-v1.json`, profile
   `dungeonmind.dnd5e` revision `dnd5e-profile-v1`).
7. **The dependency is one-way.** No code under `src/dungeonmind` imports
   `dungeonmind_dnd` (enforced by `tests/unit/test_import_boundaries.py`).
   The kernel resolves profiles through the `SemanticProfileRegistry` port
   and operator configuration, never through package imports.
8. **Descriptors are data-only.** A descriptor enumerates admitted term
   namespaces for one pinned revision. It carries no file paths, module
   names, URLs, `latest` pointers, hooks, or executable behavior.
9. **No generic ontology interpreter exists yet.** The kernel admits or
   rejects qualified terms against a descriptor; anything beyond that
   (taxonomy reasoning, mechanics, cross-profile mapping) waits for concrete
   second-system evidence.
10. **A synthetic alien canary protects the boundary.** The B.2b proof
    fixture pins `test.narrative` / `narrative-profile-v1` (namespace
    `narrative`) and forbids D&D strings in its world. The kernel proving v3
    against a non-D&D profile demonstrates decoupling; D&D is not the proof
    subject.
11. **GM/player/canon/session policy remains kernel policy for now.** It is
    DungeonMind's audience and admissibility machinery, not claimed as a
    universal TTRPG ontology, and not moved into any profile.
12. **Later extraction must preserve identity.** If `dungeonmind_dnd` is
    later extracted to its own repository or distribution, profile
    identities (`profile_id`, `profile_revision`, `descriptor_sha256`) and
    every stored graph reference must remain exactly resolvable.

## Consequences

- A new stored graph schema, `dm_union_graph_v3`, exists beside v1/v2:
  v2-shaped nodes plus a required, digest-verified `semantic_profile` ref;
  kinds and predicates are qualified terms admitted by the pinned profile.
- New contracts (`dm_semantic_profile_ref_v1`, `dm_semantic_profile_v1`,
  `dm_semantic_profile_registry_config_v1`) and a new application port
  (`SemanticProfileRegistry`) with static and filesystem adapters; the
  default registry is empty, so v3 reads fail closed when no registry is
  configured (no silent default to `dungeonmind.dnd5e`).
- Typed failure codes: `semantic_profile_not_found`,
  `semantic_profile_integrity_error`, `semantic_term_validation_error` —
  all persistence-integrity failures, none leaking local paths.
- The demo host wires the filesystem registry from
  `DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH`; fixture preflight and
  readiness share the configured versioned reader.
- Every old descriptor revision must remain loadable for as long as the v3
  graphs pinned to it must remain readable.
- D&D mechanics contracts remain excluded from `src/dungeonmind`; the first
  real D&D taxonomy/mechanics capability is a named future lane, not this
  slice.

## Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Put D&D enums in core now | Reject | Makes first consumer the universal ontology |
| Keep open unqualified strings forever | Reject for V3 | Ownership remains ambiguous |
| Add profile fields to V2 | Reject | Published schemas are immutable |
| Add profile fields to graph-revision envelope v1 | Reject | Would silently change a durable contract |
| Store descriptor filesystem path in graph | Reject | Deployment path is not durable identity |
| Embed the whole descriptor in every graph | Reject for now | Duplicates profile history and weakens package ownership |
| Load executable plugins by import path | Reject | Too broad and unsafe |
| Create a separate repository now | Defer | Breaks atomicity before operational need |
| Build universal ontology interpretation now | Defer | No second-system evidence |

## Reversal path

The profile reference is additive payload data on a new schema version; v1
and v2 revisions are untouched and readable forever. V3 can be superseded by
a v4 schema that changes the pinning or admission rules without rewriting
any stored v1–v3 revision. Extracting `dungeonmind_dnd` to another
repository or wheel is a packaging move that must keep descriptor bytes —
and therefore every digest and graph reference — identical. The non-coupling
itself (kernel never imports a profile package) needs no reversal.
