# HANDOFF — Whole-world source provenance v2 (handback)

**Created:** 2026-08-07
**Status:** COMPLETE — implementation handback (Cycle 2 corrections applied)
**Repository:** `Drakosfire/DungeonMind`
**Flow:** SOURCE / WORLD / KERNEL
**Branch:** `source/whole-world-provenance-v2`
**Base SHA:** `3842f147c15c589dff76d29dc2ad398e6d92b4d5` (DungeonMind `main`, merge of #24)
**PR:** [#25](https://github.com/Drakosfire/DungeonMind/pull/25)
**Approved #24 head:** `e563aafd346c2a510f8890965e53fe016cd3407f` (ancestor of base)
**Reviewed head (Cycle 2):** `9136d9305bf40c1d6f9a568c0c91dae2d65cb93b`
**Fix head (Cycle 2 corrections):** `a2fbf117852c36b9171da29688db90a63527543e`

**Review accounting:** `review cycles: 2` — Cycle 1 REQUEST CHANGES (3 P1 + 1 P2); Cycle 2 REQUEST CHANGES (1 P1 historical schema docstring)

---

## §0 Cycle 1 corrections

Reviewed head: `4a78c3eac7b33d33c8dab3f1233388c1f74113c1`

| Severity | Finding | Fix |
|----------|---------|-----|
| P1 | Mixed evidence/artifact schema mismatch before scope → public diagnostic leak | Scope (world/campaign/visibility / `SCOPE_UNKNOWN`) first; schema mismatch only after visible |
| P1 | Mind Turn reachable for v5 but `mind_turn_v1` cannot represent v2 evidence | Fail closed on `dm_union_graph_v5` in Mind Turn; no v2→v1 coercion |
| P1 | `SourceArtifactV2.created_at=None` rejected by Postgres | Migration `0005` nullable `created_at`; substrate `ensure_world` timestamp separated from producer timestamp |
| P2 | `GraphEvidenceRecordV2` defaults ≠ `EvidenceRefV2` requiredness | `GraphEvidenceRecordV2 = EvidenceRefV2`; field-omission matrix fails closed |

## §0b Cycle 2 corrections

Reviewed head: `9136d9305bf40c1d6f9a568c0c91dae2d65cb93b`

| Severity | Finding | Fix |
|----------|---------|-----|
| P1 | v1 `EvidenceRef` / `SourceArtifact` class docstring edits changed `model_json_schema()` and broke the D&D threat schema digest pin | Restored exact historical class docstrings; added direct v1 JSON-Schema digest locks (`test_historical_evidence_schema_locks.py`). Did **not** refresh the D&D digest. |

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
| `GraphEvidenceRecordV2` | alias of `EvidenceRefV2` (v5 ledger row) |
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

- Memory: `InMemorySourceRepository` put/get v1|v2 by `schema_version`; idempotency conflict unchanged; `created_at=None` / `updated_at=None` round-trip.
- PostgreSQL: migration `0004` drops NOT NULL on `source_domain` + `visibility`; migration `0005` drops NOT NULL on `created_at`. Unknown producer timestamps persist as NULL. World/campaign `ensure_*` uses a separate substrate timestamp and does not invent artifact `created_at`.

---

## §5 V5 proof

`dm_union_graph_v5` = v4 assertion-scoped objects/relationships + `dm_evidence_ref_v2` ledger (`EvidenceRefV2` requiredness). Scoped admission reuses v4 assertion grain. Public object/relationship dumps unchanged. Mind Turn fails closed on v5 until a later wire contract.

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

Still red: D&D whole-world vocabulary, Buddy→DM construction adapter, contribution genesis policy, existing-world adoption seam, Eldyrwild PG adoption, product authority, dark cutover. Mind Turn product reads of v5 await a versioned response/evidence contract.

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
mind_turn_v1 does not represent EvidenceRefV2.
```

---

## §9 Named successor

```text
DND: publish whole-world vocabulary v2 for Eldyrwild adoption
```

---

## §10 Verification (executed)

Unit (focused): green — source/evidence v2 (incl. scope-first adversarial), graph v5 field-omission matrix, Mind Turn v5 reject, null timestamp memory parity.

Integration: green — `test_postgres_source_v2` (incl. null timestamps), `test_postgres_graph_v5`, `test_migrations` (head pin `0005_source_created_at_null`).

Ruff / pyright: green on touched modules.
