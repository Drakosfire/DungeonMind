# ADR-0017 — Campaign thread world-object kind v5

**Status:** Accepted  
**Date:** 2026-08-12  
**Deciders:** implementing agent, per CUTOVER Case A dispatch after DungeonMindBuddy PR #568  
**Supersedes:** none  
**Related:** ADR-0013, ADR-0016, `vocabularies/world-object-v4.json`, `vocabularies/world-object-v5.json`, `vocabularies/world-property-v2.json`, `vocabularies/world-property-v3.json`, `Docs/Plans/HANDOFF-cutover-thread-world-object-v5.md`

## Question

How does DungeonMind admit the one Eldyrwild `WORLD_OBJECT_KIND` blocker selected by merged Buddy PR #568 — Buddy kind `thread` — without collapsing it into mystery/event, widening relationship endpoints, changing mechanics, or starting existing-world adoption?

## Context

DungeonMindBuddy PR #568 (`e5aaaf1d3d1e1e9f8c07a62383770dfd8326f259`) produced a whole-world CUTOVER ledger that remains `CUTOVER_NOT_READY` and selected Case A:

```text
WORLD_OBJECT_KIND = 1
blocking_stage = adoption_package_construction
responsible_repo = DungeonMind
durable_field_path =
  node:mystery:session25:light-and-sound-as-search-tools-during-night-response:field:kind
buddy_kind = thread
```

Buddy already treats `thread` as a peer entity kind. Mapping it to `dnd5e:mystery` or `dnd5e:event` would erase source identity semantics. The five remaining dual-sense relationship STOPs are not `thread` endpoint failures and stay out of scope.

## Decision

1. **Publish immutable `world-object-v5`** under `vocabulary_id = dungeonmind.dnd5e.world_object`, pinned to unchanged `dnd5e-profile-v3`.
2. **Admit exactly one new peer kind:** `dnd5e:thread` — persistent campaign/narrative continuity identity. The kind does **not** imply mystery/secrecy, event occurrence, quest/objective state, epistemic standing, fictional-time standing, completion state, or mechanics.
3. **Reject adapters** `thread → mystery`, `thread → event`, and `thread → encounter`.
4. **Preserve all `world-object-v4` predicates model-identically.** No `dnd5e:thread` subject/object endpoint widening in this revision.
5. **Publish `world-property-v3`** with identical `dnd5e:role` semantics, exact pin to world-object-v5, and subject-kind delta exactly `{dnd5e:thread}`.
6. **No profile, union-graph schema, or mechanics bump.** Catalog revision and those axes remain separate.
7. **Explicit loaders/refs only** (`load_builtin_world_object_v5_vocabulary`, `load_builtin_world_property_v3_vocabulary`, matching refs/validators). No latest/current/default semantics.
8. **Historical catalogs remain byte-immutable.**

## Consequences

DungeonMind can express the one #568 Case A kind gap. Buddy must still explicitly repin to this merged commit / v5 / v3 and re-run CUTOVER before the blocker is considered cleared. Dual-sense STOPs, attribute/evidence package blockers, and `DURABLE_ADOPTION_BOUNDARY` remain unresolved; CUTOVER stays not ready.
