# HANDOFF — Eldyrwild whole-world object kinds v2 (handback)

**Created:** 2026-08-08
**Status:** COMPLETE — implementation handback
**Repository:** `Drakosfire/DungeonMind`
**Flow:** DND / SEMANTIC PROFILE
**Branch:** `dnd/eldyrwild-world-object-v2`
**Base SHA:** `6918c7c6fbabc10849b29b831eea235e13bab74c` (DungeonMind `main`, merge of #25)
**Approved #25 head:** `9c229f8c4024d6e327b91f49152770a6a3a9e194` (ancestor of base)

**Review accounting:** `review cycles: 0`

---

## §1 New immutable artifact

| Axis | Value |
|------|--------|
| Profile id | `dungeonmind.dnd5e` |
| Profile revision | `dnd5e-profile-v3` |
| Profile digest | `2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496` |
| Vocabulary id | `dungeonmind.dnd5e.world_object` |
| Vocabulary revision | `world-object-v2` |
| Vocabulary digest | `a53e2d0ec45878288800ff3d30006d54803db70a17e6680b359a0fa88f2a9922` |

---

## §2 Exact kind table (12)

| Term | Semantics (one sentence) |
|------|--------------------------|
| `dnd5e:creature` | Persistent creature identity without a stronger product-specific kind; peer, not superclass. |
| `dnd5e:threat` | Persistent Threat identity; independent from `threatens` and mechanics. |
| `dnd5e:npc` | Persistent non-player character identity; may carry mechanics without becoming a Threat. |
| `dnd5e:player_character` | Persistent PC identity; does not imply a StatblockRevision. |
| `dnd5e:location` | Campaign place referenced by identity. |
| `dnd5e:faction` | Persistent organized group/affiliation. |
| `dnd5e:encounter` | Bounded play/preparation situation; not synonymous with combat. |
| `dnd5e:item` | Persistent in-world item/object identity; no implied mechanics/resource/ownership. |
| `dnd5e:mystery` | Persistent unresolved investigative identity; independent from epistemic standing. |
| `dnd5e:group` | Coherent collection identity; peer to Faction and Party. |
| `dnd5e:party` | Adventuring/expedition party identity; membership explicit, not automatic for PCs. |
| `dnd5e:event` | Occurrence-shaped world identity; standing owned by assertion/temporal metadata, not kind. |

---

## §3 Historical proof

```text
dnd5e-profile-v3 unchanged
world-object-v1 unchanged
world-object-v1 digest unchanged (7cc3b285…)
existing v1 loader / ref semantics unchanged
world-object mechanics exact v1 pin unchanged
Threat historical candidate path untouched by this PR
```

Additive APIs only:

```text
load_builtin_world_object_v2_vocabulary()
builtin_world_object_v2_vocabulary_ref()
```

---

## §4 Predicate proof

```text
world-object-v2 predicates == world-object-v1 predicates
(model_dump equality for all four predicates)
located_in / attacks / contains absent
```

---

## §5 #522 expected ledger delta (after Buddy re-pin + adapter)

```text
WORLD_OBJECT_KIND: 260 → 0
```

when Buddy explicitly maps:

```text
item → dnd5e:item
mystery → dnd5e:mystery
group → dnd5e:group
party → dnd5e:party
event → dnd5e:event
```

No Buddy adapter is implemented in this PR.

---

## §6 Remaining blockers

```text
RELATIONSHIP_PREDICATE
ATTRIBUTE_ASSERTION
CONTRIBUTION_HISTORY
DURABLE_ADOPTION_BOUNDARY
POSTGRES_ADOPTION
remaining provenance/visibility adapter gaps
WHOLE_GRAPH_ADOPTION_NOT_READY
CUTOVER_NOT_READY
```

---

## §7 Nonclaims

```text
No Eldyrwild graph was migrated.
No Buddy adapter was implemented.
No new relationship predicate was accepted.
located_in was not mapped to located_at.
attacks was not mapped to threatens.
contains was not treated as an inverse-derived relationship.
No role/property semantics were published.
No fictional-time semantics changed.
No mechanics binding was repinned.
No product surface consumes world-object-v2 yet.
WHOLE_GRAPH_ADOPTION_NOT_READY remains correct.
CUTOVER_NOT_READY remains correct.
```

---

## §8 Named successor

```text
DND: adjudicate Eldyrwild whole-world relationship vocabulary v3
```

---

## §9 Files

| Path | Change |
|------|--------|
| `src/dungeonmind_dnd/vocabularies/world-object-v2.json` | CREATE |
| `src/dungeonmind_dnd/application/world_object_vocabulary.py` | additive v2 loader/ref |
| `src/dungeonmind_dnd/application/__init__.py` | exports |
| `pyproject.toml` | hatch package-data map |
| `Docs/Decisions/ADR-0016-eldyrwild-whole-world-object-kinds-v2.md` | CREATE |
| `Docs/Architecture/ARCHITECTURE.md` | narrow status |
| `README.md` | narrow status |
| `tests/unit/test_dnd_world_object_v2.py` | CREATE |
| `tests/fixtures/dungeonmind_dnd/eldyrwild_kind_inventory_v1.json` | CREATE |
| `Docs/Plans/HANDOFF-eldyrwild-whole-world-object-kinds-v2.md` | this handback |
