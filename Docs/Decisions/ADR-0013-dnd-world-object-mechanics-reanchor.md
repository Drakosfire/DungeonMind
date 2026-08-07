# ADR-0013 — D&D persistent world-object kinds and exact mechanics attachment

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Implementation agent per #22 handoff after Buddy #515 / DungeonMind #22 merge
**Supersedes (partially):** ADR-0005 decision 5 *only insofar as* persistent Threat
identity was forbidden as an object kind and mechanics eligibility was left
coupled to Threat proving-domain assumptions.
**Does not supersede:** ADR-0004; ADR-0005 decisions 1–4 and 6–10;
immutability of published profile/vocabulary bytes; one-way kernel/profile
boundary; absence of a generic ontology interpreter.
**Related:** `Docs/Handoffs/HANDOFF-dnd-world-object-mechanics-reanchor.md`,
Buddy Play roadmap/tracker, Buddy PR #515 (`NOT_READY_FOR_BRIDGE`)

## Question

Under Play pressure, how should the D&D semantic profile represent persistent
Threat / NPC / PlayerCharacter world identities, keep contextual
`dnd5e:threatens` independent, and attach exact external mechanics without
requiring fictional hostility — without weakening B.3a exactness or inventing
PC mechanics?

## Context

ADR-0005 deliberately defined Threat as contextual `dnd5e:threatens` and
rejected `dnd5e:threat` as a kind. B.3a `DndThreatMechanicsBinding` then
required `dnd5e:creature` plus one or more `dnd5e:threatens` edges before
mechanics could bind.

DungeonBuddy Play now freezes Threat, NPC, and PlayerCharacter as distinct
first-class world objects. Allied NPCs (e.g. Lysandra) already have
statblocks. Player Characters already have independent mechanics authority.
Manufacturing hostility merely to hydrate mechanics is forbidden. Buddy
`uses_statblock` is mechanics attachment, not `dnd5e:threatens`.

That is the second-system pressure ADR-0005 deferred.

## Decision

### 1. Persistent world identities (freeze Q1)

New immutable vocabulary revision `world-object-v1`
(`dungeonmind.dnd5e.world_object`) admits peer object kinds:

```text
dnd5e:creature
dnd5e:threat
dnd5e:npc
dnd5e:player_character
dnd5e:location
dnd5e:faction
dnd5e:encounter
```

New cutover work pins semantic profile revision `dnd5e-profile-v3` (same
`dungeonmind.dnd5e` id and `dnd5e` namespace inventory as v2; new revision
string + digest only). Historical graphs remain on v2 + `threat-v1`.

### 2. `dnd5e:threatens` independence (freeze Q2)

`dnd5e:threatens` remains a contextual relationship. It does not define
Threat identity, mechanics eligibility, combat eligibility, or NPC hostility
as identity. Predicate domain/range explicitly admit the new peer kinds that
may participate. No inferred “is-a creature” hierarchy.

### 3. Exact hostility-independent mechanics binding (freeze Q3)

New schema `dmdnd_world_object_mechanics_binding_v1`
(`DndWorldObjectMechanicsBinding`) binds:

```text
world_id
graph_revision_id
graph_payload_sha256
semantic_profile
world_object_vocabulary   # Decision A: vocabulary pin on generic binding
object_id
object_kind               # eligible: dnd5e:threat | dnd5e:npc
resource_ref
visibility
content-addressed binding_id
```

No `threat_relationship_ids`. No hostility prerequisite.

**Vocabulary pin decision (A):** the authoritative world-object vocabulary
ref belongs on the generic binding so kind admission and binding identity
remain fail-closed against an exact catalog pin (same strength as B.3a’s
`threat_vocabulary` field, without encoding Threat hostility).

### 4. Statblock specialization (freeze Q4)

Closed specialization `DndStatblockMechanicsAttachment` pairs one exact
world-object mechanics binding with:

```text
attachment_id          # content-addressed from binding_id + role + phase_key + variant_label
binding
role ∈ {primary, alternate, phase, encounter_variant, template}
phase_key required iff role == phase (Buddy grammar: strip() nonempty only;
no stored-string trim; surrounding whitespace preserved)
variant_label optional ``str | None`` exactly as Buddy (including ``""`` and
surrounding whitespace; no nonblank restriction)
```

The generic binding remains role-free and may be shared by multiple
specializations of the same exact resource. Distinct
`(role, phase_key, variant_label)` tuples produce distinct
`attachment_id` values using the **exact** stored strings (no silent
repair/trim); enumeration uniqueness rejects identical specializations,
not shared generic `binding_id` values.

`DndStatblockMechanicsAttachment` additionally requires
`binding.resource_ref` to match the exact PR #21 DungeonMind statblock
identity (`dungeonmind.statblocks` /
`dungeonmind.dungeonbuddy-statblocks.1.0.0` / `sb_*` / `rev_*`), using the
shared `is_exact_dungeonmind_statblock_resource_ref` predicate. A valid
generic D&D mechanics resource cannot masquerade as a statblock
attachment.

Statblock role vocabulary stays off the generic external-resource binding.

### 5. PC plug-in boundary (freeze Q5)

`dnd5e:player_character` is a valid persistent world-object kind under
`world-object-v1`. This revision does **not** invent CharacterRevision,
PC-as-StatblockRevision, or a universal Character store. Future PC mechanics
authority plugs in via a later audit; PC is not an eligible kind for
`DndWorldObjectMechanicsBinding`.

### 6. Supersession without byte mutation (freeze Q6)

| Artifact | Status |
| --- | --- |
| `dnd5e-profile-v1` / `dnd5e-v1.json` | unchanged, readable |
| `dnd5e-profile-v2` / `dnd5e-v2.json` | unchanged, readable; historical B.3a pin |
| `threat-v1` | unchanged, readable; historical Threat vocabulary |
| `dnd5e-profile-v3` | **new** cutover profile pin |
| `world-object-v1` | **new** cutover vocabulary |

B.3a `DndThreatMechanicsBinding` / derive / hydrate / transport remain
authoritative for graphs pinned to v2 + threat-v1. New cutover work pins v3 +
world-object-v1 + the new binding.

### 7. Buddy bridge mapping requirements (freeze Q7)

The later conformance bridge must map losslessly, without silent renames:

| Buddy | DungeonMind (re-anchored) |
| --- | --- |
| `threat:*` / Threat world identity | `obj:*` with `kind=dnd5e:threat` |
| NPC world identity | `obj:*` with `kind=dnd5e:npc` |
| PC world identity | `obj:*` with `kind=dnd5e:player_character` |
| exact graph revision | `rev:*` + `graph_payload_sha256` |
| `uses_statblock` + `ThreatStatblockBindingV1` | world-object mechanics binding + statblock attachment (`attachment_id`, role, phase_key, variant_label) |
| exact resource id/revision/digest | `DndMechanicsResourceRef` |
| contextual hostility edges (if any) | optional `dnd5e:threatens` — **never** derived from `uses_statblock` |

### 8. Cardinality / roles / selection (freeze Q8)

A world object may have zero, one, or many exact mechanics attachments.
Enumeration is deterministic (stable sort by attachment_id, then
binding_id, then role, then phase_key / variant_label). There is never
implicit `first()` / `latest()` / list-order preference. Selecting which
attachment activates a capability (e.g. Combat / CombatantSeed) is an
explicit later domain/capability consumer decision — not the binding
layer.

### 9. `dnd5e:creature` disposition (freeze Q9)

**Option A — peer kind.** `dnd5e:creature` remains for creatures without a
stronger persistent product identity. Threat / NPC / PlayerCharacter are
peers, not subtypes. Predicate catalogs expand domains explicitly. No kernel
or profile subtype interpreter.

**Mechanics eligibility under v3:** `DndWorldObjectMechanicsBinding` admits
only `dnd5e:threat` and `dnd5e:npc`. A v3 `dnd5e:creature` is intentionally
**non-mechanics-bearing** for this revision. It does **not** fall through to
historical B.3a (`DndThreatMechanicsBinding`), which remains hard-pinned to
`dnd5e-profile-v2` + `threat-v1`. Creature mechanics under v3 are a named
later semantic slice if product pressure requires them.

## What remains true from ADR-0005

- Profile semantics stay outside the kernel (ADR-0004 / ADR-0005).
- Published profile/vocabulary revisions are immutable.
- No generic ontology interpreter exists.
- `dnd5e:threatens` is contextual fictional meaning.
- One-way dependency; no import-time package I/O; fail closed.

## What is superseded for new cutover work

- Persistent Threat cannot be represented solely as “creature + threatens”.
- Mechanics eligibility cannot require `dnd5e:threatens`.
- `dnd5e:threat` is a valid kind under `world-object-v1` (forbidden only under
  the historical `threat-v1` candidate path).

## Consequences

- Additive package data + contracts + pure application derive/hydrate.
- No new HTTP route in this slice.
- No Buddy bridge, shadow, Play, or PC mechanics implementation.
- Existing B.3a fixtures and tests remain green against retained pins.

## Reversal

Revert by stopping new work from pinning v3 / world-object-v1 / the new
binding schemas. Historical v2 / threat-v1 / B.3a paths remain loadable;
published bytes are never edited either direction.
