# HANDOFF — Whole-world source provenance v2 (handback)

**Created:** 2026-08-07  
**Status:** COMPLETE — implementation handback  
**Repository:** `Drakosfire/DungeonMind`  
**Flow:** SOURCE / WORLD / KERNEL  
**Branch:** `source/whole-world-provenance-v2`  
**Base SHA:** `3842f147c15c589dff76d29dc2ad398e6d92b4d5` (DungeonMind `main`, merge of #24)  
**Head SHA:** `afcb9cab28ad28cb3ec74b7703e563882f4015cd`  
**PR:** [#25](https://github.com/Drakosfire/DungeonMind/pull/25)  
**Approved #24 head:** `e563aafd346c2a510f8890965e53fe016cd3407f` (ancestor of base)

**Review accounting:** `review cycles: 0`

---

## §1 New public contracts

| Symbol | Schema / role |
|--------|----------------|
| `SourceArtifactV2` | `dm_source_artifact_v2` |
| `EvidenceRefV2` | `dm_evidence_ref_v2` |
| `WorkspaceDocumentRefV1` | `dm_workspace_document_ref_v1` |
| `SourceAuthority` | `primary` / `derived` / `reference` (nullable on v2) |
| `SourceReviewState` | `draft` / `reviewed` / `canonical` (nullable) |
| `SourceArtifactRecord` | `SourceArtifact \| SourceArtifactV2` |
| `EvidenceRefRecord` | `EvidenceRef \| EvidenceRefV2` |
| `GRAPH_SCHEMA_V5` | `dm_union_graph_v5` |
| `GraphEvidenceRecordV2` | v5 graph ledger row |
| `UnionGraphV5SnapshotReader` | exact v5 dispatch |

Historical: `EvidenceRef` / `SourceArtifact` / `SourceRevision` / graph v1–v4 unchanged.

---

## §2 Historical compatibility

```text
EvidenceRef v1 unchanged
SourceArtifact v1 unchanged
SourceRevision v1 unchanged
dm_union_graph_v1 unchanged
dm_union_graph_v2 unchanged
dm_union_graph_v3 unchanged
dm_union_graph_v4 unchanged
```

v4 rejects v2 evidence; v5 rejects v1 evidence.

---

## §3 Axis-separation table

| Concept | Meaning | Must not become |
|---------|---------|-----------------|
| `authority` | evidentiary role | source review state |
| `review_state` | source review standing | assertion canon / authority |
| `visibility` | DungeonMind access policy | producer visibility label |
| `source_visibility_state` | producer classification | access policy |
| `source_domain` | generic kernel provenance family | producer semantic identity |
| `source_domain_key` | exact producer classification | kernel behavior |
| `session_id` (evidence) | source/evidence provenance | fictional time |

---

## §4 Repository proof

- Memory: `InMemorySourceRepository` put/get v1|v2 by `schema_version`; idempotency conflict unchanged.
- PostgreSQL: migration `0004_source_artifact_v2_nullable` drops NOT NULL on `source_domain` + `visibility` only; payload jsonb preserves full v2 contract. `created_at` required for PG put (column NOT NULL; not manufactured from `updated_at`).

---

## §5 V5 proof

`dm_union_graph_v5` = v4 assertion-scoped objects/relationships + `dm_evidence_ref_v2` ledger. Scoped admission reuses v4 assertion grain. Public object/relationship dumps unchanged.

---

## §6 Expected #522 ledger delta (after Buddy re-pin)

Structurally representable:

```text
evidence.session_id
evidence.source_span_ref_id
evidence.source_locator
evidence.line_ref
source_domain_key (exact producer domain)
artifact_kind / document_class
authority_state → review_state (independent axis)
visibility_state → source_visibility_state (independent axis)
workspace_document_id / revision → workspace_document_ref
lineage
updated_at
```

Access-policy mapping for unknown visibility is **not** solved by durability alone.

---

## §7 Remaining blockers

```text
WHOLE_GRAPH_ADOPTION_NOT_READY
CUTOVER_NOT_READY
```

Still red: D&D whole-world vocabulary, Buddy→DM construction adapter, contribution genesis policy, existing-world adoption seam, Eldyrwild PG adoption, product authority, dark cutover.

---

## §8 Nonclaims

```text
No real Eldyrwild source migration was performed.
No Buddy adapter was added.
No source visibility mapping was assumed.
No source authority was invented from review_state.
No D&D source semantics were added to the kernel.
No contribution history was adopted.
No existing-world adoption seam was added.
DungeonMind is not yet whole-world product authority.
CUTOVER_NOT_READY remains correct.
```

---

## §9 Named successor

```text
DND: publish whole-world vocabulary v2 for Eldyrwild adoption
```

---

## §10 Verification (executed)

Unit (focused): green — source/evidence v2, graph v5, graph v4 lock, scope provenance, contract validators, fictional-time, import boundaries.

Integration: green — `test_postgres_source_v2`, `test_postgres_graph_v5`, `test_postgres_graph_v4`, `test_postgres_records`, `test_migrations` (head pin updated to 0004).

Ruff / pyright: green on touched modules.
