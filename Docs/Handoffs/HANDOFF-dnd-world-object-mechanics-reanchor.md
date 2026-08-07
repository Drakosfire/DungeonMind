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

- `Docs/Roadmaps/ROADMAP-play-world-object-combat-projection.md` (Buddy `main` at `e0dc0a098d1306694e0cfbaccf80ef97879ca884`)
- `Docs/Plans/PR-TRACKER-play-world-object-combat-projection.md` (Buddy `main` at `8d2a35019f64fa80b716a7d621903908e14d95b1`; landed after the roadmap)

Cite the roadmap as the primary Play product authority. The tracker is the
sequencing companion now also on `main`; re-anchor against current Buddy
`main` before treating either SHA as frozen forever.

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
  (no hostility prerequisite; full exactness retained)
→ zero/one/many attachment + role/phase/variant semantics (no first-winner)
→ explicit dnd5e:creature disposition (prefer peer kinds; no ontology hierarchy)
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
3. Defines one profile-owned **generic mechanics-attachment** contract that binds an eligible world object to exact opaque external mechanics resource(s) **without** requiring any `dnd5e:threatens` edge, while **preserving** the graph/profile/resource pinning integrity already proven by B.3a (not a weakened subset of identity fields).
4. Specializes that attachment for **Statblock-backed Threat and NPC** mechanics (exact resource ref / digest / revision semantics preserved from B.3a where possible).
5. Documents how a **future PC mechanics authority** plugs into the same world-object projection/capability model without claiming to be a StatblockRevision.
6. Supersedes rather than edits the current profile/vocabulary revision(s); old artifacts remain loadable and readable.
7. Names the lossless Buddy → `obj:*` / graph-revision / external-resource mapping requirements for the conformance-bridge successor (no silent `uses_statblock → dnd5e:threatens` rename).
8. Freezes **cardinality and role** semantics so zero/one/many exact attachments survive without first-winner selection, and so CombatantSeed (or equivalent capability) selection remains an explicit later choice.
9. Records how **`dnd5e:creature`** relates to the new Threat/NPC/PlayerCharacter kinds without inventing a general ontology hierarchy.

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
10. **Exactness is not optional when generalizing:** removing `threat_relationship_ids` as an eligibility gate must not discard `graph_payload_sha256`, semantic profile pin, exact resource ref, visibility/admissibility, or content-addressed binding identity.
11. **No first-winner attachments:** zero/one/many exact mechanics attachments must remain representable; role/phase/variant qualifiers must not be collapsed by silently selecting the first binding.

---

## §5 Work plan

1. **ADR** — Write `Docs/Decisions/ADR-0013-dnd-world-object-mechanics-reanchor.md` (number may adjust if another ADR lands first). Record:
   - what ADR-0005 decision 5 still holds (`dnd5e:threatens` is contextual);
   - what is reopened (persistent Threat kind vs relationship-only Threat);
   - mechanics attachment independence from hostility;
   - exactness material preserved when generalizing B.3a;
   - attachment cardinality/roles;
   - `dnd5e:creature` disposition relative to new kinds;
   - which revisions are superseded;
   - reversal path.
2. **Vocabulary / profile revision** — Add immutable package data for the new kinds and retained predicates. Exact spellings must be frozen (candidates below are proposals until the ADR chooses):

   ```text
   proposed kinds:
     dnd5e:threat
     dnd5e:npc
     dnd5e:player_character
     (+ decide dnd5e:creature disposition; retain location/faction/encounter as decided)

   retained contextual predicate:
     dnd5e:threatens
   ```

   If the ADR rejects `dnd5e:threat` as a kind name, it must still provide a persistent Threat identity representation that is not “creature + threatens edge”.

   **`dnd5e:creature` disposition (must choose explicitly; prefer A):**

   | Option | Meaning | Guidance |
   | --- | --- | --- |
   | A | Peer kind for creatures without a stronger product identity | Preferred. Expand predicate domains explicitly; no subtype interpreter. |
   | B | Conceptual superclass with profile-owned subtype semantics | Reject unless unavoidable; invents ontology hierarchy during cutover. |
   | C | Superseded for new DungeonBuddy world objects | Allowed only with an explicit migration story for historical graphs. |

   The kernel still has a single object-kind slot and no subtype interpreter. If Lysandra is `dnd5e:npc`, she is no longer literally `dnd5e:creature` unless the profile defines another mechanism. Do not stumble into accidental inheritance.
3. **Generic mechanics attachment contract** — Versioned profile-owned model that preserves B.3a exactness while removing hostility as eligibility. Minimum integrity material (names may match implementation):

   ```text
   WorldObjectMechanicsBinding (working name):
     world_id
     graph_revision_id
     graph_payload_sha256
     semantic_profile
     object_id
     object_kind          # eligible world-object kind under the new vocabulary
     exact mechanics resource ref   # DndMechanicsResourceRef or successor
     visibility / admissibility as appropriate
     content-addressed binding_id   # derived from the complete material

     NO contextual relationship required
     NO threat_relationship_ids eligibility gate
   ```

   **Design question the ADR must answer explicitly:** whether vocabulary identity (`threat_vocabulary` / successor catalog pin) belongs on the generic binding or only on domain specializations. Either answer is acceptable; omitting the question is not. Generalizing Threat mechanics must not weaken graph/profile/resource pinning.
4. **Attachment cardinality and roles** — Freeze zero/one/many semantics. Buddy already allows multiple exact bindings with roles:

   ```text
   primary
   alternate
   phase (+ phase_key)
   encounter_variant
   template
   ```

   and enumerates them rather than silently taking the first. The ADR/contracts must state:
   - a world object may have zero, one, or many exact mechanics attachments;
   - how role / phase / variant qualifiers are represented;
   - whether those qualifiers live on the generic attachment or on a domain specialization;
   - that hydration/listing never first-wins;
   - that selecting which attachment becomes a CombatantSeed (or equivalent capability activation) is an explicit later consumer/capability decision, not an implicit binding rule.
5. **Threat/NPC specialization** — Show how Statblock-backed Threat and NPC attachment reuse the generic contract (typed binding role / resource schema as needed). Do not force NPC to reuse a Threat-only type name if that encodes hostility.
6. **PC seam** — Document the plug-in boundary and explicit audit questions for the later PC authority slice. Do not invent CharacterRevision here.
7. **Compatibility** — Keep threat-v1 / B.3a loadable. State whether new hydration APIs accept old bindings, require dual pin, or confine old bindings to historical graphs.
8. **Proofs** — Update/add unit tests proving hostility independence, kind distinctness, exactness retention, and zero/one/many attachment behavior; keep import-boundary tests green.
9. **Successor naming** — Handback names exactly one Buddy conformance-bridge mission; does not implement it.

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
- `dnd5e:creature` disposition matches the ADR choice (peer / superseded / etc.) with no accidental subtype interpreter;
- generic binding retains graph payload digest, semantic profile pin, exact resource ref, and content-addressed binding identity (hostility fields absent);
- zero, one, and many attachments are representable; many-attachment fixtures enumerate without first-winner selection;
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
8. The only proposed generic binding drops graph payload digest, semantic profile pin, exact resource identity, or content-addressed binding identity while “simplifying.”
9. Many-attachment / role semantics are deferred or collapsed to first-winner “for later.”
10. The ADR invents a general ontology/type hierarchy to make NPC “be a creature.”

---

## §8 Required freeze answers (must appear in ADR + handback)

The PR is incomplete until these are answered explicitly:

1. How persistent Threat, NPC, and PlayerCharacter world identities are represented under the D&D semantic profile.
2. How contextual `dnd5e:threatens` remains independent from persistent Threat identity.
3. What exact generic/profile-owned contract attaches an external mechanics resource to an eligible world object without requiring contextual hostility — including which B.3a integrity fields are retained (`world_id`, `graph_revision_id`, `graph_payload_sha256`, `semantic_profile`, `object_id`, `object_kind`, exact resource ref, visibility/admissibility, content-addressed `binding_id`) and whether vocabulary identity belongs on the generic binding.
4. How Statblock-backed Threat/NPC mechanics specialize that attachment.
5. How a future PC mechanics authority plugs into the same world-object projection/capability model without pretending it is a StatblockRevision.
6. Which current profile/vocabulary revision is superseded rather than edited in place.
7. How existing `obj:*`, graph revision, and exact external-resource identities are expected to map losslessly from current Buddy state (requirements for the bridge successor — not the bridge itself).
8. What are the cardinality and role semantics of mechanics attachments? The contract must preserve multiple exact attachments without first-winner selection; define whether role/phase/variant qualifiers belong to the generic attachment or domain specialization; and identify who explicitly selects an attachment for a capability such as Combat activation.
9. What happens to `dnd5e:creature` relative to the new kinds — peer kind, rejected superclass hierarchy, or superseded for new DungeonBuddy objects — with predicate-domain consequences stated explicitly.

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
- Decisions table covering the nine freeze answers
- Verification (exact commands + results)
- What remains false (bridge, shadow, promotion, Play durable contracts, PC implementation)
- Named next slice: Buddy conformance bridge mission only

**Implementation note:** keep world-object semantics + hostility-independent exact mechanics attachment atomic in one implementation PR unless the diff proves unexpectedly large. Prefer not to split into a long micro-PR chain before Play can consume the corrected substrate.

---

## §11 Implementation handback — 2026-08-07

**Status:** COMPLETE (implementation branch; awaiting PR review)

### Repository identity

| Field | Value |
| --- | --- |
| Repo | `Drakosfire/DungeonMind` |
| Base SHA | `9b40c76f15a9934a7c0868a4522a30d44d24545e` (#22 merge / `main`) |
| Branch | `dnd/world-object-mechanics-reanchor-implementation` |
| Predecessors | Buddy #515 merged `46d3677d…` (`NOT_READY_FOR_BRIDGE`); DM #22 merged `9b40c76f…` |
| Buddy main | `46d3677d9ade0b7a83ab2cb07d2b6c635fb50f40` |

### Nine freeze answers

| # | Answer |
| --- | --- |
| 1 | Peer kinds under `world-object-v1`: `dnd5e:threat`, `dnd5e:npc`, `dnd5e:player_character` (+ retained peers) |
| 2 | `dnd5e:threatens` remains contextual; expanded domains; never defines Threat identity or mechanics eligibility |
| 3 | `DndWorldObjectMechanicsBinding` (`dmdnd_world_object_mechanics_binding_v1`) retains full exactness; **vocabulary pin on generic binding (Decision A)**; no `threat_relationship_ids` |
| 4 | `DndStatblockMechanicsAttachment` with content-addressed `attachment_id` from `binding_id+role+phase_key+variant_label`; requires exact PR #21 statblock resource via shared predicate |
| 5 | PC kind valid; not eligible for world-object mechanics binding; no CharacterRevision invented |
| 6 | Superseded for new work: v2+threat-v1 as *historical*; new pins `dnd5e-profile-v3` + `world-object-v1` (old bytes unchanged) |
| 7 | Bridge must map Threat/NPC/PC → kinds; `uses_statblock` → mechanics binding + attachment (`attachment_id`/role/phase/variant); never → `threatens` |
| 8 | Zero/one/many; same resource may specialize many times; enumerate by `attachment_id`; CombatantSeed selection = later consumer |
| 9 | `dnd5e:creature` remains peer kind (Option A); intentionally non-mechanics-bearing under v3 (does not fall through to B.3a) |

### Exact semantic artifacts

| Artifact | ID / revision | Digest |
| --- | --- | --- |
| Profile v3 | `dungeonmind.dnd5e` / `dnd5e-profile-v3` | `2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496` |
| Vocabulary | `dungeonmind.dnd5e.world_object` / `world-object-v1` | `7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880` |
| Profile v1 (unchanged) | `dnd5e-profile-v1` | `582851c0fc41897fff5a57a4fd6dd7fb7078b865315a30bc21552c82e7596967` |
| Profile v2 (unchanged) | `dnd5e-profile-v2` | `57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086` |
| threat-v1 (unchanged) | `threat-v1` | `0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047` |

### Exact mechanics contract

- Schema: `dmdnd_world_object_mechanics_binding_v1`
- Eligible kinds: `dnd5e:threat`, `dnd5e:npc`
- Binding ID material: schema + world_id + graph_revision_id + graph_payload_sha256 + semantic_profile + world_object_vocabulary + object_id + object_kind + visibility + resource_ref
- Hydration: `hydrate_world_object_mechanics` (transport-neutral; no new HTTP route)
- Statblock specialization schema: `dmdnd_statblock_mechanics_attachment_v1`
- Attachment ID material: exact `binding_id` + `role` + `phase_key` + `variant_label` (Buddy string grammar; no trim)
- Statblock resource gate: shared `is_exact_dungeonmind_statblock_resource_ref` (PR #21 identity)
- Enumeration: `enumerate_statblock_mechanics_attachments` (no first-winner; uniqueness on `attachment_id`)

### Compatibility evidence

- Old profile/vocab raw bytes pinned (`V1_RAW_SHA256` / `V2_RAW_SHA256` / `THREAT_VOCAB_RAW_SHA256`)
- B.3a golden binding fixture still validates and hydrates
- Import boundaries extended only for `world_object_mechanics` under existing mechanics allowlist

### New proof matrix

| Fixture | Result |
| --- | --- |
| A Threat + mechanics + zero threatens | PASS |
| B NPC + mechanics + zero threatens | PASS |
| C Threat + threatens + zero mechanics | PASS (axes independent) |
| D NPC + threatens remains NPC | PASS |
| E multiple attachments no first-winner | PASS |
| Same resource as primary + alternate | PASS (distinct `attachment_id`) |
| Same resource as two phase keys | PASS |
| `variant_label` round-trip / identity | PASS |
| Buddy `phase_key=" enraged "` preserved | PASS |
| Buddy `variant_label=""` preserved | PASS |
| Buddy `variant_label=" night raid "` preserved | PASS |
| Duplicate specialization rejected | PASS |
| Generic D&D resource ≠ statblock attachment | PASS |
| F PlayerCharacter identity, no invented mechanics | PASS (`object_kind_not_eligible`) |
| G historical B.3a | PASS |
| v3 creature intentionally non-mechanics-bearing | PASS |
| Adversarial forged binding / digest mismatch | PASS |
| Published raw bytes pinned | PASS |

### Named successor

```text
STATBLOCK: adapt exact DungeonBuddy world-object/mechanics identity into the re-anchored DungeonMind D&D contract
```

### Remains false

Buddy→DM production mapping; shadow hydration; authority promotion; Play CombatSourceLocator; PC mechanics cutover; new generic mechanics HTTP endpoint; demolition of Buddy hydration.
