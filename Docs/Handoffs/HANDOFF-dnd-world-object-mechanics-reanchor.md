# HANDOFF — D&D world-object kinds and mechanics attachment re-anchor

**Created:** 2026-08-07
**Status:** ACTIVE — dispatch exactly one DungeonMind-owned contract capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-dnd-world-object-mechanics-reanchor.md`
**Repository:** Drakosfire/DungeonMind
**Suggested branch:** `founding/dnd-world-object-mechanics-reanchor`
**Implementation base:** `7c311ae0d0d59d7379dee38780be509970fb3a8c` (GitHub `main` tip / PR #21 merge)
**Predecessor:** Buddy PR [#515](https://github.com/Drakosfire/DungeonMindBuddy/pull/515) corrected reconnaissance (`NOT_READY_FOR_BRIDGE` — contract reason); merged DungeonMind B.2c / B.3a / PR #20 / PR #21
**Suggested PR title:** DND: re-anchor world-object kinds and mechanics attachment for DungeonBuddy cutover
**One-line mission:** Extend the accepted D&D semantic profile so Threat, NPC, and PlayerCharacter are distinct persistent world-object kinds, keep contextual `dnd5e:threatens` independent from Threat identity, and attach exact external mechanics without requiring hostility — without implementing the Buddy bridge, shadow hydration, or Play surface.

---

## §0 Why this slice exists now

ADR-0004 / ADR-0005 deliberately deferred a shared world-object/mechanics abstraction until a second, materially different system created pressure.

That pressure has landed in DungeonMindBuddy:

- `Docs/Roadmaps/ROADMAP-play-world-object-combat-projection.md`
- `Docs/Plans/PR-TRACKER-play-world-object-combat-projection.md`

Play freezes:

```text
Threat
NPC
PlayerCharacter
```

as distinct first-class world objects. They may share projection and runtime capabilities, but they do not share domain meaning or mechanics authority merely because they can participate in combat.

Buddy PR #515 reconnaissance remains `NOT_READY_FOR_BRIDGE`, but the primary blocker is reframed: DungeonMind's accepted D&D profile conflates the narrow Threat proving domain with the reusable world-object/mechanics boundary Play requires. Manufacturing a Latchling fixture is explicitly rejected as the next action.

### Selected capability

```text
additive/versioned D&D profile + vocabulary revision(s)
→ persistent Threat / NPC / PlayerCharacter object kinds
→ contextual dnd5e:threatens remains independent
→ profile-owned generic mechanics-attachment contract
  (no hostility prerequisite)
→ Threat/NPC statblock specialization of that attachment
→ documented PC mechanics plug-in seam (not a fake StatblockRevision)
→ old ADR-0005 / threat-v1 / B.3a Threat-binding contracts remain readable
→ lossless Buddy mapping requirements named for the bridge successor
```

### Explicitly rejected for this slice

| Alternative | Decision | Reason |
| --- | --- | --- |
| Edit `dnd5e-profile-v2` or `threat-v1` in place | Reject | Published descriptors/catalogs are immutable |
| Buddy→DungeonMind identity bridge implementation | Reject | Successor after this contract freezes |
| Shadow hydration / authority promotion | Reject | Later chain steps |
| Latchling / Lysandra / PC real-domain fixtures as the primary proof | Reject | Synthetic conformance fixtures suffice until contract is correct |
| Universal kernel Character / WorldObject bag | Reject | ADR-0004 boundary; shared envelope is projection/capability, not storage |
| Pretend PC mechanics are a StatblockRevision | Reject | Play/PC audit forbids inventing CharacterRevision to mirror statblocks |
| Play route / CombatSourceLocator implementation | Reject | Buddy product work gated on this contract |
| Kernel imports of `dungeonmind_dnd` | Reject | One-way boundary remains absolute |
| Demolish B.3a Threat hydration path in the same PR | Reject | Old revisions stay readable; migration is additive |

### Governing invariant

World-object identity, semantic relationships, exact mechanics attachment, and runtime capabilities are independent axes. An NPC with a statblock is not a Threat. A Threat without a current `dnd5e:threatens` edge may still exist as a world object. Mechanics hydration must not require manufactured hostility.

### Mission falsification test

This is no longer one PR if it requires Buddy production code changes, a live shadow consumer, Play route work, PC generator implementation, editing published profile/catalog bytes in place, placing D&D enums in `src/dungeonmind`, or deleting the existing B.3a Threat mechanics path before a named successor owns demolition.

---

## §1 Outcome

After this PR, DungeonMindDnD has an additive, versioned semantic/mechanics contract that:

1. Represents persistent **Threat**, **NPC**, and **PlayerCharacter** world identities under the D&D semantic profile (exact term spellings frozen in the new vocabulary revision).
2. Keeps contextual **`dnd5e:threatens`** as a relationship that does not define Threat identity.
3. Defines one profile-owned **generic mechanics-attachment** contract that binds an eligible world object to one exact opaque external mechanics resource **without** requiring any `dnd5e:threatens` edge.
4. Specializes that attachment for **Statblock-backed Threat and NPC** mechanics (exact resource ref / digest / revision semantics preserved from B.3a where possible).
5. Documents how a **future PC mechanics authority** plugs into the same world-object projection/capability model without claiming to be a StatblockRevision.
6. Supersedes rather than edits the current profile/vocabulary revision(s); old artifacts remain loadable and readable.
7. Names the lossless Buddy → `obj:*` / graph-revision / external-resource mapping requirements for the conformance-bridge successor (no silent `uses_statblock → dnd5e:threatens` rename).

The existing B.3a `DndThreatMechanicsBinding` path either:

- remains available against the old vocabulary pin for historical graphs, and/or
- is explicitly superseded by a versioned successor binding that no longer embeds hostility as an eligibility gate,

with the ADR stating which behavior is authoritative for new cutover work.

---

## §2 Authority and anchors

Read in this order (checked-in sources only; chat is never authority):

### DungeonMind

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `Docs/Decisions/ADR-0004-semantic-profile-boundary.md`
4. `Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md` — especially decision 5 (Threat as relationship only) and decision 8 (second-system pressure gate)
5. `src/dungeonmind_dnd/vocabularies/threat-v1.json`
6. `src/dungeonmind_dnd/contracts/mechanics_resources.py`
7. `src/dungeonmind_dnd/application/threat_mechanics.py`
8. This handoff

### DungeonMindBuddy (consumer pressure; do not modify in this PR)

1. `Docs/Roadmaps/ROADMAP-play-world-object-combat-projection.md` (Buddy `main`)
2. `Docs/Plans/PR-TRACKER-play-world-object-combat-projection.md` (Buddy `main`)
3. `Docs/Design/DECISION-grounded-authored-world-object-lifecycle.md`
4. `Docs/Reports/REPORT-statblock-dungeonmind-cutover-reconnaissance.md` on PR #515 (corrected disposition)
5. `src/graph_memory/union_supergraph/statblock_binding.py` (`ThreatStatblockBindingV1`, `uses_statblock`)

---

## §3 Scope

**In scope:**

- New ADR that partially reopens ADR-0005 decision 5 under Play pressure, without reversing ADR-0004 ownership.
- New immutable D&D profile and/or vocabulary revision(s) admitting Threat / NPC / PlayerCharacter kinds as decided.
- New or versioned mechanics-attachment contracts that do not require `dnd5e:threatens`.
- Threat/NPC statblock specialization of that attachment.
- PC plug-in documentation + explicit non-goals for inventing CharacterRevision.
- Unit/conformance proofs that:
  - old threat-v1 / B.3a artifacts still load;
  - mechanics can bind to an eligible object with zero `dnd5e:threatens` edges;
  - `dnd5e:threatens` remains valid contextual vocabulary;
  - Threat identity is not interchangeable with “has threatens edge”.
- Roadmap note naming the Buddy conformance-bridge successor.

**Out of scope (falsification):**

- Any DungeonMindBuddy production source, route, UI, or Play implementation.
- Buddy→DungeonMind identity adapter / shadow consumer / authority promotion.
- Latchling fixture manufacturing.
- PC generator / character-sheet persistence implementation.
- Kernel D&D enums or kernel→profile imports.
- Editing published `dnd5e-profile-v2` / `threat-v1` bytes.
- Demolishing B.3a without a named demolition successor.
- Generic ontology interpreter / taxonomy reasoning layer.

---

## §4 Invariants that bind this slice

1. **Profile ownership:** D&D meaning stays in `dungeonmind_dnd`; kernel admits namespaces only (ADR-0004).
2. **Immutability:** published profile/vocabulary revisions are never edited in place.
3. **One-way dependency:** no `src/dungeonmind` import of `dungeonmind_dnd`.
4. **Identity ≠ label ≠ relationship ≠ mechanics:** opaque `obj:*` identity; relationships are contextual; mechanics are producer-owned external bytes.
5. **No hostility prerequisite for mechanics:** attachment eligibility must not require `dnd5e:threatens`.
6. **No silent renames:** Buddy `uses_statblock` is not `dnd5e:threatens`; Buddy `threat:*` is not “mere creature”.
7. **Additive cutover:** old revisions remain readable; new cutover work pins the new revision.
8. **Fail closed:** invalid kinds, missing resources, digest disagreement, and profile pin mismatch reject without repair.
9. **Second-system discipline:** shared abstractions extracted only where Play + Threat proving domains demand them; do not invent a universal Character store.

---

## §5 Work plan

1. **ADR** — Write `Docs/Decisions/ADR-0013-dnd-world-object-mechanics-reanchor.md` (number may adjust if another ADR lands first). Record:
   - what ADR-0005 decision 5 still holds (`dnd5e:threatens` is contextual);
   - what is reopened (persistent Threat kind vs relationship-only Threat);
   - mechanics attachment independence;
   - which revisions are superseded;
   - reversal path.
2. **Vocabulary / profile revision** — Add immutable package data for the new kinds and retained predicates. Exact spellings must be frozen (candidates below are proposals until the ADR chooses):

   ```text
   proposed kinds:
     dnd5e:threat
     dnd5e:npc
     dnd5e:player_character
     (+ retain creature/location/faction/encounter as decided)

   retained contextual predicate:
     dnd5e:threatens
   ```

   If the ADR rejects `dnd5e:threat` as a kind name, it must still provide a persistent Threat identity representation that is not “creature + threatens edge”.
3. **Generic mechanics attachment contract** — Versioned profile-owned model that binds:

   ```text
   world_id
   graph_revision_id
   object_id + object_kind
   exact DndMechanicsResourceRef (or successor)
   ```

   without requiring relationship IDs of predicate `dnd5e:threatens`.
4. **Threat/NPC specialization** — Show how Statblock-backed Threat and NPC attachment reuse the generic contract (typed binding role / resource schema as needed). Do not force NPC to reuse a Threat-only type name if that encodes hostility.
5. **PC seam** — Document the plug-in boundary and explicit audit questions for the later PC authority slice. Do not invent CharacterRevision here.
6. **Compatibility** — Keep threat-v1 / B.3a loadable. State whether new hydration APIs accept old bindings, require dual pin, or confine old bindings to historical graphs.
7. **Proofs** — Update/add unit tests proving hostility independence and kind distinctness; keep import-boundary tests green.
8. **Successor naming** — Handback names exactly one Buddy conformance-bridge mission; does not implement it.

---

## §6 Acceptance gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run pytest -m "not integration" -q
```

Focused proofs must include (names may match implementation):

- old `threat-v1` catalog still loads and digests stably;
- new vocabulary/profile revision loads and pins;
- mechanics attachment succeeds for an eligible object with **zero** `dnd5e:threatens` relationships;
- `dnd5e:threatens` remains valid when present and does not become the object kind;
- Threat / NPC / PlayerCharacter kinds are distinct and not collapsed into one Character kind;
- import boundaries still forbid kernel→profile imports;
- B.3a / transport tests either remain green against retained pins or have an explicit, tested compatibility story recorded in the ADR.

No Buddy repository changes are required for acceptance.

---

## §7 Stop conditions

Halt and report instead of widening scope if:

1. Correctness requires editing published profile/catalog bytes in place.
2. Correctness requires Buddy production code or a live bridge in the same PR.
3. The only way to hydrate NPC/PC mechanics is to synthesize `dnd5e:threatens` edges.
4. The design collapses Threat/NPC/PC into one universal Character object in the kernel.
5. PC support requires inventing a full CharacterRevision schema before auditing the real PC authority.
6. Import-boundary or founding charter stop conditions fire.
7. Play/CombatSourceLocator implementation is pulled into the diff.

---

## §8 Required freeze answers (must appear in ADR + handback)

The PR is incomplete until these are answered explicitly:

1. How persistent Threat, NPC, and PlayerCharacter world identities are represented under the D&D semantic profile.
2. How contextual `dnd5e:threatens` remains independent from persistent Threat identity.
3. What exact generic/profile-owned contract attaches an external mechanics resource to an eligible world object without requiring contextual hostility.
4. How Statblock-backed Threat/NPC mechanics specialize that attachment.
5. How a future PC mechanics authority plugs into the same world-object projection/capability model without pretending it is a StatblockRevision.
6. Which current profile/vocabulary revision is superseded rather than edited in place.
7. How existing `obj:*`, graph revision, and exact external-resource identities are expected to map losslessly from current Buddy state (requirements for the bridge successor — not the bridge itself).

---

## §9 Successor chain (do not compress)

```text
#515 corrected reconnaissance
        ↓
this slice — DungeonMind semantic/mechanics contract re-anchor
        ↓
Buddy → DungeonMind exact conformance bridge
        ↓
Buddy shadow hydration through DungeonMind
        ↓
bounded parity proof
        ↓
DungeonMind authority promotion + duplicate hydration demolition
        ↓
Play Phase W / C1 on the promoted identity/mechanics substrate
```

Play surface-shell work that is purely visual/routing may proceed independently in Buddy. No durable world-object, CombatSourceLocator, mechanics-ingress, NPC/PC projection, or Combat identity contract should harden before this chain settles.

---

## §10 Handback requirements

- Repositories and revisions (repo / branch / base SHA / head SHA / PR / status)
- Decisions table covering the seven freeze answers
- Verification (exact commands + results)
- What remains false (bridge, shadow, promotion, Play durable contracts, PC implementation)
- Named next slice: Buddy conformance bridge mission only
